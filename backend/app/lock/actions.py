"""Human-click lock actions — the only callers of outbound/."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.lock.audit_log import append_audit_log
from app.lock.tokens import TokenError, consume_confirm_token
from app.models import DraftStatus
from app.outbound.copy import deliver_copy
from app.storage.files import app_dir, load_meta, save_meta


class LockError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def approve_application(
    application_id: str,
    *,
    confirm_token: str,
    officer: str = "Gloria",
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        consume_confirm_token(
            confirm_token, application_id=application_id, action="approve"
        )
    except TokenError as exc:
        raise LockError(str(exc), status_code=409 if exc.conflict else 400) from exc

    meta = load_meta(application_id, settings)
    meta["status"] = "approved_by_gloria"
    meta["human_action"] = f"Approved by {officer}"
    meta["human_required"] = False
    meta["last_officer"] = officer
    meta["approved_at"] = datetime.now(timezone.utc).isoformat()
    save_meta(meta, settings)
    append_audit_log(
        officer=officer,
        action="approve",
        application_id=application_id,
        body=None,
        settings=settings,
    )
    return meta


def send_draft(
    application_id: str,
    *,
    confirm_token: str,
    officer: str = "Gloria",
    draft_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Mark send-back + promote DRAFT → SENT via copy outbound (Gloria paste)."""
    settings = settings or get_settings()
    try:
        consume_confirm_token(
            confirm_token, application_id=application_id, action="send_back"
        )
    except TokenError as exc:
        raise LockError(str(exc), status_code=409 if exc.conflict else 400) from exc

    draft, report_path, report = _load_draft(application_id, draft_id, settings)
    body = draft.get("body") or ""
    delivery = deliver_copy(body=body, application_id=application_id, officer=officer)

    draft["status"] = DraftStatus.SENT.value
    draft["approved_by"] = officer
    draft["approved_at"] = datetime.now(timezone.utc).isoformat()
    drafts = (report.get("audit") or {}).get("drafts") or []
    for i, d in enumerate(drafts):
        if d.get("id") == draft.get("id"):
            drafts[i] = draft
            break
    if report.get("audit"):
        report["audit"]["drafts"] = drafts
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    meta = load_meta(application_id, settings)
    meta["status"] = "sent_back_by_gloria"
    meta["human_action"] = f"Send-back confirmed by {officer} (copy channel)"
    meta["human_required"] = False
    meta["last_officer"] = officer
    meta["last_delivery"] = delivery
    save_meta(meta, settings)
    append_audit_log(
        officer=officer,
        action="send_back",
        application_id=application_id,
        body=body,
        extra={"draft_id": draft.get("id"), "delivery": delivery},
        settings=settings,
    )
    return {"meta": meta, "draft": draft, "delivery": delivery}


def mark_review(
    application_id: str,
    *,
    confirm_token: str,
    officer: str = "Gloria",
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        consume_confirm_token(
            confirm_token, application_id=application_id, action="review"
        )
    except TokenError as exc:
        raise LockError(str(exc), status_code=409 if exc.conflict else 400) from exc

    meta = load_meta(application_id, settings)
    meta["status"] = "awaiting_gloria_review"
    meta["human_action"] = f"Marked for more review by {officer}"
    meta["human_required"] = True
    meta["last_officer"] = officer
    save_meta(meta, settings)
    append_audit_log(
        officer=officer,
        action="review",
        application_id=application_id,
        settings=settings,
    )
    return meta


def _load_draft(
    application_id: str,
    draft_id: str | None,
    settings: Settings,
) -> tuple[dict[str, Any], Any, dict[str, Any]]:
    root = app_dir(application_id, settings)
    report_path = root / "email_pipeline_report.json"
    if not report_path.exists():
        raise LockError("no pipeline report for application")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    drafts = (report.get("audit") or {}).get("drafts") or []
    if not drafts:
        # Minimal stub so Gloria can still confirm send-back without a draft body
        draft = {
            "id": draft_id or "stub",
            "application_id": application_id,
            "channel": "copy",
            "language": "en",
            "body": "Please send the missing or corrected documents for your visa file.",
            "rule_ids": [],
            "status": DraftStatus.DRAFT.value,
        }
        report.setdefault("audit", {})["drafts"] = [draft]
        return draft, report_path, report
    if draft_id:
        for d in drafts:
            if d.get("id") == draft_id:
                return d, report_path, report
        raise LockError(f"draft not found: {draft_id}")
    return drafts[0], report_path, report
