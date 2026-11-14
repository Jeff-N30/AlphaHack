"""Email → application → OCR/MRZ → Llama extract → TLS rules (end-to-end)."""
from __future__ import annotations

import json
import logging
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.drafts.drafter import attach_drafts, first_name_from_docs
from app.extract.pipeline_extract import extract_application_docs
from app.ingest.email import SavedEmail, read_matching_emails
from app.ingest.pipeline import process_application
from app.ingest.render import allowed_suffix
from app.models import Outcome
from app.rules.checklist import load_checklist
from app.rules.engine import run
from app.rules.facts_from_extractions import facts_from_extractions
from app.storage.files import app_dir, create_application, load_meta, save_meta, store_upload

logger = logging.getLogger(__name__)

_REPO = Path(__file__).resolve().parents[3]
_CHECKLIST = _REPO / "checklists" / "fr-schengen-short-stay.yaml"


def _attachment_paths(message: SavedEmail) -> list[Path]:
    out: list[Path] = []
    for f in message.files:
        path = Path(f)
        if path.name in {"message.eml", "body.txt", "triage.json"}:
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
    """One VISA / Llama-triaged email → ingest + Llama fields + AuditReport."""
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
    extractions, llama_docs = extract_application_docs(aid, ingest, settings=settings)

    facts = facts_from_extractions(
        extractions,
        submission_date=sub,
        application_id=aid,
    )
    checklist = load_checklist(_CHECKLIST)
    audit = run(checklist, facts)
    attach_drafts(audit, applicant_first_name=first_name_from_docs(llama_docs))

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
    meta["email_source"] = message.source
    if message.person_name and message.person_name != "unknown":
        meta["triage_person_name"] = message.person_name
    save_meta(meta, settings)

    report = {
        "email_uid": message.uid,
        "subject": message.subject,
        "sender": message.sender,
        "email_source": message.source,
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
        f"VISA app {aid}: outcome={audit.outcome.value} → {human_status} "
        f"(source={message.source}; Gloria must act)",
        flush=True,
    )
    return report


def process_visa_inbox(
    *,
    settings: Settings | None = None,
    submission_date: date | None = None,
    started_after: datetime | None = None,
    max_messages: int | None = None,
) -> dict[str, Any]:
    """Poll IMAP for VISA + Llama-triaged mails and run the full pipeline on each."""
    settings = settings or get_settings()
    messages = read_matching_emails(
        settings,
        started_after=started_after,
        max_messages=max_messages,
    )
    # subject_filter (VISA in subject) + llama_triage (empty/other subject, related)
    messages = [
        m
        for m in messages
        if m.source in {"subject_filter", "llama_triage"}
    ]
    results = [
        process_email_message(m, settings=settings, submission_date=submission_date)
        for m in messages
    ]
    # Also promote any folders already sitting in needs_review/
    promoted = promote_needs_review(settings=settings, submission_date=submission_date)
    return {
        "count": len(results) + int(promoted.get("count") or 0),
        "subject_filter": settings.email_subject_filter,
        "imap_results": results,
        "needs_review_promoted": promoted,
        "results": results + list(promoted.get("results") or []),
    }


def promote_needs_review(
    *,
    settings: Settings | None = None,
    submission_date: date | None = None,
) -> dict[str, Any]:
    """Turn email_inbox/needs_review/* folders into Gloria queue applications."""
    settings = settings or get_settings()
    review_root = settings.data_dir / "email_inbox" / "needs_review"
    if not review_root.exists():
        return {"count": 0, "results": []}
    results: list[dict[str, Any]] = []
    for folder in sorted(review_root.iterdir()):
        if not folder.is_dir():
            continue
        marker = folder / ".promoted.json"
        if marker.exists():
            continue
        files = tuple(
            str(p)
            for p in sorted(folder.iterdir())
            if p.is_file() and p.name not in {".promoted.json"}
        )
        if not any(allowed_suffix(Path(f)) for f in files):
            continue
        uid = folder.name.rsplit("_", 1)[-1] if "_" in folder.name else folder.name
        message = SavedEmail(
            uid=f"needs_review:{uid}",
            subject="(needs_review)",
            sender="",
            received_at="",
            files=files,
            person_name=folder.name,
            source="llama_triage",
        )
        try:
            report = process_email_message(
                message, settings=settings, submission_date=submission_date
            )
            marker.write_text(
                json.dumps({"application_id": report.get("application_id")}, indent=2),
                encoding="utf-8",
            )
            results.append(report)
        except Exception as exc:  # noqa: BLE001
            logger.warning("promote needs_review %s failed: %s", folder.name, exc)
    return {"count": len(results), "results": results}
