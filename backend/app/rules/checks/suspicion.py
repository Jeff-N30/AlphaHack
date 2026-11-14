from __future__ import annotations

from typing import Any

from app.models import DocType
from app.rules.checks._util import ev, needs_human, ok
from app.rules.context import Facts, RuleContext
from app.rules.registry import register


@register("llm_anomaly_flags")
def llm_anomaly_flags(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    """mode=llm_flag: any anomaly_flags → NEEDS_HUMAN; else PASS."""
    types = params.get("doc_types") or []
    flags: list[str] = []
    evidence = []
    # Always scan unknown extras
    scan = list(types) + ["unknown"]
    seen: set[str] = set()
    for name in scan:
        if name in seen:
            continue
        seen.add(name)
        dtype = DocType(name)
        for doc in facts.get(dtype):
            af = list(getattr(doc, "anomaly_flags", None) or [])
            if dtype == DocType.unknown and not af:
                af = ["unknown_doc_type"]
            if af:
                flags.extend(f"{name}:{x}" for x in af)
                evidence.append(ev(name, "anomaly_flags", ",".join(af)))
    if flags:
        return needs_human("SUS.DOC_ANOMALY", f"Anomaly flags: {', '.join(flags)}", evidence=evidence)
    return ok("SUS.DOC_ANOMALY", "No anomaly flags", evidence=[ev("application", "anomaly_flags", "none")])


_DOC_PLAIN = {
    "passport": "passport",
    "travel_insurance": "insurance",
    "bank_statement": "bank statement",
    "employment_letter": "employer letter",
    "application_form": "application form",
    "flight_booking": "flight booking",
    "hotel_booking": "hotel booking",
    "payslip": "payslip",
    "family_register": "family register",
}

_FIELD_PLAIN = {
    "issue_date": "issue date",
    "date_of_birth": "birth date",
    "expiry_date": "expiry date",
    "passport_number": "passport number",
    "surname": "surname",
    "given_names": "given names",
    "account_holder": "account holder",
    "insured_name": "insured name",
    "employee_name": "employee name",
}


@register("low_extraction_confidence")
def low_extraction_confidence(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    min_c = float(params.get("min_confidence", 0.8))
    lows: list[tuple[str, str, Any, float]] = []
    evidence = []
    for dtype, docs in facts.documents.items():
        for doc in docs:
            meta = getattr(doc, "field_meta", None) or {}
            for key, conf in meta.items():
                c = getattr(conf, "confidence", None)
                if c is not None and float(c) < min_c:
                    val = getattr(doc, key, None)
                    lows.append((dtype.value, key, val, float(c)))
                    # Keep raw value in evidence for Gloria; score in message only
                    evidence.append(ev(dtype.value, key, val if val is not None else f"confidence={c}"))
    if not lows:
        return ok(
            "SUS.LOW_CONFIDENCE",
            "Extraction confidence OK",
            evidence=[ev("application", "confidence", "ok")],
        )
    # Gloria-facing: name the doc, field, and what we think we read
    dtype, key, val, _c = lows[0]
    doc_l = _DOC_PLAIN.get(dtype, dtype.replace("_", " "))
    field_l = _FIELD_PLAIN.get(key, key.replace("_", " "))
    if val is not None and str(val).strip():
        msg = (
            f"Unsure about {doc_l} {field_l} (showing {val}) "
            f"— open the {doc_l} and confirm the printed value"
        )
    else:
        msg = (
            f"Unsure about {doc_l} {field_l} "
            f"— open the {doc_l} and confirm it looks right"
        )
    if len(lows) > 1:
        msg += f" (+{len(lows) - 1} more)"
    return needs_human("SUS.LOW_CONFIDENCE", msg, evidence=evidence)



@register("manual")
def manual(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    return needs_human("MANUAL", "Manual officer confirmation required", mode="manual")
