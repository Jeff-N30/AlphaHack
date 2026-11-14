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


@pytest.mark.parametrize("pkg", ["extract", "rules", "drafts"])
def test_no_outbound_or_lock_imports(pkg: str) -> None:
    root = _APP / pkg
    offenders: list[str] = []
    for path in root.rglob("*.py"):
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


def test_approve_requires_token(tmp_path: Path) -> None:
    clear_tokens_for_tests()
    settings = Settings(data_dir=tmp_path, checklist_dir=Path(__file__).resolve().parents[2] / "checklists")
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    meta["status"] = "awaiting_gloria_approval"
    save_meta(meta, settings)
    tok = issue_confirm_token(application_id=meta["id"], action="approve")
    updated = approve_application(
        meta["id"], confirm_token=tok.token, officer="Gloria", settings=settings
    )
    assert updated["status"] == "approved_by_gloria"
    log = read_audit_log(settings)
    assert any(r["action"] == "approve" and r["application_id"] == meta["id"] for r in log)
    with pytest.raises(LockError):
        approve_application(
            meta["id"], confirm_token=tok.token, officer="Gloria", settings=settings
        )


def test_send_draft_writes_audit(tmp_path: Path) -> None:
    clear_tokens_for_tests()
    settings = Settings(data_dir=tmp_path, checklist_dir=Path(__file__).resolve().parents[2] / "checklists")
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 16),
        settings=settings,
    )
    root = app_dir(meta["id"], settings)
    (root / "email_pipeline_report.json").write_text(
        '{"audit":{"drafts":[{"id":"d1","body":"Please send bank statement.","status":"DRAFT","rule_ids":["BANK.SUFFICIENT_FUNDS"]}]}}',
        encoding="utf-8",
    )
    tok = issue_confirm_token(application_id=meta["id"], action="send_back")
    out = send_draft(
        meta["id"], confirm_token=tok.token, officer="Gloria", draft_id="d1", settings=settings
    )
    assert out["meta"]["status"] == "sent_back_by_gloria"
    assert out["draft"]["status"] == "SENT"
    assert out["delivery"]["channel"] == "copy"
