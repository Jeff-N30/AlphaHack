"""Deterministic travel-insurance field recovery from cover-note text."""
from __future__ import annotations

import re
from datetime import date


_DOB_SAME_LINE = re.compile(
    r"(?i)(?:birth\s*date|date\s*of\s*birth|d\.?\s*o\.?\s*b\.?)"
    r"\s*[:\-]?\s*(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})"
)
# Header row then value row: "Birth Date ...\nJEFF … 03/06/2003 LR 4116483"
_DOB_AFTER_HEADER = re.compile(
    r"(?is)birth\s*date.{0,80}?\n[^\n]{0,80}?"
    r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\s+LR"
)
# Fallback: DD/MM/YYYY immediately before passport number on cover notes
_DOB_BEFORE_PASSPORT = re.compile(
    r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\s+LR\s*\d",
    re.I,
)


def _as_day_first(day: int, month: int, year: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def recover_dob_day_first(text: str) -> date | None:
    """Parse DOB as day-first (DD/MM/YYYY). Never treat as US month-first."""
    if not text:
        return None
    for pat in (_DOB_SAME_LINE, _DOB_AFTER_HEADER):
        m = pat.search(text)
        if m:
            got = _as_day_first(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if got:
                return got
    if re.search(r"(?i)birth\s*date", text):
        m = _DOB_BEFORE_PASSPORT.search(text)
        if m:
            return _as_day_first(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None
