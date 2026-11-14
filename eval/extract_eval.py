#!/usr/bin/env python3
"""Score LLM field extract vs case.yaml gold (prompt+eval loop — no fine-tune).

  DEMO_OFFLINE=1  → uses fixtures (smoke only; not case-accurate)
  DEMO_OFFLINE=0  → calls Ollama llama3.2 on real PDF text from eval/cases/*/docs

  python eval/extract_eval.py
  python eval/extract_eval.py --cases case01_complete,case05_wrong_dates
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings, get_settings  # noqa: E402
from app.extract.extract import (  # noqa: E402
    extract_application_form,
    extract_bank,
    extract_employment,
    extract_flight,
    extract_hotel,
    extract_insurance,
)
from app.extract.llm import reset_cost_log, cost_log  # noqa: E402
from app.ingest.render import read_preview  # noqa: E402


def _norm_name(s: str) -> str:
    """Uppercase, drop titles, sort tokens — same idea as rules name match."""
    s = s.upper().replace("/", " ")
    for t in (" MR", " MRS", " MS", "MR ", "MRS ", "MS "):
        s = s.replace(t, " ")
    toks = [t for t in s.split() if t and t not in {"MR", "MRS", "MS"}]
    return " ".join(sorted(toks))


def _as_date(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    return str(v)[:10]


def score_flight(pred, gold: dict) -> list[tuple[str, bool, str, str]]:
    rows = []
    g_names = [_norm_name(n) for n in gold.get("passenger_names") or []]
    p_names = [_norm_name(n) for n in (pred.passenger_names or [])]
    joined = " ".join(p_names)
    name_ok = bool(g_names) and all(any(g in p or p in g or g in joined for p in p_names) for g in g_names)
    rows.append(("passenger_names", name_ok, str(g_names), str(p_names)))
    rows.append(("booking_reference", (gold.get("booking_reference") or "").upper() == (pred.booking_reference or "").upper(), str(gold.get("booking_reference")), str(pred.booking_reference)))
    gsegs = gold.get("segments") or []
    psegs = pred.segments or []
    rows.append(("segment_count", len(gsegs) == len(psegs), str(len(gsegs)), str(len(psegs))))
    for i, gs in enumerate(gsegs):
        if i >= len(psegs):
            rows.append((f"seg{i}", False, str(gs), "MISSING"))
            continue
        ps = psegs[i]
        ok = (
            ps.from_airport == gs["from_airport"]
            and ps.to_airport == gs["to_airport"]
            and _as_date(ps.departure_date) == _as_date(gs["departure_date"])
        )
        rows.append((f"seg{i}", ok, f"{gs['from_airport']}->{gs['to_airport']} {_as_date(gs['departure_date'])}", f"{ps.from_airport}->{ps.to_airport} {_as_date(ps.departure_date)}"))
    return rows


def score_insurance(pred, gold: dict) -> list[tuple[str, bool, str, str]]:
    cov = gold.get("coverage") or {}
    rows = [
        ("insured_name", _norm_name(gold.get("insured_name", "")) in _norm_name(pred.insured_name), str(gold.get("insured_name")), pred.insured_name),
        ("coverage_amount", float(cov.get("amount", 0)) == float(pred.coverage.amount), str(cov.get("amount")), str(pred.coverage.amount)),
        ("coverage_currency", (cov.get("currency") or "").upper() == pred.coverage.currency.upper(), str(cov.get("currency")), pred.coverage.currency),
        ("territory", (gold.get("territory") or "").upper() == pred.territory.upper(), str(gold.get("territory")), pred.territory),
        ("start_date", _as_date(gold.get("start_date")) == _as_date(pred.start_date), str(gold.get("start_date")), _as_date(pred.start_date) or ""),
        ("end_date", _as_date(gold.get("end_date")) == _as_date(pred.end_date), str(gold.get("end_date")), _as_date(pred.end_date) or ""),
    ]
    return rows


def score_form(pred, gold: dict) -> list[tuple[str, bool, str, str]]:
    return [
        ("surname", _norm_name(gold.get("surname", "")) == _norm_name(pred.surname), str(gold.get("surname")), pred.surname),
        ("given_names", _norm_name(gold.get("given_names", "")) == _norm_name(pred.given_names), str(gold.get("given_names")), pred.given_names),
        ("passport_number", (gold.get("passport_number") or "") == (pred.passport_number or ""), str(gold.get("passport_number")), str(pred.passport_number)),
        ("date_of_birth", _as_date(gold.get("date_of_birth")) == _as_date(pred.date_of_birth), str(gold.get("date_of_birth")), _as_date(pred.date_of_birth) or ""),
        ("intended_arrival", _as_date(gold.get("intended_arrival")) == _as_date(pred.intended_arrival), str(gold.get("intended_arrival")), _as_date(pred.intended_arrival) or ""),
    ]


def score_hotel(pred, gold: dict) -> list[tuple[str, bool, str, str]]:
    g_names = [_norm_name(n) for n in gold.get("guest_names") or []]
    p_names = [_norm_name(n) for n in (pred.guest_names or [])]
    name_ok = bool(g_names) and all(any(g in p or p in g for p in p_names) for g in g_names)
    return [
        ("guest_names", name_ok, str(g_names), str(p_names)),
        ("country", (gold.get("country") or "").upper() == (pred.country or "").upper(), str(gold.get("country")), str(pred.country)),
        ("check_in", _as_date(gold.get("check_in")) == _as_date(pred.check_in), str(gold.get("check_in")), _as_date(pred.check_in) or ""),
        ("check_out", _as_date(gold.get("check_out")) == _as_date(pred.check_out), str(gold.get("check_out")), _as_date(pred.check_out) or ""),
    ]


def score_bank(pred, gold: dict) -> list[tuple[str, bool, str, str]]:
    return [
        ("account_holder", _norm_name(gold.get("account_holder", "")) in _norm_name(pred.account_holder or ""), str(gold.get("account_holder")), str(pred.account_holder)),
        ("account_currency", (gold.get("account_currency") or "").upper() == (pred.account_currency or "").upper(), str(gold.get("account_currency")), str(pred.account_currency)),
        ("closing_balance", float(gold.get("closing_balance", 0)) == float(pred.closing_balance), str(gold.get("closing_balance")), str(pred.closing_balance)),
        ("has_bank_stamp", bool(gold.get("has_bank_stamp")) == bool(pred.has_bank_stamp), str(gold.get("has_bank_stamp")), str(pred.has_bank_stamp)),
        ("period_end", _as_date(gold.get("period_end")) == _as_date(pred.period_end), str(gold.get("period_end")), _as_date(pred.period_end) or ""),
    ]


def score_employment(pred, gold: dict) -> list[tuple[str, bool, str, str]]:
    g_pos = (gold.get("position") or "").strip()
    p_pos = (pred.position or "").strip()
    if g_pos:
        pos_ok = _norm_name(g_pos) in _norm_name(p_pos) or _norm_name(p_pos) in _norm_name(g_pos)
    else:
        # Gold omitted — still require a non-null title when extract returns one for audit
        pos_ok = bool(p_pos)
    return [
        ("employee_name", _norm_name(gold.get("employee_name", "")) in _norm_name(pred.employee_name or ""), str(gold.get("employee_name")), str(pred.employee_name)),
        ("employer_name", bool(pred.employer_name), str(gold.get("employer_name")), str(pred.employer_name)),
        ("position", pos_ok, g_pos or "(any)", p_pos or "NULL"),
        ("leave_start", _as_date(gold.get("leave_start")) == _as_date(pred.leave_start), str(gold.get("leave_start")), _as_date(pred.leave_start) or ""),
        ("leave_end", _as_date(gold.get("leave_end")) == _as_date(pred.leave_end), str(gold.get("leave_end")), _as_date(pred.leave_end) or ""),
    ]


def run_case(case_dir: Path, settings: Settings) -> dict:
    case = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
    docs = case.get("documents") or {}
    docs_dir = case_dir / "docs"
    results: list[dict] = []

    checks = [
        ("flight_booking", extract_flight, score_flight),
        ("travel_insurance", extract_insurance, score_insurance),
        ("application_form", extract_application_form, score_form),
        ("hotel_booking", extract_hotel, score_hotel),
        ("bank_statement", extract_bank, score_bank),
        ("employment_letter", extract_employment, score_employment),
    ]
    for key, extract_fn, score_fn in checks:
        gold = docs.get(key)
        if not gold:
            continue
        fname = gold.get("file")
        path = docs_dir / fname if fname else None
        if path is None or not path.exists():
            results.append({"doc": key, "skipped": True, "reason": "missing_pdf"})
            continue
        prev = read_preview(path, max_pages=6)
        reset_cost_log()
        pred = extract_fn(prev.text, source=path, settings=settings)
        rows = score_fn(pred, gold)
        ok = sum(1 for _, good, _, _ in rows if good)
        results.append(
            {
                "doc": key,
                "skipped": False,
                "correct": ok,
                "total": len(rows),
                "accuracy": ok / len(rows) if rows else 0.0,
                "fields": [{"field": f, "ok": g, "gold": a, "pred": b} for f, g, a, b in rows],
                "cost": [c.model_dump() for c in cost_log()],
            }
        )
    return {"case_id": case.get("case_id", case_dir.name), "docs": results}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", default="", help="comma case folder names; default = all with docs")
    ap.add_argument("--offline", action="store_true", help="force DEMO_OFFLINE fixtures")
    args = ap.parse_args()

    settings = get_settings()
    if args.offline:
        settings = Settings(
            data_dir=settings.data_dir,
            checklist_dir=settings.checklist_dir,
            demo_offline=True,
            extract_provider="ollama",
            extract_model=settings.extract_model,
            prompt_version=settings.prompt_version + "+eval",
        )

    cases_root = ROOT / "eval" / "cases"
    if args.cases:
        dirs = [cases_root / c.strip() for c in args.cases.split(",") if c.strip()]
    else:
        dirs = sorted(p for p in cases_root.iterdir() if p.is_dir() and (p / "case.yaml").exists())

    mode = "OFFLINE_FIXTURE" if settings.demo_offline else f"LIVE:{settings.extract_provider}/{settings.extract_model}"
    print(f"extract_eval mode={mode}")
    if settings.demo_offline:
        print("NOTE: offline fixtures are Jeff-shaped specimens — scores vs case.yaml will be low.")
        print("      Train loop: DEMO_OFFLINE=0 + ollama serve, then re-run this script.\n")

    all_rows = []
    summary = []
    for d in dirs:
        if not (d / "docs").exists():
            continue
        report = run_case(d, settings)
        for doc in report["docs"]:
            if doc.get("skipped"):
                print(f"  {report['case_id']:30} {doc['doc']:20} SKIP {doc.get('reason')}")
                continue
            pct = 100 * doc["accuracy"]
            print(f"  {report['case_id']:30} {doc['doc']:20} {doc['correct']}/{doc['total']} ({pct:.0f}%)")
            for f in doc["fields"]:
                if not f["ok"]:
                    print(f"      miss {f['field']}: gold={f['gold']!r} pred={f['pred']!r}")
            summary.append((report["case_id"], doc["doc"], doc["correct"], doc["total"]))
            all_rows.append(
                {
                    "ts": datetime.utcnow().isoformat(timespec="seconds"),
                    "mode": mode,
                    "case_id": report["case_id"],
                    "doc": doc["doc"],
                    "correct": doc["correct"],
                    "total": doc["total"],
                    "accuracy": round(doc["accuracy"], 3),
                }
            )

    if not summary:
        print("No cases with docs/ found. Run: make docs")
        return 1

    tot_c = sum(c for _, _, c, _ in summary)
    tot_t = sum(t for _, _, _, t in summary)
    print(f"\nTOTAL {tot_c}/{tot_t} fields ({100 * tot_c / tot_t:.1f}%)")

    hist = ROOT / "eval" / "extract_history.csv"
    write_header = not hist.exists()
    with hist.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "mode", "case_id", "doc", "correct", "total", "accuracy"])
        if write_header:
            w.writeheader()
        w.writerows(all_rows)
    print(f"appended {hist}")
    return 0 if tot_c == tot_t else 0  # non-fatal while prompts iterate


if __name__ == "__main__":
    raise SystemExit(main())
