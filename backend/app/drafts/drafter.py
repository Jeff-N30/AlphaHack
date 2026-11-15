"""Build ApplicantMessageDraft from FAIL results — wording only, never verdicts."""
from __future__ import annotations

import re
import uuid
from typing import Any

from app.config import Settings, get_settings
from app.models import ApplicantMessageDraft, AuditReport, DraftStatus, Status

_FORBIDDEN = re.compile(r"\b(refused|rejected|approved|LBP)\b", re.I)


def draft_send_back(
    audit: AuditReport,
    *,
    applicant_first_name: str = "Applicant",
    language: str = "en",
    agency_name: str = "VisaRef Agency",
    officer_name: str | None = None,
    appointment_date: str | None = None,
    settings: Settings | None = None,
) -> ApplicantMessageDraft | None:
    """Create DRAFT for on_fail=request FAILs. Returns None if nothing to request."""
    settings = settings or get_settings()
    officer = officer_name or settings.officer_name
    issues = _request_issues(audit)
    if not issues:
        return None
    body = _template_body(
        first_name=applicant_first_name or "Applicant",
        language=language,
        agency_name=agency_name,
        officer_name=officer,
        appointment_date=appointment_date,
        issues=issues,
    )
    body = _sanitize(body, issues)
    return ApplicantMessageDraft(
        id=str(uuid.uuid4()),
        application_id=audit.application_id,
        channel="email",
        language=_lang(language),
        body=body,
        rule_ids=[i["rule_id"] for i in issues],
        status=DraftStatus.DRAFT,
    )


def draft_ready(
    audit: AuditReport,
    *,
    applicant_first_name: str = "Applicant",
    language: str = "en",
    agency_name: str = "VisaRef Agency",
    officer_name: str | None = None,
    settings: Settings | None = None,
) -> ApplicantMessageDraft:
    """DRAFT when file is ready for Gloria to take to TLS (never says approved/refused)."""
    settings = settings or get_settings()
    officer = officer_name or settings.officer_name
    first = applicant_first_name or "Applicant"
    if language.startswith("fr"):
        body = (
            f"Bonjour {first},\n\n"
            "Votre dossier visa est complet côté documents. "
            "Nous le présenterons à TLScontact pour la suite du rendez-vous.\n\n"
            "Merci,\n"
            f"{officer} – {agency_name}"
        )
    elif language.startswith("ar"):
        body = (
            f"مرحبا {first}،\n\n"
            "ملف التأشيرة مكتمل من جهة المستندات. "
            "سنتابعه لدى TLScontact لموعدكم.\n\n"
            "شكراً،\n"
            f"{officer} – {agency_name}"
        )
    else:
        body = (
            f"Hello {first},\n\n"
            "Your visa document pack looks complete on our side. "
            "We will take the file to TLScontact for your appointment next steps.\n\n"
            "Thank you,\n"
            f"{officer} – {agency_name}"
        )
    body = _FORBIDDEN.sub("[omitted]", body)
    return ApplicantMessageDraft(
        id=str(uuid.uuid4()),
        application_id=audit.application_id,
        channel="email",
        language=_lang(language),
        body=body,
        rule_ids=[],
        status=DraftStatus.DRAFT,
    )


def attach_drafts(audit: AuditReport, *, applicant_first_name: str = "Applicant") -> AuditReport:
    """Attach send-back draft on FAIL requests, or ready-for-TLS draft when clean.

    NEEDS_GLORIA (look-items only) also gets a ready draft so Vera can Approve & email
    after she checkmarks the eye items — previously only READY_FOR_APPROVAL got a body,
    which left Approve permanently disabled.
    """
    from app.models import Outcome

    if audit.outcome == Outcome.SEND_BACK:
        draft = draft_send_back(audit, applicant_first_name=applicant_first_name)
        if draft:
            draft.channel = "email"  # type: ignore[assignment]
            audit.drafts = [draft]
        return audit
    if audit.outcome in (Outcome.READY_FOR_APPROVAL, Outcome.NEEDS_GLORIA):
        audit.drafts = [draft_ready(audit, applicant_first_name=applicant_first_name)]
    return audit


def _request_issues(audit: AuditReport) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for r in audit.results:
        if r.status != Status.FAIL:
            continue
        if r.on_fail == "flag":
            continue
        out.append(
            {
                "rule_id": r.rule_id,
                "problem": r.message,
                "needed": r.message,
            }
        )
    return out


def _lang(language: str) -> str:
    if language.startswith("ar"):
        return "ar-LB"
    if language.startswith("fr"):
        return "fr"
    return "en"


def _template_body(
    *,
    first_name: str,
    language: str,
    agency_name: str,
    officer_name: str,
    appointment_date: str | None,
    issues: list[dict[str, str]],
) -> str:
    lines = [f"Hello {first_name},", ""]
    if language.startswith("fr"):
        lines = [f"Bonjour {first_name},", ""]
        lines.append(
            "Nous avons vérifié votre dossier visa et avons besoin des documents suivants :"
        )
    elif language.startswith("ar"):
        lines = [f"مرحبا {first_name}،", ""]
        lines.append("راجعنا ملف التأشيرة ونحتاج المستندات التالية:")
    else:
        lines.append(
            "We reviewed your visa file and need the following before we can continue:"
        )
    lines.append("")
    for i, issue in enumerate(issues, start=1):
        lines.append(f"{i}. {issue['needed']}")
    if appointment_date:
        lines.append("")
        lines.append(f"Appointment date on file: {appointment_date}.")
    lines.append("")
    lines.append("Thank you,")
    lines.append(f"{officer_name} – {agency_name}")
    return "\n".join(lines)


def _sanitize(body: str, issues: list[dict[str, str]]) -> str:
    cleaned = _FORBIDDEN.sub("[omitted]", body)
    # Ensure each issue message fragment appears (deterministic template already does)
    for issue in issues:
        snippet = issue["needed"][:40]
        if snippet and snippet not in cleaned:
            cleaned = cleaned.rstrip() + f"\n- {issue['needed']}"
    return cleaned


def first_name_from_docs(llama_docs: dict[str, Any] | None) -> str:
    docs = llama_docs or {}
    form = docs.get("application_form") or {}
    given = form.get("given_names")
    if given:
        return str(given).split()[0]
    bank = docs.get("bank_statement") or {}
    if bank.get("account_holder"):
        return str(bank["account_holder"]).split()[0]
    emp = docs.get("employment_letter") or {}
    if emp.get("employee_name"):
        return str(emp["employee_name"]).split()[0]
    return "Applicant"
