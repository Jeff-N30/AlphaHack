"""Preview → classify (keywords / Llama) → MRZ when passport-like."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.extract.classify import classify_document
from app.extract.mrz import best_mrz
from app.ingest.render import DocumentPreview, allowed_suffix, read_preview
from app.models import DocType
from app.storage.files import app_dir, load_meta, save_meta


def _preview_to_dict(prev: DocumentPreview) -> dict[str, Any]:
    return {
        "path": str(prev.path),
        "method": prev.method,
        "error": prev.error,
        "text_len": len(prev.text),
        "text_preview": prev.text[:500],
        "pages": [
            {
                "page": p.page,
                "method": p.method,
                "char_count": p.char_count,
                "text_preview": p.text[:300],
            }
            for p in prev.pages
        ],
    }


def process_application(
    application_id: str,
    *,
    settings: Settings | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    meta = load_meta(application_id, settings)
    root = app_dir(application_id, settings)
    raw = root / "raw"
    max_pages = max_pages or settings.max_pages_per_doc

    files_out: list[dict[str, Any]] = []
    for path in sorted(raw.iterdir()):
        if not path.is_file():
            continue
        if not allowed_suffix(path):
            files_out.append(
                {
                    "file": path.name,
                    "rejected": True,
                    "reason": "unsupported_type",
                }
            )
            continue

        prev = read_preview(path, max_pages=max_pages)
        classified = classify_document(prev.text, filename=path.name, settings=settings)
        entry: dict[str, Any] = {
            "file": path.name,
            "rejected": False,
            "preview": _preview_to_dict(prev),
            "classification": classified.model_dump(mode="json"),
        }

        if classified.doc_type == DocType.passport or path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            # Try MRZ on images; also when classifier says passport
            if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                mrz = best_mrz(path, llm_lines=None)
                if mrz is not None:
                    entry["mrz"] = mrz.model_dump(mode="json")
                elif classified.doc_type == DocType.passport:
                    entry["mrz"] = None
                    entry["mrz_note"] = "checksums_failed_or_unreadable"

        files_out.append(entry)

    report = {
        "application_id": application_id,
        "checklist_id": meta.get("checklist_id"),
        "submission_date": meta.get("submission_date"),
        "files": files_out,
        "note": "preview + classify (keywords/llama) + MRZ",
    }
    (root / "ingest_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    meta["status"] = "ingested"
    meta["last_run"] = date.today().isoformat()
    save_meta(meta, settings)
    return report


def seed_from_eval_case(
    case_dir: Path,
    *,
    checklist_id: str = "fr-schengen-short-stay",
    settings: Settings | None = None,
) -> str:
    """Copy eval/cases/<case>/docs into a new application (for local demo)."""
    from datetime import date as date_cls

    import yaml

    from app.storage.files import create_application, store_upload

    settings = settings or get_settings()
    case = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
    sub = case.get("submission_date", "2026-11-16")
    if isinstance(sub, str):
        sub_d = date_cls.fromisoformat(sub)
    else:
        sub_d = sub
    meta = create_application(
        checklist_id=case.get("destination_checklist", checklist_id),
        submission_date=sub_d,
        settings=settings,
    )
    docs = case_dir / "docs"
    for f in sorted(docs.iterdir()):
        if f.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}:
            continue
        store_upload(meta["id"], f.name, f.read_bytes(), settings=settings)
    return meta["id"]
