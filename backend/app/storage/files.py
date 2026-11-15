"""Local application file storage under DATA_DIR/applications/<id>/."""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.storage.db import (
    redact_application_sensitive_data,
    register_application,
    register_document,
)

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
    register_application(meta, settings)
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
    register_document(
        application_id=application_id,
        filename=filename,
        path=dest,
        data=data,
        settings=settings,
    )
    meta = load_meta(application_id, settings)
    meta.setdefault("files", []).append({"name": dest.name, "bytes": len(data)})
    save_meta(meta, settings)
    return dest


def redact_application(
    application_id: str,
    *,
    officer: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Delete source documents/reports and retain only non-sensitive metadata."""
    settings = settings or get_settings()
    meta = load_meta(application_id, settings)
    root = app_dir(application_id, settings)
    # Keep only meta.json, which is rewritten below with the non-sensitive
    # decision record. This also covers future reports/traces added to the
    # application directory without requiring another retention allowlist.
    deleted_files = 0
    for path in root.iterdir():
        if path.name == "meta.json":
            continue
        if path.is_dir():
            deleted_files += sum(1 for child in path.rglob("*") if child.is_file())
            shutil.rmtree(path)
        else:
            path.unlink()
            deleted_files += 1

    deleted_rows = redact_application_sensitive_data(application_id, settings)
    for key in (
        "applicant_email",
        "email_sender",
        "sender",
        "triage_person_name",
        "last_delivery",
    ):
        meta.pop(key, None)
    meta["files"] = []
    meta["sensitive_data_redacted"] = True
    meta["sensitive_data_redacted_by"] = officer
    meta["sensitive_data_redacted_at"] = datetime.now(timezone.utc).isoformat()
    save_meta(meta, settings)
    return {
        "meta": meta,
        "deleted_files": deleted_files,
        "deleted_database_rows": deleted_rows,
    }


def complete_application(
    application_id: str,
    *,
    officer: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Permanently remove sensitive data and retain a completed decision record."""
    settings = settings or get_settings()
    result = redact_application(application_id, officer=officer, settings=settings)
    meta = result["meta"]
    meta["status"] = "completed"
    meta["completed_by"] = officer
    meta["completed_at"] = datetime.now(timezone.utc).isoformat()
    save_meta(meta, settings)
    result["meta"] = meta
    return result
