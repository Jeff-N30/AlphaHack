"""Append-only audit_log for lock actions (JSONL under DATA_DIR)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings


def append_audit_log(
    *,
    officer: str,
    action: str,
    application_id: str,
    body: str | None = None,
    extra: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path = settings.data_dir / "audit_log.jsonl"
    row: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "officer": officer,
        "action": action,
        "application_id": application_id,
        "body_sha256": hashlib.sha256((body or "").encode("utf-8")).hexdigest() if body is not None else None,
    }
    if extra:
        row.update(extra)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    return row


def read_audit_log(settings: Settings | None = None, *, limit: int = 100) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    path = settings.data_dir / "audit_log.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        if line.strip():
            out.append(json.loads(line))
    return out
