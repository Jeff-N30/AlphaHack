"""Preview + keyword classify + seed pipeline on fake docs."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.ingest.classify_keywords import classify_text
from app.ingest.pipeline import process_application, seed_from_eval_case
from app.ingest.render import read_preview
from app.models import DocType

_REPO = Path(__file__).resolve().parents[2]
_CASE01 = _REPO / "eval" / "cases" / "case01_complete" / "docs"


@pytest.fixture()
def tmp_settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", checklist_dir=_REPO / "checklists")


def test_pdf_text_preview_bank() -> None:
    path = _CASE01 / "bank_statement.pdf"
    if not path.exists():
        pytest.skip("run: python tools/generate_fake_docs.py")
    prev = read_preview(path)
    assert prev.error is None
    assert prev.method == "pdf_text"
    assert "ACCOUNT STATEMENT" in prev.text.upper() or "STATEMENT" in prev.text.upper()


def test_classify_bank_from_text() -> None:
    path = _CASE01 / "bank_statement.pdf"
    if not path.exists():
        pytest.skip("run: python tools/generate_fake_docs.py")
    prev = read_preview(path)
    c = classify_text(prev.text, filename="bank_statement.pdf")
    assert c.doc_type == DocType.bank_statement
    assert c.confidence >= 0.55


def test_classify_ekhraj_translation_doc() -> None:
    path = _CASE01 / "family_register.pdf"
    if not path.exists():
        pytest.skip("run: python tools/generate_fake_docs.py")
    prev = read_preview(path)
    c = classify_text(prev.text, filename="family_register.pdf")
    assert c.doc_type == DocType.family_register


def test_seed_and_run_mrz(tmp_settings: Settings) -> None:
    case = _REPO / "eval" / "cases" / "case01_complete"
    if not (case / "docs" / "passport.png").exists():
        pytest.skip("run: python tools/generate_fake_docs.py")
    aid = seed_from_eval_case(case, settings=tmp_settings)
    report = process_application(aid, settings=tmp_settings)
    assert report["application_id"] == aid
    passports = [f for f in report["files"] if f.get("file") == "passport.png"]
    assert passports, report["files"]
    mrz = passports[0].get("mrz")
    assert mrz is not None
    assert mrz["checksums_valid"] is True
    assert mrz["surname"] == "NASSAR"
