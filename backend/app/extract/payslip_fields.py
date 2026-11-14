"""Deterministic payslip field parse from labeled EN/FR text (LLM fallback elsewhere)."""
from __future__ import annotations

import re
from typing import Any

_MONTHS = {
    "january": "01",
    "jan": "01",
    "janvier": "01",
    "february": "02",
    "feb": "02",
    "février": "02",
    "fevrier": "02",
    "march": "03",
    "mar": "03",
    "mars": "03",
    "april": "04",
    "apr": "04",
    "avril": "04",
    "may": "05",
    "mai": "05",
    "june": "06",
    "jun": "06",
    "juin": "06",
    "july": "07",
    "jul": "07",
    "juillet": "07",
    "august": "08",
    "aug": "08",
    "août": "08",
    "aout": "08",
    "september": "09",
    "sep": "09",
    "sept": "09",
    "septembre": "09",
    "october": "10",
    "oct": "10",
    "octobre": "10",
    "november": "11",
    "nov": "11",
    "novembre": "11",
    "december": "12",
    "dec": "12",
    "décembre": "12",
    "decembre": "12",
}


def parse_payslip_from_text(text: str) -> dict[str, Any] | None:
    """Return payslip fields if Employee/Employer/Period/Net are clearly labeled."""
    if not text or not text.strip():
        return None
    employee = _labeled(text, r"employee|employé|employe")
    employer = _labeled(text, r"employer|employeur")
    period = _period(text)
    net = _money(text, r"salaire\s*net|net\s*pay|net\s*salary|net\s+pay")
    if not (employee and employer and period and net):
        return None
    return {
        "employee_name": employee,
        "employer_name": employer,
        "period_month": period,
        "net_pay": net,
    }


def _labeled(text: str, label: str) -> str | None:
    m = re.search(
        rf"^\s*(?:{label})\s*[:\-–]\s*(?P<v>[^\n|;]{{2,80}})",
        text,
        flags=re.I | re.M,
    )
    if not m:
        m = re.search(
            rf"\b(?:{label})\s*[:\-–]\s*(?P<v>[^\n|;]{{2,80}})",
            text,
            flags=re.I,
        )
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group("v")).strip(" \t-:;,.|") or None


def _period(text: str) -> str | None:
    m = re.search(r"period\s*(?:\([^)]*\))?\s*[:\-–]?\s*(\d{4})-(\d{2})", text, flags=re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(
        r"(?:period|mois|month)\s*[:\-–]?\s*([A-Za-zéûôà]+)\s+(\d{4})",
        text,
        flags=re.I,
    )
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        if mon:
            return f"{m.group(2)}-{mon}"
    m = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])\b", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


def _money(text: str, label: str) -> dict[str, Any] | None:
    m = re.search(
        rf"(?:{label})\s*[:\-–]?\s*"
        rf"(?P<amount>[0-9]+(?:[ ,][0-9]{{3}})*(?:[.,][0-9]{{2}})?)\s*"
        rf"(?P<cur>USD|EUR|GBP|CHF)\b",
        text,
        flags=re.I,
    )
    if not m:
        return None
    raw = m.group("amount").replace(" ", "").replace(",", "")
    try:
        amount = float(raw)
    except ValueError:
        return None
    return {"amount": amount, "currency": m.group("cur").upper()}
