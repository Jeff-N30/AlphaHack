#!/usr/bin/env python3
"""Run an edge-case demo pack into Gloria's queue — Jeff stays untouched.

Each edge case:
  data/edge_cases/<id>/case.yaml   — demo_label + which file to swap
  data/edge_cases/<id>/docs/       — edge passport (etc.)

Queue name = meta.demo_label (never a second \"JEFF NADER\").

Usage:
  .venv/bin/python tools/run_edge_case.py edge01_mrz_checksum
  .venv/bin/python tools/run_edge_case.py --list
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.audit_pipeline import audit_application  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.storage.files import create_application, load_meta, save_meta, store_upload  # noqa: E402

EDGES = ROOT / "data" / "edge_cases"
JEFF_PACK = ROOT / "data" / "jeff_demo_pack"
JEFF_APP = ROOT / "data" / "applications" / "eb09659c3feb" / "raw"


def _base_pack() -> Path:
    if JEFF_PACK.exists() and any(JEFF_PACK.iterdir()):
        return JEFF_PACK
    if JEFF_APP.exists():
        return JEFF_APP
    raise SystemExit("No jeff_demo_pack or Jeff application raw/ found")


def list_edges() -> None:
    if not EDGES.exists():
        print("no data/edge_cases yet")
        return
    for d in sorted(EDGES.iterdir()):
        if not d.is_dir() or not (d / "case.yaml").exists():
            continue
        case = yaml.safe_load((d / "case.yaml").read_text(encoding="utf-8"))
        print(f"{d.name:28}  {case.get('demo_label', '')}")


def run_edge(edge_id: str) -> str:
    case_dir = EDGES / edge_id
    case_path = case_dir / "case.yaml"
    if not case_path.exists():
        raise SystemExit(f"unknown edge case: {edge_id}")

    case = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    label = str(case.get("demo_label") or f"EDGE · {edge_id}").strip()
    settings = get_settings()
    base = _base_pack()

    meta = create_application(
        checklist_id=case.get("destination_checklist", "fr-schengen-short-stay"),
        submission_date=date.fromisoformat(str(case.get("submission_date", "2026-11-15"))),
        settings=settings,
    )
    aid = meta["id"]

    # Copy full supporting pack (Jeff), then overwrite swapped files
    for f in sorted(base.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}:
            continue
        store_upload(aid, f.name, f.read_bytes(), settings=settings)

    swap = case.get("swap") or {}
    for dest_name, rel in swap.items():
        src = case_dir / rel
        if not src.exists():
            raise SystemExit(f"swap missing: {src}")
        # Always land as passport.jpeg / insurance.pdf etc.
        out_name = {
            "passport": "passport.jpeg",
            "travel_insurance": "travel_insurance.pdf",
            "flight_booking": "flight_booking.pdf",
            "hotel_booking": "hotel_booking.pdf",
            "bank_statement": "bank_statement.pdf",
            "photo": "photo.png",
        }.get(dest_name, Path(rel).name)
        raw = Path(settings.data_dir) / "applications" / aid / "raw"
        # Replace in place so filename stays stable for classify
        target = raw / out_name
        if target.exists():
            target.unlink()
        shutil.copy2(src, target)
        # Keep meta.files in sync
        m = load_meta(aid, settings)
        files = [x for x in (m.get("files") or []) if x.get("name") != out_name]
        files.append({"name": out_name, "bytes": target.stat().st_size})
        m["files"] = files
        save_meta(m, settings)
        print(f"  swapped {out_name} ← {src.name}")

    m = load_meta(aid, settings)
    m["demo_label"] = label
    m["case_id"] = case.get("case_id", edge_id)
    m["edge_case"] = edge_id
    save_meta(m, settings)

    print(f"auditing {aid} as {label!r} …")
    report = audit_application(aid, settings=settings, case_id=str(case.get("case_id", edge_id)))
    audit = report.get("audit") or {}
    outcome = audit.get("outcome")
    results = audit.get("results") or []
    expected = set(case.get("expected_flags") or [])
    hit = {
        r.get("rule_id")
        for r in results
        if (r.get("status") or "").upper() in {"FAIL", "NEEDS_HUMAN"}
        and r.get("rule_id") in expected
    }
    print(f"outcome={outcome}")
    for rid in sorted(expected):
        print(f"  expected {rid}: {'HIT' if rid in hit else 'MISS'}")
    print(f"queue label: {label}")
    print(f"application: {aid}")
    return aid


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("edge_id", nargs="?", help="e.g. edge01_mrz_checksum")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list or not args.edge_id:
        list_edges()
        return 0 if args.list or not args.edge_id else 1
    run_edge(args.edge_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
