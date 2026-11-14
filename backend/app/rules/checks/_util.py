"""Shared helpers for check functions."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.models import CheckResult, DocType, Evidence, Extraction, Status
from app.rules.context import Facts
from app.rules.dates import add_months, inclusive_days


def ok(
    rule_id: str,
    message: str = "OK",
    *,
    evidence: list[Evidence] | None = None,
    mode: str = "code",
    on_fail: str | None = None,
) -> CheckResult:
    return CheckResult(
        rule_id=rule_id,
        status=Status.PASS,
        evidence=evidence or [],
        message=message,
        mode=mode,  # type: ignore[arg-type]
        on_fail=on_fail,  # type: ignore[arg-type]
    )


def fail(
    rule_id: str,
    message: str,
    *,
    evidence: list[Evidence] | None = None,
    mode: str = "code",
    on_fail: str | None = None,
    status: Status = Status.FAIL,
) -> CheckResult:
    return CheckResult(
        rule_id=rule_id,
        status=status,
        evidence=evidence or [],
        message=message,
        mode=mode,  # type: ignore[arg-type]
        on_fail=on_fail,  # type: ignore[arg-type]
    )


def needs_human(
    rule_id: str,
    message: str,
    *,
    evidence: list[Evidence] | None = None,
    mode: str = "code",
    on_fail: str | None = None,
) -> CheckResult:
    return fail(
        rule_id,
        message,
        evidence=evidence,
        mode=mode,
        on_fail=on_fail,
        status=Status.NEEDS_HUMAN,
    )


def ev(doc: str, field: str, value: Any, page: int | None = 1) -> Evidence:
    return Evidence(doc=doc, field=field, value=None if value is None else str(value), page=page)


def as_date(v: Any) -> date:
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def trip_dates(facts: Facts) -> tuple[Optional[date], Optional[date]]:
    """Return (arrival_in_schengen, return_home) from flight segments."""
    flight = facts.first(DocType.flight_booking)
    if flight is None:
        return None, None
    segs = getattr(flight, "segments", None) or []
    if not segs:
        return None, None
    arrival = as_date(segs[0].departure_date)
    ret = as_date(segs[-1].departure_date)
    return arrival, ret


def stay_days(facts: Facts) -> Optional[int]:
    a, b = trip_dates(facts)
    if a is None or b is None:
        return None
    return inclusive_days(a, b)


def file_label(doc: Extraction, fallback: str) -> str:
    meta = getattr(doc, "field_meta", {}) or {}
    if "file" in meta and getattr(meta["file"], "raw_text", None):
        return str(meta["file"].raw_text)
    return fallback


def passport_expiry_ok(expiry: date, return_date: date, months: int) -> bool:
    return expiry >= add_months(return_date, months)
