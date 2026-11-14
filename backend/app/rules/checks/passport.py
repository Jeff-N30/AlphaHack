from __future__ import annotations

from typing import Any

from app.models import DocType
from app.rules.checks._util import as_date, ev, fail, needs_human, ok, passport_expiry_ok, trip_dates
from app.rules.context import Facts, RuleContext
from app.rules.dates import add_months
from app.rules.registry import register


@register("mrz_checksums_valid")
def mrz_checksums_valid(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    pp = facts.first(DocType.passport)
    assert pp is not None
    mrz = getattr(pp, "mrz", None)
    if mrz is None:
        return needs_human("PP.MRZ_CHECKSUM", "No MRZ parsed from passport.")
    evidence = [ev("passport", "mrz.checksums_valid", mrz.checksums_valid)]
    if mrz.checksums_valid:
        return ok("PP.MRZ_CHECKSUM", "MRZ check digits valid", evidence=evidence)
    return needs_human(
        "PP.MRZ_CHECKSUM",
        "Passport MRZ check digits do not validate (bad scan or altered document).",
        evidence=evidence + [ev("passport", "mrz.failed_checks", ",".join(mrz.failed_checks or []))],
    )


@register("mrz_matches_visual_zone")
def mrz_matches_visual_zone(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    pp = facts.first(DocType.passport)
    assert pp is not None
    mrz = getattr(pp, "mrz", None)
    if mrz is None or not mrz.checksums_valid:
        return needs_human("PP.MRZ_MATCHES_VIZ", "Cannot compare VIZ without valid MRZ.")
    mismatches: list[str] = []
    pairs = [
        ("surname", pp.surname, mrz.surname),
        ("given_names", pp.given_names, mrz.given_names),
        ("passport_number", pp.passport_number, mrz.passport_number),
        ("date_of_birth", as_date(pp.date_of_birth), mrz.date_of_birth),
        ("expiry_date", as_date(pp.expiry_date), mrz.expiry_date),
    ]
    for name, viz, m in pairs:
        if str(viz).upper().replace(" ", "") != str(m).upper().replace(" ", ""):
            # allow given name token order / spacing via soft compare for names only
            if name in {"surname", "given_names"}:
                from app.rules.names import normalize_name

                if normalize_name(str(viz)) == normalize_name(str(m)):
                    continue
            mismatches.append(name)
    evidence = [ev("passport", "mrz_vs_viz", ",".join(mismatches) or "match")]
    if mismatches:
        return needs_human(
            "PP.MRZ_MATCHES_VIZ",
            f"MRZ/VIZ mismatch on: {', '.join(mismatches)}",
            evidence=evidence,
        )
    return ok("PP.MRZ_MATCHES_VIZ", "MRZ matches visual zone", evidence=evidence)


@register("date_after")
def date_after(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    """params.field like passport.expiry_date; ref: submission_date."""
    field = params["field"]
    doc_name, attr = field.split(".", 1)
    doc = facts.first(DocType(doc_name))
    assert doc is not None
    value = as_date(getattr(doc, attr))
    ref = ctx.submission_date if params.get("ref") == "submission_date" else as_date(params["ref"])
    evidence = [ev(doc_name, field, value)]
    if value >= ref:
        return ok("DATE_AFTER", f"{field} on/after {ref}", evidence=evidence)
    return fail("DATE_AFTER", f"{field}={value} before {ref}", evidence=evidence)


@register("passport_issued_within_years")
def passport_issued_within_years(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    pp = facts.first(DocType.passport)
    assert pp is not None
    years = int(params.get("years", 10))
    issued = as_date(pp.issue_date)
    ref = ctx.submission_date
    limit = add_months(ref, -years * 12)
    evidence = [ev("passport", "issue_date", issued)]
    # issued must be on/after (submission - 10y) i.e. not older than 10 years
    if issued >= limit:
        return ok("PP.ISSUED_WITHIN_10Y", f"Issued {issued} within {years}y of {ref}", evidence=evidence)
    return fail(
        "PP.ISSUED_WITHIN_10Y",
        f"Passport issued {issued}; must be within {years} years of {ref}",
        evidence=evidence,
    )


@register("passport_valid_after_departure")
def passport_valid_after_departure(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    pp = facts.first(DocType.passport)
    assert pp is not None
    months = int(params.get("months", 3))
    _, ret = trip_dates(facts)
    assert ret is not None
    expiry = as_date(pp.expiry_date)
    required = add_months(ret, months)
    evidence = [
        ev("passport", "expiry_date", expiry),
        ev("flight_booking", "return_date", ret),
    ]
    if passport_expiry_ok(expiry, ret, months):
        return ok("PP.VALID_AFTER_DEPARTURE", f"Expiry {expiry} >= {required}", evidence=evidence)
    msg = params.get("message") or "Passport expires {expiry}; must be valid until at least {required}."
    msg = msg.replace("{expiry}", expiry.strftime("%d/%m/%Y")).replace(
        "{required}", required.strftime("%d/%m/%Y")
    )
    return fail("PP.VALID_AFTER_DEPARTURE", msg, evidence=evidence)
