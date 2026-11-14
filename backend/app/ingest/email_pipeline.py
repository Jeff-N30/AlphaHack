"""Email → application → full audit (extract + rules) → Gloria queue."""
from __future__ import annotations

import json
import logging
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any

from app.audit_pipeline import audit_application
from app.config import Settings, get_settings
from app.ingest.email import SavedEmail, read_matching_emails
from app.ingest.render import allowed_suffix
from app.storage.files import create_application, load_meta, save_meta, store_upload

logger = logging.getLogger(__name__)


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
    """One VISA / Llama-triaged email → store + full audit."""
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

    report = audit_application(
        aid,
        settings=settings,
        extra_report={
            "email_uid": message.uid,
            "subject": message.subject,
            "sender": message.sender,
            "email_source": message.source,
            "files": saved,
        },
    )

    meta = load_meta(aid, settings)
    meta["email_uid"] = message.uid
    meta["email_source"] = message.source
    if message.person_name and message.person_name != "unknown":
        meta["triage_person_name"] = message.person_name
    save_meta(meta, settings)
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
    messages = [m for m in messages if m.source in {"subject_filter", "llama_triage"}]
    results = [
        process_email_message(m, settings=settings, submission_date=submission_date)
        for m in messages
    ]
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
