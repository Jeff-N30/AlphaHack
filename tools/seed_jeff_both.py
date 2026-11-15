#!/usr/bin/env python3
"""Keep original Jeff (eb09659c3feb) and seed a second Dec-2026 file.

  .venv/bin/python tools/seed_jeff_both.py
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tools"))

from generate_fake_docs import pdf, render_photo  # noqa: E402
import yaml  # noqa: E402

from app.audit_pipeline import audit_application  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.storage.files import (  # noqa: E402
    create_application,
    load_meta,
    save_meta,
    store_upload,
)

ORIG_APP = "eb09659c3feb"
PACK = ROOT / "data" / "jeff_demo_pack"
PACK_DEC = ROOT / "data" / "jeff_demo_pack_dec"
CASE_DEC = ROOT / "data" / "jeff_demo_case" / "case.yaml"

DOC_EXTS = {".pdf", ".png", ".jpg", ".jpeg"}


def _wipe_raw(raw: Path, *, keep: set[str]) -> None:
    if not raw.exists():
        return
    for p in list(raw.iterdir()):
        if p.is_file() and p.name not in keep:
            p.unlink()


def _sync_meta_files(aid: str, settings) -> None:
    raw = settings.data_dir / "applications" / aid / "raw"
    meta = load_meta(aid, settings)
    meta["files"] = [
        {"name": f.name, "bytes": f.stat().st_size}
        for f in sorted(raw.iterdir())
        if f.is_file() and f.suffix.lower() in DOC_EXTS
    ]
    save_meta(meta, settings)


def restore_original_jeff(settings) -> None:
    """Seed/refresh Jeff original from data/jeff_demo_pack (stable on disk)."""
    if not PACK.exists() or not any(PACK.iterdir()):
        raise SystemExit(f"missing pack {PACK}")
    raw = settings.data_dir / "applications" / ORIG_APP / "raw"
    if not (settings.data_dir / "applications" / ORIG_APP / "meta.json").exists():
        create_application(
            checklist_id="fr-schengen-short-stay",
            submission_date=date(2026, 11, 15),
            settings=settings,
            application_id=ORIG_APP,
        )
    raw.mkdir(parents=True, exist_ok=True)
    _wipe_raw(raw, keep=set())
    for src in sorted(PACK.iterdir()):
        if src.is_file() and src.suffix.lower() in DOC_EXTS:
            shutil.copy2(src, raw / src.name)
            print("restore", src.name)

    meta = load_meta(ORIG_APP, settings)
    meta["demo_label"] = "Jeff Nader"
    meta["case_id"] = "jeff_original"
    meta["submission_date"] = "2026-11-15"
    meta["status"] = "awaiting_gloria_review"
    meta.pop("human_action", None)
    save_meta(meta, settings)
    _sync_meta_files(ORIG_APP, settings)

    print(f"auditing original {ORIG_APP} …")
    report = audit_application(ORIG_APP, settings=settings, case_id="jeff_original")
    audit = report.get("audit") or {}
    print("  outcome", audit.get("outcome"))
    for r in audit.get("results") or []:
        st = (r.get("status") or "").upper()
        if st != "PASS":
            print(f"  {st:12} {r.get('rule_id')}")
    _write_report(ORIG_APP, settings, audit, "jeff_original")


def build_dec_pack() -> Path:
    """Regenerate Dec-2026 pack into jeff_demo_pack_dec (does not touch original)."""
    case = yaml.safe_load(CASE_DEC.read_text(encoding="utf-8"))
    PACK_DEC.mkdir(parents=True, exist_ok=True)
    for p in list(PACK_DEC.iterdir()):
        if p.is_file():
            p.unlink()
    # Passport scan from Jeff pack
    # Passport only from scans — national ID is not on the FR checklist.
    for name in ("passport.jpeg",):
        src = PACK / name
        if not src.exists():
            src = ROOT / "data" / "applications" / ORIG_APP / "raw" / name
        if src.exists():
            shutil.copy2(src, PACK_DEC / name)
            print("dec keep", name)
    # One real Jeff ID photo, duplicated as photo_2 (checklist wants 2).
    src_photo = PACK / "photo.png"
    if not src_photo.exists() or src_photo.stat().st_size < 20_000:
        render_photo(src_photo)
        print("wrote specimen photo.png into pack")
    shutil.copy2(src_photo, PACK_DEC / "photo.png")
    shutil.copy2(src_photo, PACK_DEC / "photo_2.png")
    print("dec photo.png + photo_2.png (same Jeff photo ×2)")
    for dtype, spec in case["documents"].items():
        for d in spec if isinstance(spec, list) else [spec]:
            out = PACK_DEC / d["file"]
            pdf(dtype, d, out)
            print("dec wrote", out.name)
    return PACK_DEC


def seed_dec_app(settings) -> str:
    pack = build_dec_pack()
    meta = create_application(
        checklist_id="fr-schengen-short-stay",
        submission_date=date(2026, 11, 15),
        settings=settings,
    )
    aid = meta["id"]
    for f in sorted(pack.iterdir()):
        if f.is_file() and f.suffix.lower() in DOC_EXTS:
            store_upload(aid, f.name, f.read_bytes(), settings=settings)
            print("upload", f.name)
    m = load_meta(aid, settings)
    m["demo_label"] = "Jeff Nader · Dec 2026"
    m["case_id"] = "jeff_demo"
    m["status"] = "awaiting_gloria_review"
    save_meta(m, settings)
    print(f"auditing Dec file {aid} …")
    report = audit_application(aid, settings=settings, case_id="jeff_demo")
    audit = report.get("audit") or {}
    print("  outcome", audit.get("outcome"))
    for r in audit.get("results") or []:
        st = (r.get("status") or "").upper()
        if st != "PASS":
            print(f"  {st:12} {r.get('rule_id')}")
    _write_report(aid, settings, audit, "jeff_demo")
    return aid


def _write_report(aid: str, settings, audit: dict, case_id: str) -> None:
    path = settings.data_dir / "applications" / aid / "email_pipeline_report.json"
    blob = json.loads(path.read_text()) if path.exists() else {"application_id": aid}
    blob["audit"] = audit
    blob["case_id"] = case_id
    path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    settings = get_settings()
    restore_original_jeff(settings)
    aid = seed_dec_app(settings)
    print(f"\nDONE original={ORIG_APP}  dec={aid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
