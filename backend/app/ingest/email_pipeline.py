"""Email → application → OCR/MRZ → Llama extract → TLS rules (end-to-end)."""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.extract.extract import extract_by_type
from app.ingest.email import SavedEmail, read_matching_emails
from app.ingest.pipeline import process_application
from app.ingest.render import allowed_suffix, read_preview
from app.models import DocType, Extraction, MRZ, Outcome
from app.rules.checklist import load_checklist
from app.rules.engine import run
from app.rules.facts_from_extractions import facts_from_extractions, passport_from_mrz
from app.storage.files import app_dir, create_application, load_meta, save_meta, store_upload

logger = logging.getLogger(__name__)

_REPO = Path(__file__).resolve().parents[3]
_CHECKLIST = _REPO / "checklists" / "fr-schengen-short-stay.yaml"

_EXTRACTABLE = {
    DocType.flight_booking,
    DocType.travel_insurance,
    DocType.application_form,
}


def _attachment_paths(message: SavedEmail) -> list[Path]:
    out: list[Path] = []
    for f in message.files:
        path = Path(f)
        if path.name in {"message.eml", "body.txt"}:
            continue
        if allowed_suffix(path):
            out.append(path)
    return out


def process_email_message(
    message: SavedEmail,
    *,
    settings: Settings | None = None,
    submission_date: date | None = None,
    checklist_id: str = "fr-schengen-short-stay",
) -> dict[str, Any]:
    """One VISA email → ingest + Llama fields + AuditReport."""
    settings = settings or get_settings()
    sub = submission_date or date.today()
    paths = _attachment_paths(message)
    meta = create_application(
        checklist_id=checklist_id,
        submission_date=sub,
        settings=settings,
    )
    aid = meta["id"]
    saved: list[str] = []
    for path in paths:
        store_upload(aid, path.name, path.read_bytes(), settings=settings)
        saved.append(path.name)

    ingest = process_application(aid, settings=settings)
    extractions: list[Extraction] = []
    llama_docs: dict[str, Any] = {}

    # Passport from MRZ (code)
    for entry in ingest.get("files") or []:
        mrz_raw = entry.get("mrz")
        if not mrz_raw:
            continue
        try:
            mrz = MRZ.model_validate(mrz_raw)
            extractions.append(passport_from_mrz(mrz))
        except Exception as exc:  # noqa: BLE001
            logger.warning("bad MRZ on %s: %s", entry.get("file"), exc)

    # Llama extract for classified / known doc types
    raw = app_dir(aid, settings) / "raw"
    for entry in ingest.get("files") or []:
        if entry.get("rejected"):
            continue
        fname = entry.get("file") or ""
        path = raw / fname
        if not path.exists():
            continue
        cls = (entry.get("classification") or {}).get("doc_type")
        try:
            dtype = DocType(cls) if cls else DocType.unknown
        except ValueError:
            dtype = DocType.unknown
        if dtype not in _EXTRACTABLE:
            from app.extract.classify import classify_document

            prev = read_preview(path, max_pages=4)
            dtype = classify_document(prev.text, filename=fname, settings=settings).doc_type
        if dtype not in _EXTRACTABLE:
            continue
        try:
            prev = read_preview(path, max_pages=6)
            ex = extract_by_type(dtype, prev.text, source=path, settings=settings)
            extractions.append(ex)
            llama_docs[dtype.value] = ex.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            logger.warning("extract failed %s: %s", fname, exc)

    facts = facts_from_extractions(
        extractions,
        submission_date=sub,
        application_id=aid,
    )
    checklist = load_checklist(_CHECKLIST)
    audit = run(checklist, facts)

    # Human lock: pipeline never Approve/Send — only mark what Gloria must do
    if audit.outcome == Outcome.SEND_BACK:
        human_status = "awaiting_gloria_send_back"
        human_action = "Gloria: review FAILs and send the request draft (not auto-sent)."
    elif audit.outcome == Outcome.NEEDS_GLORIA:
        human_status = "awaiting_gloria_review"
        human_action = "Gloria: resolve NEEDS_HUMAN flags (photo/pages/name/etc)."
    else:
        human_status = "awaiting_gloria_approval"
        human_action = "Gloria: confirm Approve (human-click lock). Pipeline cannot approve."

    meta = load_meta(aid, settings)
    meta["status"] = human_status
    meta["outcome"] = audit.outcome.value
    meta["human_required"] = True
    meta["human_action"] = human_action
    meta["email_uid"] = message.uid
    save_meta(meta, settings)

    report = {
        "email_uid": message.uid,
        "subject": message.subject,
        "sender": message.sender,
        "application_id": aid,
        "files": saved,
        "human_required": True,
        "human_status": human_status,
        "human_action": human_action,
        "ingest_report": ingest,
        "llama_extract": {
            "provider": settings.extract_provider,
            "model": settings.extract_model,
            "demo_offline": settings.demo_offline,
            "docs": llama_docs,
        },
        "audit": audit.model_dump(mode="json"),
    }
    out_path = app_dir(aid, settings) / "email_pipeline_report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        f"VISA app {aid}: outcome={audit.outcome.value} → {human_status} (Gloria must act)",
        flush=True,
    )
    return report


def process_visa_inbox(
    *,
    settings: Settings | None = None,
    submission_date: date | None = None,
) -> dict[str, Any]:
    """Poll IMAP for VISA mails and run the full pipeline on each."""
    settings = settings or get_settings()
    messages = read_matching_emails(settings)
    results = [
        process_email_message(m, settings=settings, submission_date=submission_date) for m in messages
    ]
    return {
        "count": len(results),
        "subject_filter": settings.email_subject_filter,
        "results": results,
    }
