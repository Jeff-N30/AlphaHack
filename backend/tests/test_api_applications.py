"""Gloria queue list/detail/action helpers."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from app.api_applications import get_application_detail, list_applications, mark_gloria_action
from app.config import Settings
from app.storage.files import create_application, save_meta


def test_list_and_gloria_action(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, checklist_dir=Path(__file__).resolve().parents[2] / "checklists")
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    meta["status"] = "awaiting_gloria_approval"
    meta["human_required"] = True
    meta["outcome"] = "READY_FOR_APPROVAL"
    save_meta(meta, settings)

    rows = list_applications(settings)
    row = next(r for r in rows if r["id"] == meta["id"])
    assert row["applicant_name"] is None  # no extract yet
    detail = get_application_detail(meta["id"], settings)
    assert detail["meta"]["id"] == meta["id"]

    updated = mark_gloria_action(meta["id"], action="approve", officer="Gloria", settings=settings)
    assert updated["status"] == "approved_by_gloria"
    assert updated["human_required"] is False
