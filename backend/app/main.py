"""VisaRef API — intake + Gloria desk + human lock."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pydantic import BaseModel, Field

from app.api_applications import (
    get_application_detail,
    list_applications,
    resolve_application_file,
)
from app.config import get_settings
from app.ingest.email_pipeline import process_visa_inbox
from app.ingest.email_watcher import watch_email_inbox
from app.ingest.pipeline import process_application
from app.ingest.render import allowed_suffix
from app.lock.actions import LockError, approve_application, mark_review, send_draft
from app.lock.tokens import issue_confirm_token
from app.storage.files import create_application, load_meta, store_upload

logger = logging.getLogger(__name__)
_REPO = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    watcher: asyncio.Task[None] | None = None
    if settings.email_imap_host and settings.email_imap_user and settings.email_imap_password:
        print("Email watcher enabled; connecting to Gmail...", flush=True)
        watcher = asyncio.create_task(watch_email_inbox(settings))
    else:
        logger.info("Email watcher disabled: configure EMAIL_IMAP_HOST, EMAIL_IMAP_USER, and EMAIL_IMAP_PASSWORD.")
    try:
        yield
    finally:
        if watcher is not None:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)


app = FastAPI(title="VisaRef", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/checklists")
def list_checklists() -> list[dict[str, str]]:
    settings = get_settings()
    out: list[dict[str, str]] = []
    for path in sorted(settings.checklist_dir.glob("*.yaml")):
        out.append({"id": path.stem, "file": path.name})
    return out


@app.post("/applications")
async def create_app(
    files: list[UploadFile] = File(...),
    checklist_id: str = Form("fr-schengen-short-stay"),
    submission_date: str = Form("2026-11-16"),
) -> dict:
    try:
        sub = date.fromisoformat(submission_date)
    except ValueError as exc:
        raise HTTPException(400, f"bad submission_date: {exc}") from exc

    settings = get_settings()
    if not (settings.checklist_dir / f"{checklist_id}.yaml").exists():
        raise HTTPException(400, f"unknown checklist_id: {checklist_id}")

    meta = create_application(checklist_id=checklist_id, submission_date=sub, settings=settings)
    saved: list[str] = []
    rejected: list[dict[str, str]] = []
    for uf in files:
        name = uf.filename or "upload.bin"
        data = await uf.read()
        if not allowed_suffix(Path(name)):
            rejected.append({"file": name, "reason": "unsupported_type"})
            continue
        path = store_upload(meta["id"], name, data, settings=settings)
        saved.append(path.name)

    return {
        "id": meta["id"],
        "checklist_id": checklist_id,
        "submission_date": sub.isoformat(),
        "files": saved,
        "rejected": rejected,
    }


@app.post("/applications/{application_id}/run")
def run_application(application_id: str) -> dict:
    try:
        load_meta(application_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    return process_application(application_id)


@app.get("/applications")
def applications_list() -> list[dict]:
    """Gloria queue: newest applications first."""
    return list_applications()


@app.get("/applications/{application_id}")
def get_application(application_id: str) -> dict:
    try:
        return get_application_detail(application_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc


@app.get("/applications/{application_id}/files/{filename}")
def get_application_file(application_id: str, filename: str):
    """Document preview (PDF/PNG) for Gloria's desk."""
    try:
        load_meta(application_id)
        path = resolve_application_file(application_id, filename)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc) or "file not found") from exc
    media = "application/pdf" if path.suffix.lower() == ".pdf" else None
    return FileResponse(path, filename=path.name, media_type=media)


class ConfirmTokenBody(BaseModel):
    application_id: str
    action: str = Field(..., description="approve | send_back | review")
    officer: str = Field(default="Gloria", min_length=1, max_length=80)


class GloriaActionBody(BaseModel):
    action: str = Field(..., description="approve | send_back | review")
    officer: str = Field(default="Gloria", min_length=1, max_length=80)
    confirm_token: str = Field(..., min_length=8)
    draft_id: str | None = None


class OfficerAuthBody(BaseModel):
    pin: str = Field(..., min_length=1, max_length=32)
    officer: str = Field(default="Gloria", min_length=1, max_length=80)


@app.post("/auth/officer")
def auth_officer(body: OfficerAuthBody) -> dict:
    """PIN gate for Gloria. Empty OFFICER_PIN in .env → demo accepts any pin."""
    settings = get_settings()
    expected = (settings.officer_pin or "").strip()
    if expected and body.pin.strip() != expected:
        raise HTTPException(401, "invalid officer PIN")
    return {
        "ok": True,
        "officer": body.officer.strip() or settings.officer_name,
        "session": "demo" if not expected else "pin_ok",
    }


@app.post("/confirm-tokens")
def create_confirm_token(body: ConfirmTokenBody) -> dict:
    action = body.action.lower().strip()
    if action not in {"approve", "send_back", "review"}:
        raise HTTPException(400, "action must be approve | send_back | review")
    try:
        load_meta(body.application_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    row = issue_confirm_token(
        application_id=body.application_id,
        action=action,
        officer=body.officer.strip() or "Gloria",
    )
    return {
        "token": row.token,
        "application_id": row.application_id,
        "action": row.action,
        "expires_in_s": 120,
    }


@app.post("/applications/{application_id}/gloria-action")
def gloria_action(application_id: str, body: GloriaActionBody) -> dict:
    """Human-click lock: Approve / Send back / Flag — requires one-time confirm_token."""
    try:
        load_meta(application_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    officer = body.officer.strip() or "Gloria"
    action = body.action.lower().strip()
    try:
        if action == "approve":
            meta = approve_application(
                application_id, confirm_token=body.confirm_token, officer=officer
            )
            return {"meta": meta}
        if action == "send_back":
            return send_draft(
                application_id,
                confirm_token=body.confirm_token,
                officer=officer,
                draft_id=body.draft_id,
            )
        if action == "review":
            meta = mark_review(
                application_id, confirm_token=body.confirm_token, officer=officer
            )
            return {"meta": meta}
    except LockError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    raise HTTPException(400, "action must be approve | send_back | review")


@app.post("/demo/seed-case/{case_id}")
def seed_case(case_id: str) -> dict:
    """Load eval case docs → Llama extract → rules AuditReport (live facts when online)."""
    from app.drafts.drafter import attach_drafts, first_name_from_docs
    from app.extract.pipeline_extract import extract_application_docs
    from app.ingest.pipeline import seed_from_eval_case
    from app.models import DocType, Outcome
    from app.rules.checklist import load_checklist
    from app.rules.engine import run
    from app.rules.facts_from_case import facts_from_case
    from app.rules.facts_from_extractions import facts_from_extractions
    from app.storage.files import app_dir, load_meta, save_meta

    case_dir = _REPO / "eval" / "cases" / case_id
    if not (case_dir / "case.yaml").exists():
        raise HTTPException(404, f"unknown case: {case_id}")
    settings = get_settings()
    aid = seed_from_eval_case(case_dir)
    ingest = process_application(aid, settings=settings)
    extractions, llama_docs = extract_application_docs(aid, ingest, settings=settings)
    llama = {
        "provider": settings.extract_provider,
        "model": settings.extract_model,
        "demo_offline": settings.demo_offline,
        "docs": llama_docs,
    }

    # Offline fixtures are Jeff-shaped — keep case.yaml gold facts for reliable demos.
    # Live Ollama: audit from extracted fields (AI extracts, code decides).
    if settings.demo_offline:
        facts = facts_from_case(case_dir)
        facts_source = "case_yaml_offline"
    else:
        facts = facts_from_extractions(
            extractions,
            submission_date=date.fromisoformat(
                load_meta(aid, settings).get("submission_date") or "2026-11-16"
            ),
            application_id=aid,
        )
        # Thin extract → fall back so Gloria still gets a usable desk file
        if not (
            facts.has(DocType.bank_statement)
            or facts.has(DocType.flight_booking)
            or facts.has(DocType.application_form)
        ):
            facts = facts_from_case(case_dir)
            facts_source = "case_yaml_fallback"
            llama["fallback"] = True
        else:
            facts_source = "live_extract"

    checklist = load_checklist(_REPO / "checklists" / "fr-schengen-short-stay.yaml")
    audit = run(checklist, facts)
    attach_drafts(audit, applicant_first_name=first_name_from_docs(llama_docs))
    audit_json = audit.model_dump(mode="json")

    if audit.outcome == Outcome.SEND_BACK:
        human_status = "awaiting_gloria_send_back"
    elif audit.outcome == Outcome.NEEDS_GLORIA:
        human_status = "awaiting_gloria_review"
    else:
        human_status = "awaiting_gloria_approval"

    meta = load_meta(aid, settings)
    meta["status"] = human_status
    meta["outcome"] = audit.outcome.value
    meta["human_required"] = True
    meta["case_id"] = case_id
    meta["facts_source"] = facts_source
    save_meta(meta, settings)
    report = {
        "application_id": aid,
        "case_id": case_id,
        "facts_source": facts_source,
        "audit": audit_json,
        "human_required": True,
        "human_status": human_status,
        "ingest_report": ingest,
        "llama_extract": llama,
    }
    (app_dir(aid, settings) / "email_pipeline_report.json").write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )
    return {
        "id": aid,
        "case_id": case_id,
        "facts_source": facts_source,
        "llama_extract": llama,
        "ingest_report": ingest,
        "audit": audit_json,
        "human_status": human_status,
    }


@app.post("/email/inbox/read")
def read_email_inbox() -> dict[str, object]:
    """VISA + Llama-triaged emails → OCR/MRZ → Llama extract → TLS AuditReport."""
    try:
        return process_visa_inbox(settings=get_settings())  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=f"Email inbox pipeline failed: {exc}") from exc
