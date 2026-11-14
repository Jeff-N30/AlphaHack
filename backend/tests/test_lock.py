"""Human lock: tokens, actions, AST scan (no outbound in extract/rules/drafts)."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from app.config import Settings
from app.lock.actions import LockError, approve_application, send_draft
from app.lock.audit_log import read_audit_log
from app.lock.tokens import clear_tokens_for_tests, consume_confirm_token, issue_confirm_token
from app.storage.files import app_dir, create_application, save_meta

_APP = Path(__file__).resolve().parents[1] / "app"
_FORBIDDEN_IMPORTS = {"app.outbound", "app.lock"}


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


@pytest.mark.parametrize("pkg", ["extract", "rules", "drafts", "ingest", "audit_pipeline.py"])
def test_no_outbound_or_lock_imports(pkg: str) -> None:
    root = _APP / pkg
    paths = [root] if root.suffix == ".py" else list(root.rglob("*.py"))
    offenders: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        mods = _imports_of(path)
        for bad in _FORBIDDEN_IMPORTS:
            if any(m == bad or m.startswith(bad + ".") for m in mods):
                offenders.append(f"{path.relative_to(_APP)}: {bad}")
    assert offenders == [], "pipeline packages must not import lock/outbound:\n" + "\n".join(
        offenders
    )


def test_confirm_token_single_use(tmp_path: Path) -> None:
    clear_tokens_for_tests()
    row = issue_confirm_token(application_id="a1", action="approve", officer="Gloria")
    consume_confirm_token(row.token, application_id="a1", action="approve")
    with pytest.raises(Exception) as exc:
        consume_confirm_token(row.token, application_id="a1", action="approve")
    assert getattr(exc.value, "conflict", False) is True


def _smtp_settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        checklist_dir=Path(__file__).resolve().parents[2] / "checklists",
        email_imap_user="officer@gmail.com",
        email_imap_password="app-pass",
    )


def _fake_smtp(monkeypatch) -> None:
    def _send(**kwargs):
        to = kwargs.get("to_address") or ""
        return {
            "channel": "email",
            "delivered": True,
            "to": "karim@example.com" if "karim" in to else to.lower(),
            "application_id": kwargs["application_id"],
            "officer": kwargs["officer"],
            "body_chars": len(kwargs["body"]),
            "note": "Sent by Gloria confirm (SMTP).",
        }

    monkeypatch.setattr("app.outbound.deliver.deliver_email", _send)


def test_approve_requires_token(tmp_path: Path, monkeypatch) -> None:
    clear_tokens_for_tests()
    _fake_smtp(monkeypatch)
    settings = _smtp_settings(tmp_path)
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    meta["status"] = "awaiting_gloria_approval"
    meta["applicant_email"] = "karim@example.com"
    save_meta(meta, settings)
    root = app_dir(meta["id"], settings)
    (root / "email_pipeline_report.json").write_text(
        '{"audit":{"drafts":[{"id":"ready1","body":"Your pack looks complete.","status":"DRAFT","rule_ids":[]}]}}',
        encoding="utf-8",
    )
    tok = issue_confirm_token(application_id=meta["id"], action="approve")
    out = approve_application(
        meta["id"], confirm_token=tok.token, officer="Gloria", settings=settings
    )
    assert out["meta"]["status"] == "approved_by_gloria"
    assert out["delivery"]["channel"] == "email"
    log = read_audit_log(settings)
    assert any(r["action"] == "approve" and r["application_id"] == meta["id"] for r in log)
    with pytest.raises(LockError):
        approve_application(
            meta["id"], confirm_token=tok.token, officer="Gloria", settings=settings
        )


def test_send_draft_writes_audit(tmp_path: Path, monkeypatch) -> None:
    clear_tokens_for_tests()
    _fake_smtp(monkeypatch)
    settings = _smtp_settings(tmp_path)
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    save_meta(meta, settings)
    root = app_dir(meta["id"], settings)
    (root / "email_pipeline_report.json").write_text(
        '{"audit":{"drafts":[{"id":"d1","body":"Please send bank statement.","status":"DRAFT","rule_ids":["BANK.SUFFICIENT_FUNDS"]}]}}',
        encoding="utf-8",
    )
    tok = issue_confirm_token(application_id=meta["id"], action="send_back")
    out = send_draft(
        meta["id"],
        confirm_token=tok.token,
        officer="Gloria",
        draft_id="d1",
        to_email="karim@example.com",
        settings=settings,
    )
    assert out["meta"]["status"] == "sent_back_by_gloria"
    assert out["draft"]["status"] == "SENT"
    assert out["delivery"]["channel"] == "email"
    assert out["delivery"]["to"] == "karim@example.com"


def test_approve_sends_ready_draft(tmp_path: Path, monkeypatch) -> None:
    clear_tokens_for_tests()
    _fake_smtp(monkeypatch)
    settings = _smtp_settings(tmp_path)
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    meta["status"] = "awaiting_gloria_approval"
    meta["email_sender"] = "Applicant <karim@example.com>"
    save_meta(meta, settings)
    root = app_dir(meta["id"], settings)
    (root / "email_pipeline_report.json").write_text(
        '{"audit":{"drafts":[{"id":"ready1","body":"Your visa document pack looks complete.","status":"DRAFT","rule_ids":[]}]}}',
        encoding="utf-8",
    )
    tok = issue_confirm_token(application_id=meta["id"], action="approve")
    out = approve_application(
        meta["id"], confirm_token=tok.token, officer="Gloria", draft_id="ready1", settings=settings
    )
    assert out["meta"]["status"] == "approved_by_gloria"
    assert out["draft"]["status"] == "SENT"
    assert out["delivery"]["channel"] == "email"
    assert out["delivery"]["to"] == "karim@example.com"


def test_send_draft_fails_without_email(tmp_path: Path) -> None:
    clear_tokens_for_tests()
    settings = _smtp_settings(tmp_path)
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    save_meta(meta, settings)
    root = app_dir(meta["id"], settings)
    (root / "email_pipeline_report.json").write_text(
        '{"audit":{"drafts":[{"id":"d1","body":"Please send bank statement.","status":"DRAFT"}]}}',
        encoding="utf-8",
    )
    tok = issue_confirm_token(application_id=meta["id"], action="send_back")
    with pytest.raises(LockError, match="No applicant email"):
        send_draft(
            meta["id"], confirm_token=tok.token, officer="Gloria", draft_id="d1", settings=settings
        )
