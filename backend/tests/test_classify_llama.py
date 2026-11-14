"""Doc-type classify: keywords when clear, Llama when ambiguous."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.extract.classify import _KEYWORD_TRUST, classify_document
from app.ingest.classify_keywords import classify_text
from app.ingest.render import read_preview
from app.models import DocType

_REPO = Path(__file__).resolve().parents[2]
_CASE01 = _REPO / "eval" / "cases" / "case01_complete" / "docs"


@pytest.fixture()
def offline(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        checklist_dir=_REPO / "checklists",
        demo_offline=True,
        extract_provider="ollama",
        extract_model="llama3.2",
        prompt_version="classify-test-1",
    )


def test_strong_keywords_skip_need_for_llm(offline: Settings) -> None:
    text = "TRAVEL INSURANCE COVER NOTE Medical Coverage: 30000 EUR Schengen"
    kw = classify_text(text, filename="scan001.pdf")
    assert kw.doc_type == DocType.travel_insurance
    assert kw.confidence >= _KEYWORD_TRUST
    out = classify_document(text, filename="scan001.pdf", settings=offline)
    assert out.doc_type == DocType.travel_insurance


def test_random_filename_flight_from_body(offline: Settings) -> None:
    text = "BOOKING REF YM3MB6 CheckMyTrip BEY CDG Middle East Airlines"
    out = classify_document(text, filename="IMG_9999.pdf", settings=offline)
    assert out.doc_type == DocType.flight_booking


def test_france_visas_form_not_employment(offline: Settings) -> None:
    text = (
        "Harmonised application form Application for Schengen Visa "
        "REQUIRED SUPPORTING DOCUMENTS TO SUBMIT APPLICABLE VISA FEE"
    )
    out = classify_document(text, filename="doc.pdf", settings=offline)
    assert out.doc_type == DocType.application_form


def test_garbage_is_unknown(offline: Settings) -> None:
    out = classify_document("hello world blah xyz", filename="x.bin.pdf", settings=offline)
    assert out.doc_type == DocType.unknown


@pytest.mark.skipif(not (_CASE01 / "flight_booking.pdf").exists(), reason="make docs")
def test_case01_pdfs_classify_offline(offline: Settings) -> None:
    expectations = {
        "flight_booking.pdf": DocType.flight_booking,
        "travel_insurance.pdf": DocType.travel_insurance,
        "application_form.pdf": DocType.application_form,
        "bank_statement.pdf": DocType.bank_statement,
        "hotel_booking.pdf": DocType.hotel_booking,
    }
    for name, expected in expectations.items():
        prev = read_preview(_CASE01 / name, max_pages=3)
        # Rename to prove filename is irrelevant
        out = classify_document(prev.text, filename=f"unknown_{name}", settings=offline)
        assert out.doc_type == expected, f"{name}: got {out.doc_type}"


@pytest.mark.integration
def test_live_llama_classifies_ambiguous_flight_wording(tmp_path: Path) -> None:
    """No BEY/CDG/BOOKING keywords — Llama must read the prose."""
    import httpx

    try:
        httpx.get("http://127.0.0.1:11434/api/tags", timeout=2.0).raise_for_status()
    except Exception:
        pytest.skip("Ollama not running")

    settings = Settings(
        data_dir=tmp_path / "data",
        checklist_dir=_REPO / "checklists",
        demo_offline=False,
        extract_provider="ollama",
        extract_model="llama3.2",
        prompt_version="classify-live-1",
        llm_timeout_s=120,
    )
    text = (
        "Passenger ticket confirmation for KARIM NASSAR. "
        "Outbound Middle East Airlines from Beirut Rafic Hariri International "
        "to Paris Charles de Gaulle on 18 December 2026. "
        "Return from Paris to Beirut on 28 December 2026."
    )
    kw = classify_text(text, filename="a.pdf")
    assert kw.doc_type == DocType.unknown or kw.confidence < _KEYWORD_TRUST
    out = classify_document(text, filename="a.pdf", settings=settings)
    assert out.doc_type == DocType.flight_booking
    assert out.confidence >= 0.45
