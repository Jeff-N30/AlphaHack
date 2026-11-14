"""Deterministic flight-field recovery from ticket text (EN/FR labels)."""
from __future__ import annotations

import re

_REF = re.compile(
    r"(?i)\b(?:"
    r"booking\s*ref(?:erence)?|booking\s*#|pnr|record\s*locator|"
    r"confirmation\s*(?:no|num|number|#)?|réf(?:érence)?\s*(?:réservation)?"
    r")\s*[:\-–]?\s*(?P<ref>[A-Z0-9]{5,8})\b"
)


def recover_booking_reference(text: str) -> str | None:
    if not text:
        return None
    m = _REF.search(text)
    return m.group("ref").upper() if m else None
