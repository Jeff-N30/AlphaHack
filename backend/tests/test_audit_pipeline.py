"""Full audit path: ingest → extract → rules → Gloria queue status."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.audit_pipeline import audit_application
from app.config import Settings
from app.ingest.pipeline import seed_from_eval_case
from app.lock.tokens import clear_tokens_for_tests

_REPO = Path(__file__).resolve().parents[2]
_CASE01 = _REPO / "eval" / "cases" / "case01_complete"


@pytest.fixture()
def offline_settings(tmp_path: Path) -> Settings:
    clear_tokens_for_tests()
    return Settings(
        data_dir=tmp_path / "data",
        checklist_dir=_REPO / "checklists",
        demo_offline=True,
        extract_provider="ollama",
        extract_model="llama3.2",
        prompt_version="test-audit",
    )


@pytest.mark.skipif(not (_CASE01 / "docs" / "flight_booking.pdf").exists(), reason="run make docs")
def test_audit_application_puts_file_in_gloria_queue(offline_settings: Settings) -> None:
    aid = seed_from_eval_case(_CASE01, settings=offline_settings)
    report = audit_application(aid, settings=offline_settings)
    assert report["application_id"] == aid
    assert report["human_required"] is True
    assert report["human_status"].startswith("awaiting_gloria")
    assert report["audit"]["outcome"] in {
        "READY_FOR_APPROVAL",
        "SEND_BACK",
        "NEEDS_GLORIA",
    }
    assert "llama_extract" in report
    assert isinstance(report["audit"]["results"], list)
    assert len(report["audit"]["results"]) >= 1
    # Report persisted for desk
    from app.storage.files import app_dir, load_meta

    meta = load_meta(aid, offline_settings)
    assert meta["status"] == report["human_status"]
    assert meta["human_required"] is True
    path = app_dir(aid, offline_settings) / "email_pipeline_report.json"
    assert path.exists()
