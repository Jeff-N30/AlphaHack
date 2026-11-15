#!/usr/bin/env python3
"""Regenerate Dec-2026 Jeff pack only — never overwrites original Jeff (eb09659c3feb).

  .venv/bin/python tools/regen_jeff_pack.py          # pack only
  .venv/bin/python tools/regen_jeff_pack.py --seed   # also new queue app
  .venv/bin/python tools/seed_jeff_both.py           # restore original + seed Dec
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tools"))

from seed_jeff_both import build_dec_pack, seed_dec_app  # noqa: E402
from app.config import get_settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="create a new Dec-2026 queue app")
    args = ap.parse_args()
    pack = build_dec_pack()
    print(f"pack → {pack}")
    if args.seed:
        aid = seed_dec_app(get_settings())
        print(f"seeded {aid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
