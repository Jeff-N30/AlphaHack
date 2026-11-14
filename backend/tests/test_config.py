"""Settings must be stable regardless of process CWD."""
from __future__ import annotations

import os
from pathlib import Path

from app.config import Settings, get_settings

_REPO = Path(__file__).resolve().parents[2]


def test_paths_anchor_to_repo_root(tmp_path: Path, monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.chdir(tmp_path)
    s = Settings()
    assert s.data_dir == (_REPO / "data").resolve()
    assert s.checklist_dir == (_REPO / "checklists").resolve()
    assert s.database_url.startswith("sqlite:///")
    assert s.database_url.endswith(str(s.data_dir / "visaref.db"))
    get_settings.cache_clear()


def test_get_settings_cached() -> None:
    get_settings.cache_clear()
    a = get_settings()
    b = get_settings()
    assert a is b
    get_settings.cache_clear()
