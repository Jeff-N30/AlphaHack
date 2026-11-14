"""HTTP intake slice."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

_REPO = Path(__file__).resolve().parents[2]
_CASE01 = _REPO / "eval" / "cases" / "case01_complete" / "docs"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("DATA_DIR", str(data))
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_checklists(client: TestClient) -> None:
    r = client.get("/checklists")
    assert r.status_code == 200
    ids = {x["id"] for x in r.json()}
    assert "fr-schengen-short-stay" in ids


def test_upload_and_run(client: TestClient) -> None:
    passport = _CASE01 / "passport.png"
    bank = _CASE01 / "bank_statement.pdf"
    if not passport.exists():
        pytest.skip("run: python tools/generate_fake_docs.py")
    files = [
        ("files", ("passport.png", passport.read_bytes(), "image/png")),
        ("files", ("bank_statement.pdf", bank.read_bytes(), "application/pdf")),
    ]
    r = client.post(
        "/applications",
        data={"checklist_id": "fr-schengen-short-stay", "submission_date": "2026-11-16"},
        files=files,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"]
    assert "passport.png" in body["files"]

    run = client.post(f"/applications/{body['id']}/run")
    assert run.status_code == 200, run.text
    report = run.json()
    assert any(f.get("mrz") and f["mrz"]["checksums_valid"] for f in report["files"])
