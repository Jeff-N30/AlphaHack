"""Upload path: store files → audit_application → Gloria queue."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.audit_pipeline import audit_application
from app.config import Settings
from app.storage.files import create_application, load_meta, store_upload

_REPO = Path(__file__).resolve().parents[2]
_CASE01 = _REPO / "eval" / "cases" / "case01_complete" / "docs"


@pytest.mark.skipif(not (_CASE01 / "flight_booking.pdf").exists(), reason="run make docs")
def test_upload_then_audit_lands_in_queue(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        checklist_dir=_REPO / "checklists",
        demo_offline=True,
        extract_provider="ollama",
        extract_model="llama3.2",
        prompt_version="test-upload",
    )
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    aid = meta["id"]
    for name in ("flight_booking.pdf", "travel_insurance.pdf", "cnss_certificate.pdf"):
        src = _CASE01 / name
        if not src.exists():
            continue
        store_upload(aid, name, src.read_bytes(), settings=settings)

    report = audit_application(aid, settings=settings)
    assert report["application_id"] == aid
    assert report["human_status"].startswith("awaiting_gloria")
    assert report["audit"]["outcome"] in {
        "READY_FOR_APPROVAL",
        "SEND_BACK",
        "NEEDS_GLORIA",
    }
    saved = load_meta(aid, settings)
    assert saved["status"] == report["human_status"]
    # CNSS generic extract should land when file present
    docs = (report.get("llama_extract") or {}).get("docs") or {}
    if (_CASE01 / "cnss_certificate.pdf").exists():
        assert "cnss_certificate" in docs
