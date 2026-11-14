"""Full Gloria path: ingest → Llama extract → rules → DRAFT → queue status.

Used by POST /applications/{id}/run, email inbox, and demo seed.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.drafts.drafter import attach_drafts, first_name_from_docs
from app.extract.pipeline_extract import extract_application_docs
from app.ingest.pipeline import process_application
from app.models import DocType, Outcome
from app.rules.checklist import load_checklist
from app.rules.context import Facts
from app.rules.engine import run
from app.rules.facts_from_extractions import facts_from_extractions
from app.storage.files import app_dir, load_meta, save_meta

logger = logging.getLogger(__name__)

_REPO = Path(__file__).resolve().parents[2]
_CHECKLIST = _REPO / "checklists" / "fr-schengen-short-stay.yaml"


def _human_status(outcome: Outcome) -> tuple[str, str]:
    if outcome == Outcome.SEND_BACK:
        return (
            "awaiting_gloria_send_back",
            "Gloria: review FAILs and send the request draft (not auto-sent).",
        )
    if outcome == Outcome.NEEDS_GLORIA:
        return (
            "awaiting_gloria_review",
            "Gloria: resolve NEEDS_HUMAN flags (photo/pages/name/etc).",
        )
    return (
        "awaiting_gloria_approval",
        "Gloria: confirm Approve (human-click lock). Pipeline cannot approve.",
    )


def audit_application(
    application_id: str,
    *,
    settings: Settings | None = None,
    facts: Facts | None = None,
    facts_source: str = "live_extract",
    case_id: str | None = None,
    extra_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ingest (if needed) + extract + rules + draft. Returns desk report dict."""
    settings = settings or get_settings()
    meta = load_meta(application_id, settings)
    sub = date.fromisoformat(str(meta.get("submission_date") or date.today().isoformat()))

    ingest = process_application(application_id, settings=settings)
    extractions, llama_docs = extract_application_docs(
        application_id, ingest, settings=settings
    )
    llama = {
        "provider": settings.extract_provider,
        "model": settings.extract_model,
        "demo_offline": settings.demo_offline,
        "docs": llama_docs,
    }

    used_source = facts_source
    if facts is None:
        facts = facts_from_extractions(
            extractions,
            submission_date=sub,
            application_id=application_id,
        )
        # Thin live extract → Gloria still gets a usable file only if caller overrides
        if not (
            facts.has(DocType.bank_statement)
            or facts.has(DocType.flight_booking)
            or facts.has(DocType.application_form)
            or facts.has(DocType.passport)
        ):
            used_source = "live_extract_thin"
            logger.warning("thin extract for %s — rules may skip many checks", application_id)

    checklist = load_checklist(_CHECKLIST)
    audit = run(checklist, facts)
    attach_drafts(audit, applicant_first_name=first_name_from_docs(llama_docs))
    audit_json = audit.model_dump(mode="json")

    human_status, human_action = _human_status(audit.outcome)
    meta = load_meta(application_id, settings)
    meta["status"] = human_status
    meta["outcome"] = audit.outcome.value
    meta["human_required"] = True
    meta["human_action"] = human_action
    meta["facts_source"] = used_source
    if case_id:
        meta["case_id"] = case_id
    save_meta(meta, settings)

    report: dict[str, Any] = {
        "application_id": application_id,
        "facts_source": used_source,
        "human_required": True,
        "human_status": human_status,
        "human_action": human_action,
        "ingest_report": ingest,
        "llama_extract": llama,
        "audit": audit_json,
    }
    if case_id:
        report["case_id"] = case_id
    if extra_report:
        report.update(extra_report)

    out_path = app_dir(application_id, settings) / "email_pipeline_report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        f"Audit {application_id}: outcome={audit.outcome.value} → {human_status}",
        flush=True,
    )
    return report
