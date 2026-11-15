"""Human-click lock actions — the only callers of outbound/."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.lock.audit_log import append_audit_log
from app.lock.tokens import TokenError, consume_confirm_token
from app.models import DraftStatus
from app.outbound.deliver import DeliveryError, deliver_applicant_message
from app.storage.files import app_dir, load_meta, save_meta
from app.trace.recorder import record as trace_record
from app.trace.recorder import span as trace_span
from app.trace.recorder import start_run


class LockError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _delivery_audit(delivery: dict[str, Any]) -> dict[str, Any]:
    """Keep delivery outcome without retaining recipient-identifying fields."""
    return {
        key: value
        for key, value in delivery.items()
        if key not in {"to", "intended_to", "email_error"}
    }


def _applicant_email(
    meta: dict[str, Any],
    settings: Settings,
    override: str | None = None,
) -> str | None:
    if override and override.strip():
        return override.strip()
    for key in ("applicant_email", "email_sender", "sender"):
        raw = meta.get(key)
        if raw:
            return str(raw)
    return settings.demo_applicant_email or None


def _send_or_raise(
    *,
    body: str,
    application_id: str,
    officer: str,
    to_address: str | None,
    subject: str,
    settings: Settings,
) -> dict[str, Any]:
    with trace_span(
        "outbound:smtp",
        label="SMTP delivery",
        inputs={"subject": subject, "to": to_address, "body_chars": len(body)},
    ) as out:
        try:
            result = deliver_applicant_message(
                body=body,
                application_id=application_id,
                officer=officer,
                to_address=to_address,
                subject=subject,
                settings=settings,
            )
        except DeliveryError as exc:
            raise LockError(str(exc), status_code=400) from exc
        out["delivered"] = bool(result.get("delivered"))
        out["to"] = result.get("to")
        out["channel"] = result.get("channel")
        return result


def _mark_draft_sent(
    *,
    draft: dict[str, Any],
    report: dict[str, Any],
    report_path: Path,
    officer: str,
) -> None:
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


def _approve_application(
    application_id: str,
    *,
    confirm_token: str,
    officer: str = "Gloria",
    draft_id: str | None = None,
    to_email: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    with trace_span(
        "lock:confirm_token", label="Confirm token", inputs={"action": "approve", "officer": officer}
    ) as tok_out:
        try:
            consume_confirm_token(
                confirm_token, application_id=application_id, action="approve"
            )
        except TokenError as exc:
            raise LockError(str(exc), status_code=409 if exc.conflict else 400) from exc
        tok_out["consumed"] = True

    meta = load_meta(application_id, settings)
    draft, report_path, report = _load_draft(application_id, draft_id, settings)
    body = draft.get("body") or ""
    if not body.strip():
        raise LockError("no draft body to email the applicant")

    to = _applicant_email(meta, settings, to_email)
    delivery = _send_or_raise(
        body=body,
        application_id=application_id,
        officer=officer,
        to_address=to,
        subject="Your visa file — next steps",
        settings=settings,
    )
    _mark_draft_sent(
        draft=draft, report=report, report_path=report_path, officer=officer
    )
    if to:
        meta["applicant_email"] = to

    meta["status"] = "approved_by_gloria"
    meta["human_action"] = f"Marked ready by {officer} (email sent)"
    meta["human_required"] = False
    meta["last_officer"] = officer
    meta["approved_at"] = datetime.now(timezone.utc).isoformat()
    meta["last_delivery"] = delivery
    save_meta(meta, settings)
    with trace_span("store:audit_log", label="Audit log", inputs={"action": "approve"}):
        append_audit_log(
            officer=officer,
            action="approve",
            application_id=application_id,
            body=body,
            extra={"delivery": _delivery_audit(delivery), "draft_id": draft.get("id")},
            settings=settings,
        )
    return {"meta": meta, "draft": draft, "delivery": delivery}


def _send_draft(
    application_id: str,
    *,
    confirm_token: str,
    officer: str = "Gloria",
    draft_id: str | None = None,
    to_email: str | None = None,
    body_override: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Mark send-back + SMTP the draft to the correspondent.

    body_override: when Gloria fails a look-item on an otherwise-clean file,
    the desk sends her composed send-back text (still audited via sha256).
    """
    settings = settings or get_settings()
    with trace_span(
        "lock:confirm_token", label="Confirm token", inputs={"action": "send_back", "officer": officer}
    ) as tok_out:
        try:
            consume_confirm_token(
                confirm_token, application_id=application_id, action="send_back"
            )
        except TokenError as exc:
            raise LockError(str(exc), status_code=409 if exc.conflict else 400) from exc
        tok_out["consumed"] = True

    draft, report_path, report = _load_draft(application_id, draft_id, settings)
    override = (body_override or "").strip()
    if override:
        draft["body"] = override
        # Officer-authored look rejects — not auto rule ids
        draft["rule_ids"] = list(draft.get("rule_ids") or []) + ["HUMAN.LOOK_REJECT"]
    body = draft.get("body") or ""
    if not body.strip():
        raise LockError("no draft body to email the applicant")
    meta = load_meta(application_id, settings)
    to = _applicant_email(meta, settings, to_email)
    delivery = _send_or_raise(
        body=body,
        application_id=application_id,
        officer=officer,
        to_address=to,
        subject="Your visa file — documents needed",
        settings=settings,
    )
    _mark_draft_sent(
        draft=draft, report=report, report_path=report_path, officer=officer
    )
    if to:
        meta["applicant_email"] = to

    meta["status"] = "sent_back_by_gloria"
    meta["human_action"] = f"Send-back emailed by {officer}"
    meta["human_required"] = False
    meta["last_officer"] = officer
    meta["last_delivery"] = delivery
    save_meta(meta, settings)
    with trace_span("store:audit_log", label="Audit log", inputs={"action": "send_back"}):
        append_audit_log(
            officer=officer,
            action="send_back",
            application_id=application_id,
            body=body,
            extra={"draft_id": draft.get("id"), "delivery": _delivery_audit(delivery)},
            settings=settings,
        )
    return {"meta": meta, "draft": draft, "delivery": delivery}


def _mark_review(
    application_id: str,
    *,
    confirm_token: str,
    officer: str = "Gloria",
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    with trace_span(
        "lock:confirm_token", label="Confirm token", inputs={"action": "review", "officer": officer}
    ) as tok_out:
        try:
            consume_confirm_token(
                confirm_token, application_id=application_id, action="review"
            )
        except TokenError as exc:
            raise LockError(str(exc), status_code=409 if exc.conflict else 400) from exc
        tok_out["consumed"] = True

    meta = load_meta(application_id, settings)
    meta["status"] = "awaiting_gloria_review"
    meta["human_action"] = f"Marked for more review by {officer}"
    meta["human_required"] = True
    meta["last_officer"] = officer
    save_meta(meta, settings)
    with trace_span("store:audit_log", label="Audit log", inputs={"action": "review"}):
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
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
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
            "channel": "email",
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


def approve_application(
    application_id: str,
    *,
    confirm_token: str,
    officer: str = "Gloria",
    draft_id: str | None = None,
    to_email: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Traced human-lock action (events appended to execution_trace.json)."""
    with start_run(application_id, kind="lock", settings=settings):
        with trace_span("lock:approve", source="gate:human", label="Approve", inputs={"officer": officer}) as out:
            result = _approve_application(application_id, confirm_token=confirm_token, officer=officer, draft_id=draft_id, to_email=to_email, settings=settings)
            out["officer"] = officer
        trace_record(
            "gate:human",
            label="Human gate",
            status="resolved",
            outputs={"action": "approve", "officer": officer},
            source="lock:approve",
        )
        return result


def send_draft(
    application_id: str,
    *,
    confirm_token: str,
    officer: str = "Gloria",
    draft_id: str | None = None,
    to_email: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Traced human-lock action (events appended to execution_trace.json)."""
    with start_run(application_id, kind="lock", settings=settings):
        with trace_span("lock:send_back", source="gate:human", label="Send back", inputs={"officer": officer}) as out:
            result = _send_draft(application_id, confirm_token=confirm_token, officer=officer, draft_id=draft_id, to_email=to_email, settings=settings)
            out["officer"] = officer
        trace_record(
            "gate:human",
            label="Human gate",
            status="resolved",
            outputs={"action": "send_back", "officer": officer},
            source="lock:send_back",
        )
        return result


def mark_review(
    application_id: str,
    *,
    confirm_token: str,
    officer: str = "Gloria",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Traced human-lock action (events appended to execution_trace.json)."""
    with start_run(application_id, kind="lock", settings=settings):
        with trace_span("lock:review", source="gate:human", label="Flag for review", inputs={"officer": officer}) as out:
            result = _mark_review(application_id, confirm_token=confirm_token, officer=officer, settings=settings)
            out["officer"] = officer
        trace_record(
            "gate:human",
            label="Human gate",
            status="resolved",
            outputs={"action": "review", "officer": officer},
            source="lock:review",
        )
        return result
