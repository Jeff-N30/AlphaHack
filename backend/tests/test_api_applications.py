"""Gloria queue list/detail + file preview helpers."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.api_applications import get_application_detail, list_applications, resolve_application_file
from app.config import Settings
from app.lock.actions import approve_application
from app.lock.tokens import clear_tokens_for_tests, issue_confirm_token
from app.storage.files import (
    app_dir,
    create_application,
    redact_application,
    save_meta,
    store_upload,
)


def test_list_and_gloria_action(tmp_path: Path, monkeypatch) -> None:
    clear_tokens_for_tests()
    settings = Settings(
        data_dir=tmp_path,
        checklist_dir=Path(__file__).resolve().parents[2] / "checklists",
        email_imap_user="officer@gmail.com",
        email_imap_password="app-pass",
    )
    monkeypatch.setattr(
        "app.outbound.deliver.deliver_email",
        lambda **kwargs: {
            "channel": "email",
            "delivered": True,
            "to": "karim@example.com",
            "application_id": kwargs["application_id"],
            "officer": kwargs["officer"],
            "body_chars": len(kwargs["body"]),
            "note": "Sent",
        },
    )
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    meta["status"] = "awaiting_gloria_approval"
    meta["human_required"] = True
    meta["outcome"] = "READY_FOR_APPROVAL"
    meta["applicant_email"] = "karim@example.com"
    save_meta(meta, settings)
    root = app_dir(meta["id"], settings)
    (root / "email_pipeline_report.json").write_text(
        '{"audit":{"drafts":[{"id":"d1","body":"Your pack looks complete.","status":"DRAFT"}]}}',
        encoding="utf-8",
    )

    rows = list_applications(settings)
    row = next(r for r in rows if r["id"] == meta["id"])
    assert row["applicant_name"] is None  # no extract yet
    detail = get_application_detail(meta["id"], settings)
    assert detail["meta"]["id"] == meta["id"]

    tok = issue_confirm_token(application_id=meta["id"], action="approve")
    out = approve_application(
        meta["id"], confirm_token=tok.token, officer="Gloria", settings=settings
    )
    assert out["meta"]["status"] == "approved_by_gloria"
    assert out["meta"]["human_required"] is False
    assert out["delivery"]["channel"] == "email"


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


def test_employee_sender_is_not_used_as_applicant_email(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        checklist_dir=Path(__file__).resolve().parents[2] / "checklists",
        email_imap_user="jeffnader30@gmail.com",
    )
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    meta["email_sender"] = "Jeff Nader <jeffnader30@gmail.com>"
    save_meta(meta, settings)

    row = next(r for r in list_applications(settings) if r["id"] == meta["id"])
    detail = get_application_detail(meta["id"], settings)

    assert row["applicant_email"] is None
    assert detail["meta"]["applicant_email"] is None


def test_sender_address_is_used_as_applicant_email(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        checklist_dir=Path(__file__).resolve().parents[2] / "checklists",
        email_imap_user="jeffnader30@gmail.com",
    )
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    meta["email_sender"] = "Jason Boulos <jason.boulos1990@gmail.com>"
    save_meta(meta, settings)

    detail = get_application_detail(meta["id"], settings)

    assert detail["meta"]["applicant_email"] == "jason.boulos1990@gmail.com"


def test_redact_keeps_approved_record_and_removes_sensitive_data(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        checklist_dir=Path(__file__).resolve().parents[2] / "checklists",
    )
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    meta.update(
        {
            "status": "approved_by_gloria",
            "applicant_email": "person@example.com",
            "triage_person_name": "Person",
        }
    )
    save_meta(meta, settings)
    store_upload(meta["id"], "passport.pdf", b"private", settings=settings)
    (app_dir(meta["id"], settings) / "email_pipeline_report.json").write_text(
        '{"passport":{"number":"secret"}}',
        encoding="utf-8",
    )

    result = redact_application(meta["id"], officer="Gloria", settings=settings)

    assert result["deleted_files"] == 2
    assert not (app_dir(meta["id"], settings) / "raw").exists()
    assert not (app_dir(meta["id"], settings) / "email_pipeline_report.json").exists()
    redacted = json.loads(
        (app_dir(meta["id"], settings) / "meta.json").read_text(encoding="utf-8")
    )
    assert redacted["id"] == meta["id"]
    assert redacted["status"] == "approved_by_gloria"
    assert "applicant_email" not in redacted
    assert redacted["sensitive_data_redacted"] is True
