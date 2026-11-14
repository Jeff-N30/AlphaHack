"""schemas/models.py is the source of truth; backend/app/models.py must match."""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def test_models_identical_to_schemas() -> None:
    schema = (_REPO / "schemas" / "models.py").read_text(encoding="utf-8")
    app_copy = (_REPO / "backend" / "app" / "models.py").read_text(encoding="utf-8")
    assert schema == app_copy, (
        "backend/app/models.py drifted from schemas/models.py — re-copy the schema file"
    )
