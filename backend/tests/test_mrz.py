"""MRZ engine: ICAO checksums, image OCR, tamper detection."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.extract.mrz import best_mrz, compare_viz, parse_td3, read_mrz_image
from app.models import DocType, PassportExtraction

_REPO = Path(__file__).resolve().parents[2]
_CASES = _REPO / "eval" / "cases"


def _case_dirs() -> list[Path]:
    return sorted(p for p in _CASES.iterdir() if p.is_dir() and (p / "docs" / "passport_mrz.txt").exists())


def _truth_lines(case_dir: Path) -> list[str]:
    return (case_dir / "docs" / "passport_mrz.txt").read_text(encoding="utf-8").strip().splitlines()


@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_parse_td3_matches_passport_mrz_txt(case_dir: Path) -> None:
    lines = _truth_lines(case_dir)
    mrz = parse_td3(lines, today=date(2026, 11, 14))
    assert mrz.checksums_valid, mrz.failed_checks
    assert mrz.line1 == lines[0]
    assert mrz.line2 == lines[1]
    assert mrz.failed_checks == []


@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_passport_png_parses_and_matches_truth(case_dir: Path) -> None:
    png = case_dir / "docs" / "passport.png"
    assert png.exists()
    lines = _truth_lines(case_dir)
    # Production path: passporteye first, LLM lines as fallback (here: ground-truth transcription)
    mrz = best_mrz(png, llm_lines=lines, today=date(2026, 11, 14))
    assert mrz is not None
    assert mrz.checksums_valid, mrz.failed_checks
    assert mrz.line1 == lines[0]
    assert mrz.line2 == lines[1]


def test_tampered_expiry_digit_fails_checksum() -> None:
    case = _CASES / "case01_complete"
    lines = _truth_lines(case)
    l2 = list(lines[1])
    # expiry YYMMDD starts at index 21
    l2[22] = "0" if l2[22] != "0" else "1"
    tampered = [lines[0], "".join(l2)]
    mrz = parse_td3(tampered, today=date(2026, 11, 14))
    assert mrz.checksums_valid is False
    assert mrz.failed_checks  # at least one hash failed


def test_century_rules_dob_and_expiry() -> None:
    # DOB yy=94 > 26 → 1994; expiry always 20xx → 2032
    lines = [
        "P<LBNNASSAR<<KARIM<<<<<<<<<<<<<<<<<<<<<<<<<<",
        "LR04829131LBN9403121M3205091<<<<<<<<<<<<<<<6",
    ]
    mrz = parse_td3(lines, today=date(2026, 11, 14))
    assert mrz.checksums_valid
    assert mrz.date_of_birth == date(1994, 3, 12)
    assert mrz.expiry_date == date(2032, 5, 9)


def test_compare_viz_detects_mismatch() -> None:
    lines = _truth_lines(_CASES / "case01_complete")
    mrz = parse_td3(lines, today=date(2026, 11, 14))
    viz = PassportExtraction(
        doc_type=DocType.passport,
        surname="NASSAR",
        given_names="KARIM",
        passport_number="LR0482913",
        nationality="LBN",
        date_of_birth=date(1994, 3, 12),
        sex="M",
        issue_date=date(2022, 5, 9),
        expiry_date=date(2030, 1, 1),  # wrong vs MRZ
        mrz_lines=lines,
    )
    assert "expiry_date" in compare_viz(mrz, viz)


def test_passport_phone_jpg_case04() -> None:
    phone = _CASES / "case04_name_mismatch" / "docs" / "passport_phone.jpg"
    if not phone.exists():
        pytest.skip("passport_phone.jpg not generated — run tools/generate_fake_docs.py --degrade")
    lines = _truth_lines(_CASES / "case04_name_mismatch")
    mrz = best_mrz(phone, llm_lines=lines, today=date(2026, 11, 14))
    assert mrz is not None
    assert mrz.checksums_valid, mrz.failed_checks


def test_read_mrz_image_handles_missing() -> None:
    assert read_mrz_image("/nonexistent/passport.png") is None
