"""Gloria queue list/detail + file preview helpers."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from app.api_applications import get_application_detail, list_applications, resolve_application_file
from app.config import Settings
from app.lock.actions import approve_application
from app.lock.tokens import clear_tokens_for_tests, issue_confirm_token
from app.storage.files import app_dir, create_application, save_meta


def test_list_and_gloria_action(tmp_path: Path) -> None:
    clear_tokens_for_tests()
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

    tok = issue_confirm_token(application_id=meta["id"], action="approve")
    updated = approve_application(
        meta["id"], confirm_token=tok.token, officer="Gloria", settings=settings
    )
    assert updated["status"] == "approved_by_gloria"
    assert updated["human_required"] is False


def test_resolve_application_file(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, checklist_dir=Path(__file__).resolve().parents[2] / "checklists")
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    raw = app_dir(meta["id"], settings) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "bank_statement.pdf").write_bytes(b"%PDF-1.4 demo")
    path = resolve_application_file(meta["id"], "bank_statement.pdf", settings=settings)
    assert path.name == "bank_statement.pdf"
