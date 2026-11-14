#!/usr/bin/env python3
"""Terminal demo for screen recording (30s): run one eval case end-to-end."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rules.checklist import load_checklist
from app.rules.engine import run
from app.rules.facts_from_case import facts_from_case
from app.extract.mrz import best_mrz


def main() -> None:
    case_id = sys.argv[1] if len(sys.argv) > 1 else "case05_wrong_dates"
    case_dir = ROOT / "eval" / "cases" / case_id
    print("=" * 56)
    print("  VisaRef agent demo — Lebanon → France Schengen")
    print("=" * 56)
    time.sleep(0.4)
    print(f"\n[1] Load case: {case_id}")
    passport = case_dir / "docs" / "passport.png"
    time.sleep(0.3)
    print("[2] Read passport MRZ (passporteye + ICAO checksums)…")
    mrz = best_mrz(passport)
    if mrz and mrz.checksums_valid:
        print(f"    OK  {mrz.surname} / {mrz.given_names}  {mrz.passport_number}")
    else:
        print("    MRZ needs human / failed")
    time.sleep(0.4)
    print("[3] Run checklist rules (code decides PASS/FAIL)…")
    t0 = time.perf_counter()
    report = run(load_checklist(ROOT / "checklists" / "fr-schengen-short-stay.yaml"), facts_from_case(case_dir))
    ms = (time.perf_counter() - t0) * 1000
    time.sleep(0.3)
    print(f"\n>>> OUTCOME: {report.outcome.value}")
    print(f"    escalations={report.escalations}  ({ms:.0f} ms)")
    print("\n    Non-PASS rules:")
    for r in report.results:
        if r.mode == "manual" or r.status.value == "PASS":
            continue
        print(f"      {r.rule_id:28} {r.status.value:12} {r.message[:60]}")
    print("\n[4] Gloria reviews → Send draft or Approve (human lock).")
    print("=" * 56)


if __name__ == "__main__":
    main()
