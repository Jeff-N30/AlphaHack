from __future__ import annotations

from typing import Any

from app.models import DocType
from app.rules.checks._util import ev, fail, ok
from app.rules.context import Facts, RuleContext
from app.rules.registry import register


@register("documents_present")
def documents_present(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    """params: required = list[{type,label,min_count,when}] injected by engine."""
    required = params.get("required") or []
    missing: list[str] = []
    evidence = []
    for req in required:
        when = req.get("when")
        if when and "employee" in when and facts.profile != "employee":
            continue
        dtype = DocType(req["type"])
        need = int(req.get("min_count") or 1)
        have = len(facts.get(dtype))
        if have < need:
            missing.append(req.get("label") or dtype.value)
        else:
            evidence.append(ev(dtype.value, "present", f"count={have}"))
    if missing:
        msg = params.get("message") or "Missing: {missing_labels}"
        msg = msg.replace("{missing_labels}", ", ".join(missing))
        return fail("DOC.PRESENT", msg, evidence=evidence or [ev("application", "missing", ", ".join(missing))])
    return ok("DOC.PRESENT", "All required documents present", evidence=evidence)
