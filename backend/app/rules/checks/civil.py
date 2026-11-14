from __future__ import annotations

from typing import Any

from app.models import DocType
from app.rules.checks._util import as_date, ev, fail, ok
from app.rules.context import Facts, RuleContext
from app.rules.dates import add_months
from app.rules.registry import register


@register("issued_within_months")
def issued_within_months(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    field = params.get("field") or "family_register.issue_date"
    doc_name, attr = field.split(".", 1)
    doc = facts.first(DocType(doc_name))
    assert doc is not None
    months = int(params.get("months", 6))
    issued = as_date(getattr(doc, attr))
    limit = add_months(ctx.submission_date, -months)
    evidence = [ev(doc_name, attr, issued)]
    if issued >= limit:
        return ok("FAM.ISSUED_WITHIN_6M", f"Issued {issued} within {months}m", evidence=evidence)
    return fail(
        "FAM.ISSUED_WITHIN_6M",
        f"Issued {issued}; must be within {months} months of {ctx.submission_date}",
        evidence=evidence,
    )
