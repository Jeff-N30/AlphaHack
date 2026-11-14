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


@register("low_extraction_confidence")
def low_extraction_confidence(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    min_c = float(params.get("min_confidence", 0.8))
    lows: list[str] = []
    evidence = []
    for dtype, docs in facts.documents.items():
        for doc in docs:
            meta = getattr(doc, "field_meta", None) or {}
            for key, conf in meta.items():
                c = getattr(conf, "confidence", None)
                if c is not None and float(c) < min_c:
                    lows.append(f"{dtype.value}.{key}={c}")
                    evidence.append(ev(dtype.value, key, c))
    if lows:
        return needs_human(
            "SUS.LOW_CONFIDENCE",
            f"Low confidence fields: {', '.join(lows[:8])}",
            evidence=evidence,
        )
    return ok("SUS.LOW_CONFIDENCE", "Extraction confidence OK", evidence=[ev("application", "confidence", "ok")])


@register("manual")
def manual(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    return needs_human("MANUAL", "Manual officer confirmation required", mode="manual")
