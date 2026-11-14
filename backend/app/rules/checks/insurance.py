from __future__ import annotations

from typing import Any

from app.models import DocType
from app.rules.checks._util import as_date, ev, fail, needs_human, ok, trip_dates
from app.rules.context import Facts, RuleContext
from app.rules.registry import register


@register("insurance_min_coverage")
def insurance_min_coverage(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    ins = facts.first(DocType.travel_insurance)
    assert ins is not None
    min_amt = float(params.get("min_amount", 30000))
    want_ccy = str(params.get("currency", "EUR")).upper()
    cov = ins.coverage
    evidence = [ev("travel_insurance", "coverage", f"{cov.amount} {cov.currency}")]
    if cov.currency.upper() != want_ccy:
        return needs_human(
            "INS.MIN_COVERAGE",
            f"Coverage currency {cov.currency} != {want_ccy}",
            evidence=evidence,
        )
    if cov.amount + 1e-9 >= min_amt:
        return ok("INS.MIN_COVERAGE", f"Coverage {cov.amount} >= {min_amt}", evidence=evidence)
    return fail(
        "INS.MIN_COVERAGE",
        f"Coverage {cov.amount} {cov.currency} below {min_amt} {want_ccy}",
        evidence=evidence,
    )


@register("insurance_territory")
def insurance_territory(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    ins = facts.first(DocType.travel_insurance)
    assert ins is not None
    accepted = set(params.get("accepted") or ["SCHENGEN", "EUROPE", "WORLDWIDE"])
    terr = str(ins.territory).upper()
    evidence = [ev("travel_insurance", "territory", terr), ev("travel_insurance", "territory_raw", ins.territory_raw)]
    if terr in accepted:
        return ok("INS.TERRITORY", f"Territory {terr} accepted", evidence=evidence)
    return fail("INS.TERRITORY", f"Territory {terr} not accepted", evidence=evidence)


@register("insurance_covers_stay")
def insurance_covers_stay(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    ins = facts.first(DocType.travel_insurance)
    arrival, ret = trip_dates(facts)
    assert ins and arrival and ret
    start, end = as_date(ins.start_date), as_date(ins.end_date)
    evidence = [
        ev("travel_insurance", "start_date", start),
        ev("travel_insurance", "end_date", end),
        ev("flight_booking", "arrival", arrival),
        ev("flight_booking", "return", ret),
    ]
    if start <= arrival and end >= ret:
        return ok("INS.COVERS_STAY", "Insurance covers trip dates", evidence=evidence)
    return fail(
        "INS.COVERS_STAY",
        f"Insurance {start}→{end} does not cover stay {arrival}→{ret}",
        evidence=evidence,
    )


@register("insurance_covers_items")
def insurance_covers_items(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    ins = facts.first(DocType.travel_insurance)
    assert ins is not None
    required = set(params.get("required") or [])
    have = set(ins.covers or [])
    evidence = [ev("travel_insurance", "covers", ",".join(sorted(have)))]
    missing = required - have
    if missing:
        return fail(
            "INS.MEDICAL_REPATRIATION",
            f"Missing cover items: {', '.join(sorted(missing))}",
            evidence=evidence,
        )
    return ok("INS.MEDICAL_REPATRIATION", "Required cover items present", evidence=evidence)
