"""Email message → application → extract → rules (no live IMAP)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.config import Settings
from app.ingest.email import SavedEmail
from app.ingest.email_pipeline import process_email_message
from app.models import DocType, FlightBookingExtraction, FlightSegment, MRZ
from app.rules.facts_from_extractions import facts_from_extractions, passport_from_mrz

_REPO = Path(__file__).resolve().parents[2]
_CASE01 = _REPO / "eval" / "cases" / "case01_complete" / "docs"


@pytest.fixture()
def offline_settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        checklist_dir=_REPO / "checklists",
        demo_offline=True,
        extract_provider="ollama",
        extract_model="llama3.2",
        prompt_version="test-email-pipe",
    )


def test_passport_from_mrz_builds_extraction() -> None:
    mrz = MRZ(
        line1="P<LBNNASSAR<<KARIM<<<<<<<<<<<<<<<<<<<<<<<",
        line2="LR04829136LBN9403121M3205095<<<<<<<<<<<<<<06",
        surname="NASSAR",
        given_names="KARIM",
        passport_number="LR0482913",
        nationality="LBN",
        date_of_birth=date(1994, 3, 12),
        sex="M",
        expiry_date=date(2032, 5, 9),
        checksums_valid=True,
        failed_checks=[],
    )
    pe = passport_from_mrz(mrz)
    assert pe.doc_type == DocType.passport
    assert pe.passport_number == "LR0482913"
    assert pe.mrz is not None and pe.mrz.checksums_valid


def test_facts_from_extractions_groups_by_type() -> None:
    flight = FlightBookingExtraction(
        passenger_names=["KARIM NASSAR"],
        booking_reference="FAKE13",
        segments=[
            FlightSegment(
                from_airport="BEY",
                to_airport="CDG",
                to_country="FR",
                departure_date=date(2026, 12, 18),
                flight_number="XX0201",
            ),
            FlightSegment(
                from_airport="CDG",
                to_airport="BEY",
                to_country="LB",
                departure_date=date(2026, 12, 28),
                flight_number="XX0202",
            ),
        ],
    )
    facts = facts_from_extractions(
        [flight],
        submission_date=date(2026, 11, 16),
        application_id="t1",
    )
    assert facts.has(DocType.flight_booking)
    assert not facts.has(DocType.passport)


@pytest.mark.skipif(not (_CASE01 / "flight_booking.pdf").exists(), reason="run make docs")
def test_process_email_message_runs_rules(offline_settings: Settings, tmp_path: Path) -> None:
    # Pretend IMAP already saved attachments under a uid folder
    mail_dir = tmp_path / "mail" / "99"
    mail_dir.mkdir(parents=True)
    files: list[str] = []
    for name in ("flight_booking.pdf", "travel_insurance.pdf", "application_form.pdf"):
        src = _CASE01 / name
        dest = mail_dir / name
        dest.write_bytes(src.read_bytes())
        files.append(str(dest))
    files = [str(mail_dir / "message.eml"), str(mail_dir / "body.txt"), *files]
    (mail_dir / "message.eml").write_bytes(b"From: test\n")
    (mail_dir / "body.txt").write_text("hi", encoding="utf-8")

    msg = SavedEmail(
        uid="99",
        subject="VISA application",
        sender="applicant@example.com",
        received_at="Sat, 14 Nov 2026 10:00:00 +0000",
        files=tuple(files),
    )
    report = process_email_message(
        msg,
        settings=offline_settings,
        submission_date=date(2026, 11, 16),
    )
    assert report["application_id"]
    assert "flight_booking" in report["llama_extract"]["docs"]
    assert "travel_insurance" in report["llama_extract"]["docs"]
    assert report["audit"]["outcome"] in {
        "READY_FOR_APPROVAL",
        "SEND_BACK",
        "NEEDS_GLORIA",
    }
    # Missing hotel/bank/passport etc → not a full READY usually; still produced results
    assert isinstance(report["audit"]["results"], list)
    assert len(report["audit"]["results"]) >= 1
