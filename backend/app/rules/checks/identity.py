from __future__ import annotations

from typing import Any

from app.models import DocType, Status
from app.rules.checks._util import as_date, ev, fail, needs_human, ok
from app.rules.context import Facts, RuleContext
from app.rules.names import compare_names
from app.rules.registry import register


def _mrz_reference(facts: Facts) -> str | None:
    pp = facts.first(DocType.passport)
    if pp is None:
        return None
    mrz = getattr(pp, "mrz", None)
    if mrz is not None and mrz.checksums_valid:
        return f"{mrz.surname} {mrz.given_names}"
    return f"{pp.surname} {pp.given_names}"


def _names_on_doc(doc: Any, dtype: DocType) -> list[str]:
    if dtype == DocType.flight_booking:
        return list(getattr(doc, "passenger_names", []) or [])
    if dtype == DocType.hotel_booking:
        return list(getattr(doc, "guest_names", []) or [])
    if dtype == DocType.travel_insurance:
        return [getattr(doc, "insured_name")] if getattr(doc, "insured_name", None) else []
    if dtype == DocType.bank_statement:
        return [getattr(doc, "account_holder")] if getattr(doc, "account_holder", None) else []
    if dtype == DocType.employment_letter:
        return [getattr(doc, "employee_name")] if getattr(doc, "employee_name", None) else []
    if dtype == DocType.payslip:
        return [getattr(doc, "employee_name")] if getattr(doc, "employee_name", None) else []
    if dtype == DocType.application_form:
        return [f"{doc.surname} {doc.given_names}"]
    return []


@register("name_consistency")
def name_consistency(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    ref = _mrz_reference(facts)
    if not ref:
        return needs_human("ID.NAME_MATCH", "No passport name reference.")
    variant = int(params.get("variant_threshold", 85))
    fail_below = int(params.get("fail_below", 70))
    compare = params.get("compare") or []
    worst = Status.PASS
    evidence = [ev("passport", "mrz_name", ref)]
    for name in compare:
        dtype = DocType(name)
        for doc in facts.get(dtype):
            for cand in _names_on_doc(doc, dtype):
                st, score, pair = compare_names(
                    ref, cand, variant_threshold=variant, fail_below=fail_below
                )
                evidence.append(ev(dtype.value, "name", f"{cand} ({score:.1f})"))
                if st == Status.FAIL:
                    worst = Status.FAIL
                elif st == Status.NEEDS_HUMAN and worst != Status.FAIL:
                    worst = Status.NEEDS_HUMAN
    if worst == Status.PASS:
        return ok("ID.NAME_MATCH", "Names consistent with passport MRZ", evidence=evidence)
    if worst == Status.NEEDS_HUMAN:
        return needs_human("ID.NAME_MATCH", "Name variant vs passport MRZ — Gloria review", evidence=evidence)
    return fail("ID.NAME_MATCH", "Name mismatch vs passport MRZ", evidence=evidence)


@register("form_matches_passport")
def form_matches_passport(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    form = facts.first(DocType.application_form)
    pp = facts.first(DocType.passport)
    assert form is not None and pp is not None
    fields = params.get("fields") or ["surname", "given_names", "date_of_birth", "passport_number", "expiry_date"]
    bad: list[str] = []
    evidence = []
    for f in fields:
        fv = getattr(form, f)
        pv = getattr(pp, f)
        if f in {"date_of_birth", "expiry_date"}:
            match = as_date(fv) == as_date(pv)
        elif f in {"surname", "given_names"}:
            from app.rules.names import normalize_name

            match = normalize_name(str(fv)) == normalize_name(str(pv))
        else:
            match = str(fv).upper() == str(pv).upper()
        evidence.append(ev("application_form", f, fv))
        if not match:
            bad.append(f)
    if bad:
        return fail(
            "ID.FORM_MATCHES_PASSPORT",
            f"Form does not match passport on: {', '.join(bad)}",
            evidence=evidence,
        )
    return ok("ID.FORM_MATCHES_PASSPORT", "Form matches passport", evidence=evidence)


@register("field_equal_across_docs")
def field_equal_across_docs(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    field = params["field"]
    docs = [DocType(x) for x in params.get("docs") or []]
    optional = bool(params.get("optional_missing", False))
    values: list[tuple[str, Any]] = []
    for dtype in docs:
        for doc in facts.get(dtype):
            if not hasattr(doc, field):
                continue
            val = getattr(doc, field)
            if val is None:
                if optional:
                    continue
                return needs_human(
                    "FIELD_EQ",
                    f"Missing {field} on {dtype.value}",
                    evidence=[ev(dtype.value, field, None)],
                )
            values.append((dtype.value, val))
    if len(values) < 2:
        return ok("FIELD_EQ", f"Not enough docs to compare {field}", evidence=[])
    normed = []
    for _, v in values:
        if hasattr(v, "isoformat"):
            normed.append(as_date(v))
        else:
            normed.append(str(v).upper())
    evidence = [ev(dn, field, v) for dn, v in values]
    if len(set(str(x) for x in normed)) == 1:
        return ok("FIELD_EQ", f"{field} matches across docs", evidence=evidence)
    return fail(
        "FIELD_EQ",
        f"{field} mismatch across documents",
        evidence=evidence,
    )
