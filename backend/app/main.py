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

from app.config import get_settings
from app.ingest.email import read_matching_emails
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


@app.get("/applications/{application_id}")
def get_application(application_id: str) -> dict:
    settings = get_settings()
    try:
        meta = load_meta(application_id, settings)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    report_path = settings.data_dir / "applications" / application_id / "ingest_report.json"
    report = None
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return {"meta": meta, "ingest_report": report}


def _demo_llama_extract(case_dir: Path) -> dict:
    """Run Llama (Ollama) field extract on case PDFs — shown on /demo for recording."""
    from app.config import Settings
    from app.extract.extract import (
        extract_application_form,
        extract_flight,
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
    from app.rules.checklist import load_checklist
    from app.rules.engine import run
    from app.rules.facts_from_case import facts_from_case

    case_dir = _REPO / "eval" / "cases" / case_id
    if not (case_dir / "case.yaml").exists():
        raise HTTPException(404, f"unknown case: {case_id}")
    aid = seed_from_eval_case(case_dir)
    llama = _demo_llama_extract(case_dir)
    ingest = process_application(aid)
    checklist = load_checklist(_REPO / "checklists" / "fr-schengen-short-stay.yaml")
    audit = run(checklist, facts_from_case(case_dir))
    return {
        "id": aid,
        "case_id": case_id,
        "llama_extract": llama,
        "ingest_report": ingest,
        "audit": audit.model_dump(mode="json"),
    }


@app.get("/demo")
def demo_page():
    """Hackathon demo UI — run one eval case and show outcome."""
    html = (_REPO / "tools" / "demo.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.post("/email/inbox/read")
def read_email_inbox() -> dict[str, object]:
    """Read configured matching emails and save their attachments locally."""
    try:
        messages = read_matching_emails(get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=f"Email inbox read failed: {exc}") from exc
    return {
        "count": len(messages),
        "subject_filter": get_settings().email_subject_filter,
        "messages": [
            {
                "uid": message.uid,
                "subject": message.subject,
                "sender": message.sender,
                "received_at": message.received_at,
                "files": message.files,
            }
            for message in messages
        ],
    }
