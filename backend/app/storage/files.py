"""Local application file storage under DATA_DIR/applications/<id>/."""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def new_application_id() -> str:
    return uuid.uuid4().hex[:12]


def app_dir(application_id: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.data_dir / "applications" / application_id


def raw_dir(application_id: str, settings: Settings | None = None) -> Path:
    return app_dir(application_id, settings) / "raw"


def safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = _SAFE.sub("_", base).strip("._") or "file"
    return cleaned[:180]


def create_application(
    *,
    checklist_id: str,
    submission_date: date,
    settings: Settings | None = None,
    application_id: str | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    aid = application_id or new_application_id()
    root = app_dir(aid, settings)
    raw_dir(aid, settings).mkdir(parents=True, exist_ok=True)
    meta = {
        "id": aid,
        "checklist_id": checklist_id,
        "submission_date": submission_date.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": [],
        "status": "created",
    }
    (root / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load_meta(application_id: str, settings: Settings | None = None) -> dict[str, Any]:
    path = app_dir(application_id, settings) / "meta.json"
    if not path.exists():
        raise FileNotFoundError(application_id)
    return json.loads(path.read_text(encoding="utf-8"))


def save_meta(meta: dict[str, Any], settings: Settings | None = None) -> None:
    aid = meta["id"]
    path = app_dir(aid, settings) / "meta.json"
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def store_upload(
    application_id: str,
    filename: str,
    data: bytes,
    settings: Settings | None = None,
) -> Path:
    settings = settings or get_settings()
    dest_dir = raw_dir(application_id, settings)
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = safe_filename(filename)
    dest = dest_dir / name
    if dest.exists():
        stem, suf = dest.stem, dest.suffix
        dest = dest_dir / f"{stem}_{uuid.uuid4().hex[:6]}{suf}"
    dest.write_bytes(data)
    meta = load_meta(application_id, settings)
    meta.setdefault("files", []).append({"name": dest.name, "bytes": len(data)})
    save_meta(meta, settings)
    return dest
