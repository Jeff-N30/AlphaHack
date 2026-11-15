"""Preview → classify (keywords / Llama) → MRZ when passport-like."""
from __future__ import annotations

import json
import logging
import re
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.extract.classify import classify_document
from app.extract.mrz import best_mrz
from app.ingest.render import DocumentPreview, allowed_suffix, read_preview, render_page_png
from app.models import DocType, MRZ
from app.storage.files import app_dir, load_meta, save_meta
from app.trace.recorder import record as trace_record
from app.trace.recorder import span as trace_span

logger = logging.getLogger(__name__)


def _ocr_mrz_lines(text: str) -> list[str] | None:
    """Pull TD3-looking lines from OCR (spaces stripped) for MRZ fallback."""
    if not text:
        return None
    compact = re.sub(r"\s+", "", text.upper().replace("«", "<").replace("‹", "<"))
    # Prefer explicit TD3 pair: P<… then passport-number line
    m = re.search(
        r"(P<[A-Z0-9<]{42,})(LR[A-Z0-9<]{40,}|[A-Z0-9]{9}[A-Z0-9<]{30,})",
        compact,
    )
    if m:
        return [m.group(1)[:44].ljust(44, "<"), m.group(2)[:44].ljust(44, "<")]
    lines: list[str] = []
    for raw in text.splitlines():
        c = re.sub(r"\s+", "", raw.upper().replace("«", "<").replace("‹", "<"))
        if c.startswith("P<") and len(c) >= 40:
            lines.append(c[:44].ljust(44, "<"))
        elif re.match(r"^[A-Z0-9<]{40,}$", c) and len(c) >= 40:
            lines.append(c[:44].ljust(44, "<"))
    if len(lines) >= 2:
        return lines[:2]
    if compact.startswith("P<") and len(compact) >= 88:
        return [compact[:44].ljust(44, "<"), compact[44:88].ljust(44, "<")]
    return None


def _mrz_for_file(path: Path, *, preview_text: str = "") -> MRZ | None:
    """Run MRZ on image path, or rasterize PDF page 1 first."""
    ocr_lines = _ocr_mrz_lines(preview_text)
    suffix = path.suffix.lower()
    try:
        if suffix in {".png", ".jpg", ".jpeg"}:
            return best_mrz(path, llm_lines=ocr_lines)
        if suffix == ".pdf":
            png = render_page_png(path, page=1)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                tmp_path.write_bytes(png)
                return best_mrz(tmp_path, llm_lines=ocr_lines)
            finally:
                tmp_path.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MRZ failed on %s: %s", path.name, exc)
        if ocr_lines:
            return best_mrz(None, llm_lines=ocr_lines)
    if ocr_lines:
        return best_mrz(None, llm_lines=ocr_lines)
    return None


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
    with trace_span("stage:ingest", label="Ingest documents") as out:
        report = _process_application(application_id, settings=settings, max_pages=max_pages)
        files = report.get("files") or []
        out["files"] = len(files)
        out["rejected"] = sum(1 for f in files if f.get("rejected"))
        out["mrz_found"] = sum(1 for f in files if f.get("mrz"))
        return report


def _process_application(
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
            trace_record(
                f"file:{path.name}",
                label=path.name,
                status="skipped",
                inputs={"file": path.name},
                outputs={"rejected": True, "reason": "unsupported_type"},
            )
            continue

        f_started = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()
        prev = read_preview(path, max_pages=max_pages)
        t1 = time.perf_counter()
        classified = classify_document(prev.text, filename=path.name, settings=settings)
        t2 = time.perf_counter()
        t3 = t2
        entry: dict[str, Any] = {
            "file": path.name,
            "rejected": False,
            "preview": _preview_to_dict(prev),
            "classification": classified.model_dump(mode="json"),
        }

        # MRZ only for passport-like files. Running it on insurance/forms picks up
        # random 44-char lines and poisons DOC.PRESENT / PP.MRZ_CHECKSUM.
        looks_like_passport = classified.doc_type == DocType.passport or (
            classified.doc_type == DocType.unknown
            and (
                "passport" in path.name.lower()
                or path.suffix.lower() in {".png", ".jpg", ".jpeg"}
            )
        )
        if looks_like_passport:
            # Passport PDFs must be rasterized — previously only PNG/JPG ran MRZ.
            mrz = _mrz_for_file(path, preview_text=prev.text or "")
            t3 = time.perf_counter()
            if mrz is not None:
                entry["mrz"] = mrz.model_dump(mode="json")
            elif classified.doc_type == DocType.passport:
                entry["mrz"] = None
                entry["mrz_note"] = "checksums_failed_or_unreadable"

        files_out.append(entry)
        cls_json = entry["classification"]
        trace_record(
            f"file:{path.name}",
            label=path.name,
            started_at=f_started,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=round((t3 - t0) * 1000, 3),
            inputs={"file": path.name, "bytes": path.stat().st_size, "max_pages": max_pages},
            outputs={
                "preview_method": prev.method,
                "pages": len(prev.pages),
                "chars": len(prev.text),
                "doc_type": cls_json.get("doc_type"),
                "classification": {k: cls_json.get(k) for k in ("method", "confidence") if k in cls_json},
                "mrz": "valid" if entry.get("mrz") else entry.get("mrz_note") if looks_like_passport else None,
                "timings_ms": {
                    "render_preview": round((t1 - t0) * 1000, 3),
                    "classify": round((t2 - t1) * 1000, 3),
                    **({"mrz": round((t3 - t2) * 1000, 3)} if looks_like_passport else {}),
                },
            },
            via=["op:render", "op:classify", *(["op:mrz"] if looks_like_passport else [])],
        )

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
