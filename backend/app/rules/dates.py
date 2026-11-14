"""Pure date helpers for checklist rules (no datetime.now — callers pass refs)."""
from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta


def add_months(d: date, months: int) -> date:
    return d + relativedelta(months=months)


def inclusive_days(start: date, end: date) -> int:
    """Calendar days inclusive (18..28 Dec = 11)."""
    return (end - start).days + 1


def nights(check_in: date, check_out: date) -> int:
    """Hotel nights = checkout - checkin (not inclusive of checkout day as a night)."""
    return (check_out - check_in).days


def months_covered(period_start: date, period_end: date) -> float:
    """Approximate month span for bank statement windows (end - start in months)."""
    rd = relativedelta(period_end, period_start)
    return rd.years * 12 + rd.months + rd.days / 31.0
