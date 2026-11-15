"""VisaRef API — intake + Gloria desk + human lock."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from pydantic import BaseModel, Field

from app.api_applications import (
    get_application_detail,
    list_applications,
    resolve_application_file,
)
from app.audit_pipeline import audit_application
from app.config import get_settings
from app.ingest.email_pipeline import process_visa_inbox
from app.ingest.email_watcher import watch_email_inbox
from app.ingest.render import allowed_suffix
from app.lock.actions import LockError, approve_application, mark_review, send_draft
from app.lock.audit_log import append_audit_log
from app.lock.tokens import issue_confirm_token
from app.storage.files import create_application, load_meta, redact_application, store_upload

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
    """Full path: ingest → Llama extract → rules → draft → Gloria queue."""
    try:
        load_meta(application_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    return audit_application(application_id)


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


_MEDIA = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


@app.get("/applications/{application_id}/files/{filename}")
def get_application_file(application_id: str, filename: str):
    """Original document (PDF / PNG / JPEG) for Gloria's desk."""
    try:
        load_meta(application_id)
        path = resolve_application_file(application_id, filename)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc) or "file not found") from exc
    media = _MEDIA.get(path.suffix.lower(), "application/octet-stream")
    # inline = show in browser/desk; attachment would force download
    return FileResponse(
        path,
        media_type=media,
        filename=path.name,
        content_disposition_type="inline",
    )


@app.get("/applications/{application_id}/files/{filename}/page/{page}")
def get_application_file_page(application_id: str, filename: str, page: int = 1):
    """Raster page preview (PNG) — works for scanned PDFs and passport images."""
    from app.ingest.render import render_page_png

    if page < 1:
        raise HTTPException(400, "page must be >= 1")
    try:
        load_meta(application_id)
        path = resolve_application_file(application_id, filename)
        png = render_page_png(path, page=page)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc) or "file not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"could not render page: {exc}") from exc
    return Response(content=png, media_type="image/png")


class ConfirmTokenBody(BaseModel):
    application_id: str
    action: str = Field(..., description="approve | send_back | review")
    officer: str = Field(default="Gloria", min_length=1, max_length=80)


class GloriaActionBody(BaseModel):
    action: str = Field(..., description="approve | send_back | review")
    officer: str = Field(default="Gloria", min_length=1, max_length=80)
    confirm_token: str = Field(..., min_length=8)
    draft_id: str | None = None
    to_email: str | None = Field(
        default=None, description="Correspondent email — required to SMTP send"
    )


class OfficerAuthBody(BaseModel):
    pin: str = Field(..., min_length=1, max_length=32)
    officer: str = Field(default="Gloria", min_length=1, max_length=80)


@app.post("/auth/officer")
def auth_officer(body: OfficerAuthBody) -> dict:
    """PIN gate for Gloria. Empty OFFICER_PIN in .env accepts any pin for local demo."""
    settings = get_settings()
    expected = (settings.officer_pin or "").strip()
    if expected and body.pin.strip() != expected:
        raise HTTPException(401, "invalid officer PIN")
    return {
        "ok": True,
        "officer": body.officer.strip() or settings.officer_name,
        "session": "demo" if not expected else "pin_ok",
    }


class RedactBody(BaseModel):
    confirm: bool = Field(..., description="Must be true to delete sensitive data")


@app.post("/applications/{application_id}/redact")
def redact_applicant_data(
    application_id: str,
    body: RedactBody,
) -> dict:
    """Delete personal documents/details after approval, retaining the decision record."""
    if not body.confirm:
        raise HTTPException(400, "confirm must be true")
    try:
        meta = load_meta(application_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    if meta.get("sensitive_data_redacted"):
        return {"meta": meta, "deleted_files": 0, "deleted_database_rows": 0}
    if meta.get("status") != "approved_by_gloria":
        raise HTTPException(409, "sensitive data can only be redacted after approval")
    try:
        result = redact_application(
            application_id,
            officer="Gloria",
            settings=get_settings(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    append_audit_log(
        officer="Gloria",
        action="redact_sensitive_data",
        application_id=application_id,
        settings=get_settings(),
        extra={
            "deleted_files": result["deleted_files"],
            "deleted_database_rows": result["deleted_database_rows"],
        },
    )
    return result


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
def gloria_action(
    application_id: str,
    body: GloriaActionBody,
) -> dict:
    """Human-click lock: Approve / Send back / Flag — requires one-time confirm_token."""
    try:
        load_meta(application_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    officer = body.officer.strip() or "Gloria"
    action = body.action.lower().strip()
    try:
        if action == "approve":
            return approve_application(
                application_id,
                confirm_token=body.confirm_token,
                officer=officer,
                draft_id=body.draft_id,
                to_email=body.to_email,
            )
        if action == "send_back":
            return send_draft(
                application_id,
                confirm_token=body.confirm_token,
                officer=officer,
                draft_id=body.draft_id,
                to_email=body.to_email,
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
    """Load eval case docs → full audit (live extract; case.yaml when offline)."""
    from app.ingest.pipeline import seed_from_eval_case
    from app.rules.facts_from_case import facts_from_case

    case_dir = _REPO / "eval" / "cases" / case_id
    if not (case_dir / "case.yaml").exists():
        raise HTTPException(404, f"unknown case: {case_id}")
    settings = get_settings()
    aid = seed_from_eval_case(case_dir, settings=settings)

    # Offline fixtures are Jeff-shaped — gold case.yaml keeps demo PASS/FAIL reliable.
    if settings.demo_offline:
        report = audit_application(
            aid,
            settings=settings,
            facts=facts_from_case(case_dir),
            facts_source="case_yaml_offline",
            case_id=case_id,
        )
    else:
        report = audit_application(aid, settings=settings, case_id=case_id)
        if report.get("facts_source") == "live_extract_thin":
            report = audit_application(
                aid,
                settings=settings,
                facts=facts_from_case(case_dir),
                facts_source="case_yaml_fallback",
                case_id=case_id,
            )
            report.setdefault("llama_extract", {})["fallback"] = True

    return {
        "id": aid,
        "case_id": case_id,
        "facts_source": report.get("facts_source"),
        "llama_extract": report.get("llama_extract"),
        "ingest_report": report.get("ingest_report"),
        "audit": report.get("audit"),
        "human_status": report.get("human_status"),
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
