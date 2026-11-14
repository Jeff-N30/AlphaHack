"""LLM field extract (DEMO_OFFLINE fixtures) — flight / insurance / form."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.config import Settings
from app.extract.extract import (
    extract_application_form,
    extract_by_type,
    extract_flight,
    extract_insurance,
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


def test_extract_by_type_dispatch(offline_settings: Settings) -> None:
    f = extract_by_type(DocType.flight_booking, "x", settings=offline_settings)
    assert f.doc_type == DocType.flight_booking
    with pytest.raises(NotImplementedError):
        extract_by_type(DocType.hotel_booking, "x", settings=offline_settings)


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
