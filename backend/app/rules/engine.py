"""Run checklist rules over Facts → AuditReport."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import AuditReport, CheckResult, DocType, Outcome, Status
from app.rules.checklist import Checklist, RuleDef, load_checklist
from app.rules.context import Facts, RuleContext
from app.rules.registry import ensure_loaded, get_check


def _docs_present(facts: Facts, docs: list[str]) -> bool:
    for d in docs:
        if not facts.has(DocType(d)):
            return False
    return True


def _apply_fail_status(result: CheckResult, rule: RuleDef) -> CheckResult:
    if result.status == Status.FAIL and rule.fail_status:
        result.status = Status(rule.fail_status)
    return result


def _compute_outcome(results: list[CheckResult]) -> tuple[Outcome, int]:
    escalations = 0
    send_back = False
    needs_gloria = False
    for r in results:
        if r.mode == "manual":
            continue
        if r.status == Status.NEEDS_HUMAN:
            escalations += 1
            needs_gloria = True
        elif r.status == Status.FAIL:
            if r.on_fail == "flag":
                escalations += 1
                needs_gloria = True
            elif r.on_fail == "request":
                send_back = True
            else:
                send_back = True
    if send_back:
        return Outcome.SEND_BACK, escalations
    if needs_gloria:
        return Outcome.NEEDS_GLORIA, escalations
    return Outcome.READY_FOR_APPROVAL, escalations


def run(checklist: Checklist, facts: Facts) -> AuditReport:
    ensure_loaded()
    ctx = RuleContext(
        submission_date=facts.submission_date,
        checklist_id=checklist.id,
        checklist_version=checklist.version,
        reference_currency=checklist.reference_currency,
        fx_rates_to_eur=dict(checklist.fx_rates_to_eur or {"EUR": 1.0}),
        schengen_countries=list(checklist.schengen_countries or []),
    )

    results: list[CheckResult] = []
    skipped: list[str] = []

    for rule in checklist.rules:
        # Manual rules always NEEDS_HUMAN; still emitted
        if rule.mode == "manual" or rule.check == "manual":
            fn = get_check("manual")
            res = fn(facts, rule.params, ctx)
            res.rule_id = rule.id
            res.mode = "manual"
            res.on_fail = rule.on_fail  # type: ignore[assignment]
            results.append(res)
            continue

        # DOC.PRESENT special: inject required_documents
        params: dict[str, Any] = dict(rule.params)
        if rule.check == "documents_present":
            params["required"] = [r.model_dump() for r in checklist.required_documents]
            if rule.message:
                params["message"] = rule.message
            fn = get_check(rule.check)
            res = fn(facts, params, ctx)
            res.rule_id = rule.id
            res.mode = rule.mode  # type: ignore[assignment]
            res.on_fail = rule.on_fail  # type: ignore[assignment]
            if rule.message and res.status != Status.PASS and "{missing" not in res.message:
                pass
            results.append(_apply_fail_status(res, rule))
            continue

        # Skip if dependency docs missing
        if rule.docs and not _docs_present(facts, rule.docs):
            skipped.append(rule.id)
            continue

        fn = get_check(rule.check)
        if rule.message:
            params["message"] = rule.message
        # pass docs list for required_fields etc.
        params["_docs"] = list(rule.docs)
        res = fn(facts, params, ctx)
        res.rule_id = rule.id
        res.mode = rule.mode  # type: ignore[assignment]
        res.on_fail = rule.on_fail  # type: ignore[assignment]
        if rule.mode == "llm_flag" and res.status == Status.FAIL:
            res.status = Status.NEEDS_HUMAN
        results.append(_apply_fail_status(res, rule))

    # Exclude manual from escalation count (already handled)
    outcome, escalations = _compute_outcome(results)

    return AuditReport(
        application_id=facts.application_id,
        checklist_id=checklist.id,
        checklist_version=checklist.version,
        submission_date=facts.submission_date,
        results=results,
        skipped_rules=skipped,
        outcome=outcome,
        escalations=escalations,
        drafts=[],
        cost=[],
        total_usd=0.0,
        created_at=datetime.now(timezone.utc),
    )


def run_path(checklist_path: str, facts: Facts) -> AuditReport:
    return run(load_checklist(checklist_path), facts)
