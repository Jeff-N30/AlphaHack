from __future__ import annotations

from typing import Any

from app.models import DocType
from app.rules.checks._util import as_date, ev, fail, ok, trip_dates
from app.rules.context import Facts, RuleContext
from app.rules.registry import register


@register("required_fields")
def required_fields(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    # Used for employment letter — docs list from engine ensures present
    docs = params.get("_docs") or ["employment_letter"]
    fields = params.get("fields") or []
    dtype = DocType(docs[0] if isinstance(docs[0], str) else docs[0])
    # engine passes rule docs separately; look up employment_letter by default
    doc = facts.first(DocType.employment_letter)
    assert doc is not None
    missing = [f for f in fields if getattr(doc, f, None) is None]
    evidence = [ev("employment_letter", f, getattr(doc, f, None)) for f in fields]
    if missing:
        return fail(
            "EMP.LETTER_FIELDS",
            f"Missing fields: {', '.join(missing)}",
            evidence=evidence,
        )
    return ok("EMP.LETTER_FIELDS", "Employment letter fields present", evidence=evidence)


@register("leave_covers_trip")
def leave_covers_trip(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    letter = facts.first(DocType.employment_letter)
    arrival, ret = trip_dates(facts)
    assert letter and arrival and ret
    ls, le = as_date(letter.leave_start), as_date(letter.leave_end)
    evidence = [
        ev("employment_letter", "leave_start", ls),
        ev("employment_letter", "leave_end", le),
        ev("flight_booking", "arrival", arrival),
        ev("flight_booking", "return", ret),
    ]
    if ls <= arrival and le >= ret:
        return ok("EMP.LEAVE_COVERS_TRIP", "Leave covers trip", evidence=evidence)
    return fail(
        "EMP.LEAVE_COVERS_TRIP",
        f"Leave {ls}→{le} does not cover trip {arrival}→{ret}",
        evidence=evidence,
    )


@register("payslips_recent")
def payslips_recent(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    slips = facts.get(DocType.payslip)
    need = int(params.get("count", 3))
    consecutive = bool(params.get("consecutive", True))
    latest_within = int(params.get("latest_within_days", 45))
    evidence = [ev("payslip", "count", len(slips))]
    if len(slips) < need:
        return fail("EMP.PAYSLIPS_RECENT", f"Need {need} payslips, have {len(slips)}", evidence=evidence)
    months = sorted(s.period_month for s in slips)
    if consecutive and len(months) >= need:
        # check last `need` months are consecutive YYYY-MM
        use = months[-need:]
        ok_seq = True
        for a, b in zip(use, use[1:]):
            y1, m1 = map(int, a.split("-"))
            y2, m2 = map(int, b.split("-"))
            nm = m1 + 1
            ny = y1
            if nm == 13:
                nm, ny = 1, y1 + 1
            if (y2, m2) != (ny, nm):
                ok_seq = False
                break
        if not ok_seq:
            return fail("EMP.PAYSLIPS_RECENT", f"Payslips not consecutive: {use}", evidence=evidence)
        months = use
    # latest month end roughly within latest_within days of submission
    latest = months[-1]
    y, m = map(int, latest.split("-"))
    from calendar import monthrange
    from datetime import date

    last_day = date(y, m, monthrange(y, m)[1])
    age = (ctx.submission_date - last_day).days
    evidence.append(ev("payslip", "latest_period", latest))
    if age > latest_within:
        return fail(
            "EMP.PAYSLIPS_RECENT",
            f"Latest payslip {latest} is {age}d before submission (max {latest_within})",
            evidence=evidence,
        )
    return ok("EMP.PAYSLIPS_RECENT", "Payslips recent and consecutive", evidence=evidence)
