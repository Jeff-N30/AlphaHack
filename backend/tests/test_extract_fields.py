"""LLM field extract (DEMO_OFFLINE fixtures) — flight / insurance / form."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.config import Settings
from app.extract.extract import (
    extract_application_form,
    extract_bank,
    extract_by_type,
    extract_employment,
    extract_family_register,
    extract_flight,
    extract_hotel,
    extract_insurance,
    extract_payslip,
)
from app.extract.llm import reset_cost_log
from app.ingest.classify_keywords import classify_text
from app.models import DocType

_REPO = Path(__file__).resolve().parents[2]
_JEFF = _REPO / "data" / "real_demo"


@pytest.fixture()
def offline_settings(tmp_path: Path) -> Settings:
    reset_cost_log()
    return Settings(
        data_dir=tmp_path / "data",
        checklist_dir=_REPO / "checklists",
        demo_offline=True,
        prompt_version="test-1",
        extract_model="offline-fixture",
    )


def test_offline_flight_fixture_shape(offline_settings: Settings) -> None:
    out = extract_flight("dummy itinerary text BEY CDG", settings=offline_settings)
    assert out.doc_type == DocType.flight_booking
    assert len(out.segments) == 2
    assert out.segments[0].from_airport == "BEY"
    assert out.segments[0].to_airport == "CDG"
    assert out.segments[0].departure_date == date(2026, 2, 4)
    assert out.segments[-1].to_airport == "BEY"
    assert out.booking_reference == "YM3MB6"


def test_offline_insurance_covers_schengen(offline_settings: Settings) -> None:
    out = extract_insurance("dummy cover note", settings=offline_settings)
    assert out.doc_type == DocType.travel_insurance
    assert out.territory == "SCHENGEN"
    assert out.coverage.amount >= 30_000
    assert out.start_date <= date(2026, 2, 4)
    assert out.end_date >= date(2026, 2, 10)


def test_offline_application_form(offline_settings: Settings) -> None:
    out = extract_application_form("Harmonised application form", settings=offline_settings)
    assert out.doc_type == DocType.application_form
    assert out.surname.upper() == "NADER"
    assert "JEFF" in out.given_names.upper()


def test_offline_hotel_fixture(offline_settings: Settings) -> None:
    out = extract_hotel("dummy hotel confirmation Paris", settings=offline_settings)
    assert out.doc_type == DocType.hotel_booking
    assert out.country == "FR"
    assert out.city.lower() == "paris"
    assert out.check_in == date(2026, 2, 4)
    assert out.check_out == date(2026, 2, 10)
    assert out.check_out > out.check_in


def test_offline_bank_fixture(offline_settings: Settings) -> None:
    out = extract_bank("dummy bank statement USD", settings=offline_settings)
    assert out.doc_type == DocType.bank_statement
    assert out.account_currency == "USD"
    assert out.closing_balance >= out.opening_balance
    assert out.has_bank_stamp is True
    assert out.period_end >= out.period_start
    assert len(out.transactions) >= 1


def test_offline_employment_payslip_family(offline_settings: Settings) -> None:
    emp = extract_employment("dummy employer letter", settings=offline_settings)
    assert emp.doc_type == DocType.employment_letter
    assert emp.employee_name
    assert emp.leave_end is not None and emp.leave_start is not None
    assert emp.leave_end >= emp.leave_start
    pay = extract_payslip("dummy payslip", settings=offline_settings)
    assert pay.doc_type == DocType.payslip
    assert pay.period_month.count("-") == 1
    fam = extract_family_register("dummy ekhraj", settings=offline_settings)
    assert fam.doc_type == DocType.family_register
    assert fam.issue_date is not None
    assert fam.translated is True


def test_extract_by_type_dispatch(offline_settings: Settings) -> None:
    f = extract_by_type(DocType.flight_booking, "x", settings=offline_settings)
    assert f.doc_type == DocType.flight_booking
    h = extract_by_type(DocType.hotel_booking, "x", settings=offline_settings)
    assert h.doc_type == DocType.hotel_booking
    b = extract_by_type(DocType.bank_statement, "x", settings=offline_settings)
    assert b.doc_type == DocType.bank_statement
    e = extract_by_type(DocType.employment_letter, "x", settings=offline_settings)
    assert e.doc_type == DocType.employment_letter
    p = extract_by_type(DocType.payslip, "x", settings=offline_settings)
    assert p.doc_type == DocType.payslip
    fr = extract_by_type(DocType.family_register, "x", settings=offline_settings)
    assert fr.doc_type == DocType.family_register
    with pytest.raises(NotImplementedError):
        extract_by_type(DocType.cnss_certificate, "x", settings=offline_settings)


def test_offline_bank_hotel_feed_rules(offline_settings: Settings) -> None:
    """Extracted bank+hotel must be enough for funds/hotel rules (AI extract → code decide)."""
    from app.rules.checklist import load_checklist
    from app.rules.engine import run
    from app.rules.facts_from_extractions import facts_from_extractions

    hotel = extract_hotel("x", settings=offline_settings)
    bank = extract_bank("x", settings=offline_settings)
    flight = extract_flight("x", settings=offline_settings)
    facts = facts_from_extractions(
        [hotel, bank, flight],
        submission_date=date(2026, 1, 15),
        application_id="test-bank-hotel",
    )
    checklist = load_checklist(_REPO / "checklists" / "fr-schengen-short-stay.yaml")
    audit = run(checklist, facts)
    by_id = {r.rule_id: r.status.value for r in audit.results}
    assert by_id.get("BANK.SUFFICIENT_FUNDS") == "PASS"
    assert by_id.get("BANK.STAMPED") == "PASS"
    assert by_id.get("TRIP.HOTEL_COVERS_STAY") == "PASS"
    assert by_id.get("TRIP.HOTEL_IN_DESTINATION") == "PASS"


def test_classify_france_visas_form_not_employment() -> None:
    text = (
        "Harmonised application form Application for Schengen Visa "
        "REQUIRED SUPPORTING DOCUMENTS TO SUBMIT YOUR APPLICATION "
        "APPLICABLE VISA FEE Current occupation Employer address"
    )
    c = classify_text(text, filename="All_documents_visa.pdf")
    assert c.doc_type == DocType.application_form


@pytest.mark.skipif(not (_JEFF / "flight_itinerary.pdf").exists(), reason="no local Jeff demo PDFs")
def test_classify_jeff_local_pdfs() -> None:
    from app.ingest.render import read_preview

    form = read_preview(_JEFF / "All_documents_visa.pdf", max_pages=6)
    assert classify_text(form.text, filename="All_documents_visa.pdf").doc_type == DocType.application_form

    ins = read_preview(_JEFF / "insurance.pdf", max_pages=2)
    assert classify_text(ins.text, filename="insurance.pdf").doc_type == DocType.travel_insurance

    fl = read_preview(_JEFF / "flight_itinerary.pdf", max_pages=2)
    assert classify_text(fl.text, filename="flight_itinerary.pdf").doc_type == DocType.flight_booking
