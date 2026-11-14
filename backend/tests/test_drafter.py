"""Send-back draft from FAIL results (template, DRAFT only)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.drafts.drafter import attach_drafts, draft_send_back
from app.models import AuditReport, CheckResult, Outcome, Status


def _audit(*results: CheckResult) -> AuditReport:
    return AuditReport(
        application_id="app-1",
        checklist_id="fr-schengen-short-stay",
        checklist_version="1",
        submission_date=date(2026, 11, 16),
        results=list(results),
        skipped_rules=[],
        outcome=Outcome.SEND_BACK,
        escalations=0,
        drafts=[],
        cost=[],
        total_usd=0.0,
        created_at=datetime.now(timezone.utc),
    )


def test_draft_from_request_fails() -> None:
    audit = _audit(
        CheckResult(
            rule_id="BANK.SUFFICIENT_FUNDS",
            status=Status.FAIL,
            message="Closing balance too low for the stay.",
            on_fail="request",
        )
    )
    draft = draft_send_back(audit, applicant_first_name="Karim")
    assert draft is not None
    assert draft.status.value == "DRAFT"
    assert "Closing balance too low" in draft.body
    assert "Karim" in draft.body
    assert "refused" not in draft.body.lower()


def test_attach_drafts_skips_when_no_request_fails() -> None:
    audit = _audit(
        CheckResult(
            rule_id="PHOTO.QUALITY",
            status=Status.NEEDS_HUMAN,
            message="Check photo",
            mode="manual",
        )
    )
    attach_drafts(audit)
    assert audit.drafts == []


def test_attach_drafts_ready_on_clean_file() -> None:
    audit = _audit()
    audit.outcome = Outcome.READY_FOR_APPROVAL
    attach_drafts(audit, applicant_first_name="Karim")
    assert len(audit.drafts) == 1
    assert audit.drafts[0].status.value == "DRAFT"
    assert "Karim" in audit.drafts[0].body
    assert "complete" in audit.drafts[0].body.lower()
    assert "approved" not in audit.drafts[0].body.lower()
