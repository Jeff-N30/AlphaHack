"""Deterministic payslip parse (EN/FR labeled specimens)."""
from __future__ import annotations

from app.extract.payslip_fields import parse_payslip_from_text


def test_parse_specimen_payslip() -> None:
    text = (
        "PAYSLIP / BULLETIN DE PAIE — SPECIMEN\n"
        "Employer: Cedar Specimen SAL (FAKE)\n"
        "Employee: KARIM NASSAR\n"
        "Period (YYYY-MM): 2026-10\n"
        "Net pay: 1,800.00 USD\n"
    )
    p = parse_payslip_from_text(text)
    assert p is not None
    assert p["employee_name"] == "KARIM NASSAR"
    assert "Cedar Specimen" in p["employer_name"]
    assert p["period_month"] == "2026-10"
    assert p["net_pay"]["amount"] == 1800.0
    assert p["net_pay"]["currency"] == "USD"


def test_parse_french_month_name() -> None:
    text = (
        "Employeur: Soft SAL\n"
        "Employé: Karim Nassar\n"
        "Mois: octobre 2026\n"
        "Salaire net: 1800.00 EUR\n"
    )
    p = parse_payslip_from_text(text)
    assert p is not None
    assert p["period_month"] == "2026-10"
    assert p["net_pay"]["currency"] == "EUR"


def test_parse_incomplete_returns_none() -> None:
    assert parse_payslip_from_text("Employee: Karim\nNet pay: 100 USD") is None
