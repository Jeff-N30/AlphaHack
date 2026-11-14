"""VisaRef API — intake + preview/classify/MRZ slice."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from pydantic import BaseModel, Field

from app.api_applications import get_application_detail, list_applications, mark_gloria_action
from app.config import get_settings
from app.ingest.email_pipeline import process_visa_inbox
from app.ingest.email_watcher import watch_email_inbox
from app.ingest.pipeline import process_application
from app.ingest.render import allowed_suffix
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


class GloriaActionBody(BaseModel):
    action: str = Field(..., description="approve | send_back | review")
    officer: str = Field(default="Gloria", min_length=1, max_length=80)


@app.post("/applications/{application_id}/gloria-action")
def gloria_action(application_id: str, body: GloriaActionBody) -> dict:
    """Human-click lock (demo): Approve / Send back / Keep reviewing."""
    try:
        load_meta(application_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    try:
        meta = mark_gloria_action(
            application_id, action=body.action, officer=body.officer.strip() or "Gloria"
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"meta": meta}


def _demo_llama_extract(case_dir: Path) -> dict:
    """Run Llama (Ollama) field extract on case PDFs — shown on /demo for recording."""
    from app.config import Settings
    from app.extract.extract import (
        extract_application_form,
        extract_bank,
        extract_flight,
        extract_hotel,
        extract_insurance,
    )
    from app.ingest.render import read_preview

    settings = get_settings()
    # Prefer live/cache; if unset keys / offline flag, fixtures still return typed JSON for the UI
    docs_dir = case_dir / "docs"
    out: dict[str, object] = {
        "provider": settings.extract_provider,
        "model": settings.extract_model,
        "demo_offline": settings.demo_offline,
        "docs": {},
    }
    mapping = [
        ("flight_booking.pdf", "flight_booking", extract_flight),
        ("travel_insurance.pdf", "travel_insurance", extract_insurance),
        ("application_form.pdf", "application_form", extract_application_form),
        ("hotel_booking.pdf", "hotel_booking", extract_hotel),
        ("bank_statement.pdf", "bank_statement", extract_bank),
    ]
    for fname, key, fn in mapping:
        path = docs_dir / fname
        if not path.exists():
            continue
        try:
            prev = read_preview(path, max_pages=4)
            extracted = fn(prev.text, source=path, settings=settings)
            out["docs"][key] = extracted.model_dump(mode="json")  # type: ignore[index]
        except Exception as exc:  # noqa: BLE001 — demo UI must still render
            logger.warning("demo llama extract %s failed: %s", key, exc)
            # Fall back to offline fixture so the screen always shows Llama-shaped output
            offline = Settings(
                data_dir=settings.data_dir,
                checklist_dir=settings.checklist_dir,
                demo_offline=True,
                extract_provider="ollama",
                extract_model=settings.extract_model,
                prompt_version=settings.prompt_version + "+demo-fallback",
            )
            prev = read_preview(path, max_pages=4) if path.exists() else None
            text = prev.text if prev else "demo"
            extracted = fn(text, source=path if path.exists() else None, settings=offline)
            out["docs"][key] = extracted.model_dump(mode="json")  # type: ignore[index]
            out["fallback"] = True
    return out


@app.post("/demo/seed-case/{case_id}")
def seed_case(case_id: str) -> dict:
    """Load eval case docs → Llama extract → ingest → rules AuditReport."""
    from app.ingest.pipeline import seed_from_eval_case
    from app.models import Outcome
    from app.rules.checklist import load_checklist
    from app.rules.engine import run
    from app.rules.facts_from_case import facts_from_case
    from app.storage.files import app_dir, load_meta, save_meta

    case_dir = _REPO / "eval" / "cases" / case_id
    if not (case_dir / "case.yaml").exists():
        raise HTTPException(404, f"unknown case: {case_id}")
    aid = seed_from_eval_case(case_dir)
    llama = _demo_llama_extract(case_dir)
    ingest = process_application(aid)
    checklist = load_checklist(_REPO / "checklists" / "fr-schengen-short-stay.yaml")
    audit = run(checklist, facts_from_case(case_dir))
    audit_json = audit.model_dump(mode="json")

    if audit.outcome == Outcome.SEND_BACK:
        human_status = "awaiting_gloria_send_back"
    elif audit.outcome == Outcome.NEEDS_GLORIA:
        human_status = "awaiting_gloria_review"
    else:
        human_status = "awaiting_gloria_approval"

    settings = get_settings()
    meta = load_meta(aid, settings)
    meta["status"] = human_status
    meta["outcome"] = audit.outcome.value
    meta["human_required"] = True
    save_meta(meta, settings)
    report = {
        "application_id": aid,
        "case_id": case_id,
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
        "llama_extract": llama,
        "ingest_report": ingest,
        "audit": audit_json,
        "human_status": human_status,
    }


@app.get("/demo")
def demo_page():
    """Hackathon demo UI — run one eval case and show outcome."""
    html = (_REPO / "tools" / "demo.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.post("/email/inbox/read")
def read_email_inbox() -> dict[str, object]:
    """VISA emails → attachments → OCR/MRZ → Llama extract → TLS AuditReport."""
    try:
        return process_visa_inbox(settings=get_settings())  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=f"Email inbox pipeline failed: {exc}") from exc
