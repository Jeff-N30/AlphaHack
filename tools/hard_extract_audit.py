#!/usr/bin/env python3
"""Hard extract audit: PDF text vs Llama fields vs case.yaml gold.

Groups misses into:
  NULL_IN_TEXT  — value clearly in PDF text but model returned null/empty
  WRONG_VS_GOLD — model value disagrees with case.yaml
  OK

Usage:
  .venv/bin/python tools/hard_extract_audit.py
  .venv/bin/python tools/hard_extract_audit.py --cases case01_complete,case24_arabic_only_employment_letter
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
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
    extract_payslip,
)
from app.extract.llm import reset_cost_log  # noqa: E402
from app.ingest.render import read_preview  # noqa: E402

# Critical fields per doc — if null while a cue exists in text → NULL_IN_TEXT
_FIELD_CUES: dict[str, dict[str, list[str]]] = {
    "employment_letter": {
        "position": [r"\bas\s+[A-Z]", r"(?i)position\s*:", r"(?i)fonction\s*:", r"(?i)job\s*title"],
        "employee_name": [r"(?i)certify that", r"(?i)employé"],
        "hire_date": [r"(?i)since\s+\d", r"(?i)depuis\s+\d"],
        "leave_start": [r"(?i)leave", r"(?i)cong"],
        "leave_end": [r"(?i)leave", r"(?i)cong"],
        "monthly_salary": [r"(?i)salary", r"(?i)salaire"],
    },
    "travel_insurance": {
        "date_of_birth": [r"(?i)birth", r"(?i)né|nee|dob", r"\d{2}/\d{2}/\d{4}"],
        "passport_number": [r"(?i)passport", r"\b[A-Z]{1,2}\d{6,9}\b"],
        "insured_name": [r"(?i)insured", r"(?i)assuré"],
        "coverage": [r"(?i)EUR|USD|coverage|sum insured"],
        "start_date": [r"(?i)valid|from|start"],
        "end_date": [r"(?i)until|to|end"],
    },
    "bank_statement": {
        "account_holder": [r"(?i)account holder|titulaire"],
        "closing_balance": [r"(?i)closing|solde"],
        "account_currency": [r"\bUSD\b|\bEUR\b|\bLBP\b"],
        "period_end": [r"(?i)period|to\s+\d"],
    },
    "hotel_booking": {
        "guest_names": [r"(?i)guest|name"],
        "check_in": [r"(?i)check[- ]?in|arrival"],
        "check_out": [r"(?i)check[- ]?out|departure"],
        "country": [r"(?i)france|paris|fr\b"],
    },
    "flight_booking": {
        "passenger_names": [r"(?i)passenger|name"],
        "booking_reference": [r"(?i)pnr|booking|ref"],
    },
    "application_form": {
        "surname": [r"(?i)surname|nom"],
        "given_names": [r"(?i)given|prénom"],
        "passport_number": [r"(?i)passport"],
        "date_of_birth": [r"(?i)birth|né"],
    },
    "payslip": {
        "period_month": [r"(?i)period|mois|2026-"],
        "net_pay": [r"(?i)net|salary|salaire"],
        "employee_name": [r"(?i)employee|employé"],
    },
}


def _as_date(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    return str(v)[:10]


def _empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, dict)) and not v:
        return True
    return False


def _get(pred, field: str):
    if hasattr(pred, field):
        return getattr(pred, field)
    return None


def _pred_dict(pred) -> dict:
    if hasattr(pred, "model_dump"):
        return pred.model_dump(mode="json")
    return dict(pred)


def _text_has_cue(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text) for p in patterns)


def _norm(s: str) -> str:
    s = (s or "").upper().replace("/", " ")
    for t in (" MR", " MRS", " MS", "MR ", "MRS ", "MS "):
        s = s.replace(t, " ")
    toks = sorted(t for t in re.split(r"[^A-Z0-9]+", s) if t and t not in {"MR", "MRS", "MS"})
    return "".join(toks)


def compare_gold(field: str, gold_val, pred_val) -> bool | None:
    if gold_val is None:
        return None
    if field.endswith("_date") or field in {
        "hire_date",
        "leave_start",
        "leave_end",
        "letter_date",
        "check_in",
        "check_out",
        "start_date",
        "end_date",
        "period_start",
        "period_end",
        "issue_date",
        "date_of_birth",
        "intended_arrival",
        "intended_departure",
        "expiry_date",
    }:
        return _as_date(gold_val) == _as_date(pred_val)
    if field in {"passenger_names", "guest_names", "members"}:
        g = {_norm(x) for x in (gold_val or [])}
        p = {_norm(x) for x in (pred_val or [])}
        if not g:
            return None
        # token-sort match: NASSAR/KARIM MR ↔ KARIM NASSAR
        return all(any(gv == pv or gv in pv or pv in gv for pv in p) for gv in g)
    if field in {"coverage", "monthly_salary", "net_pay"} and isinstance(gold_val, dict):
        if pred_val is None:
            return False
        pa = getattr(pred_val, "amount", None)
        pc = getattr(pred_val, "currency", None)
        if isinstance(pred_val, dict):
            pa, pc = pred_val.get("amount"), pred_val.get("currency")
        try:
            return float(gold_val.get("amount", 0)) == float(pa) and str(
                gold_val.get("currency", "")
            ).upper() == str(pc or "").upper()
        except (TypeError, ValueError):
            return False
    if isinstance(gold_val, (int, float)) and pred_val is not None:
        try:
            return float(gold_val) == float(pred_val)
        except (TypeError, ValueError):
            return False
    if isinstance(gold_val, bool):
        return bool(gold_val) == bool(pred_val)
    if isinstance(gold_val, str):
        return _norm(gold_val) in _norm(str(pred_val or "")) or _norm(str(pred_val or "")) in _norm(
            gold_val
        )
    return True


EXTRACTORS = {
    "flight_booking": extract_flight,
    "travel_insurance": extract_insurance,
    "application_form": extract_application_form,
    "hotel_booking": extract_hotel,
    "bank_statement": extract_bank,
    "employment_letter": extract_employment,
    "payslip": extract_payslip,
}


def audit_doc(
    *,
    case_id: str,
    doc_key: str,
    path: Path,
    gold: dict,
    settings: Settings,
) -> dict:
    prev = read_preview(path, max_pages=6)
    text = prev.text or ""
    reset_cost_log()
    fn = EXTRACTORS[doc_key]
    pred = fn(text, source=path, settings=settings)
    pdata = _pred_dict(pred)

    cues = _FIELD_CUES.get(doc_key, {})
    fields_out = []
    for field, patterns in cues.items():
        # payslip gold may nest differently; employment position may be absent from gold
        gval = gold.get(field)
        if field == "coverage" and "coverage" not in gold and "coverage_amount" in gold:
            gval = {"amount": gold.get("coverage_amount"), "currency": gold.get("coverage_currency")}
        pval = _get(pred, field)
        cue = _text_has_cue(text, patterns)
        empty = _empty(pval)
        gold_ok = compare_gold(field, gval, pval) if gval is not None else None

        if empty and cue:
            group = "NULL_IN_TEXT"
        elif gold_ok is False:
            group = "WRONG_VS_GOLD"
        elif empty and not cue:
            group = "NULL_NO_CUE"
        else:
            group = "OK"

        fields_out.append(
            {
                "field": field,
                "group": group,
                "pred": pdata.get(field),
                "gold": gval,
                "text_cue": cue,
                "text_snippet": _snippet(text, patterns) if cue else None,
            }
        )

    return {
        "case_id": case_id,
        "doc": doc_key,
        "file": path.name,
        "text_chars": len(text),
        "text_preview": text[:400].replace("\n", " | "),
        "fields": fields_out,
        "pred": pdata,
    }


def _snippet(text: str, patterns: list[str], radius: int = 60) -> str | None:
    for p in patterns:
        m = re.search(p, text)
        if m:
            a = max(0, m.start() - radius)
            b = min(len(text), m.end() + radius)
            return re.sub(r"\s+", " ", text[a:b]).strip()
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cases",
        default="case01_complete,case08_insurance_ends_early,case20_leave_ends_early,case05_wrong_dates,case11_insufficient_funds",
    )
    args = ap.parse_args()

    get_settings.cache_clear()
    base = get_settings()
    settings = Settings(
        data_dir=base.data_dir,
        checklist_dir=base.checklist_dir,
        demo_offline=False,
        extract_provider="ollama",
        extract_model=base.extract_model,
        prompt_version=str(base.prompt_version),
        ollama_base_url=base.ollama_base_url,
    )

    cases_root = ROOT / "eval" / "cases"
    reports = []
    for name in [c.strip() for c in args.cases.split(",") if c.strip()]:
        case_dir = cases_root / name
        if not (case_dir / "case.yaml").exists():
            print(f"SKIP missing case {name}")
            continue
        case = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
        docs = case.get("documents") or {}
        print(f"\n=== {name} ===")
        for key, extract_key in [
            ("flight_booking", "flight_booking"),
            ("travel_insurance", "travel_insurance"),
            ("application_form", "application_form"),
            ("hotel_booking", "hotel_booking"),
            ("bank_statement", "bank_statement"),
            ("employment_letter", "employment_letter"),
        ]:
            gold = docs.get(key)
            if not gold:
                continue
            fname = gold.get("file")
            path = case_dir / "docs" / fname if fname else None
            if not path or not path.exists():
                print(f"  {key}: missing pdf")
                continue
            print(f"  extracting {key} …", flush=True)
            try:
                rep = audit_doc(
                    case_id=name,
                    doc_key=extract_key,
                    path=path,
                    gold=gold,
                    settings=settings,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  {key}: EXTRACT_ERROR {exc}")
                reports.append(
                    {
                        "case_id": name,
                        "doc": key,
                        "file": path.name,
                        "error": str(exc),
                        "fields": [],
                    }
                )
                continue
            reports.append(rep)
            bad = [f for f in rep["fields"] if f["group"] not in {"OK", "NULL_NO_CUE"}]
            if not bad:
                print(f"  {key}: all critical OK")
            else:
                for f in bad:
                    print(
                        f"  {key}.{f['field']}: {f['group']}  pred={f['pred']!r}  gold={f['gold']!r}"
                    )
                    if f.get("text_snippet"):
                        print(f"      text: …{f['text_snippet']}…")

        # payslips (list or single) — one slip per case is enough for audit
        slips = docs.get("payslips") or docs.get("payslip")
        if isinstance(slips, list) and slips:
            slip = slips[-1]  # latest month
            fname = slip.get("file")
            path = case_dir / "docs" / fname if fname else None
            if path and path.exists():
                print("  extracting payslip …", flush=True)
                try:
                    rep = audit_doc(
                        case_id=name,
                        doc_key="payslip",
                        path=path,
                        gold=slip,
                        settings=settings,
                    )
                    reports.append(rep)
                    bad = [f for f in rep["fields"] if f["group"] not in {"OK", "NULL_NO_CUE"}]
                    if bad:
                        for f in bad:
                            print(f"  payslip.{f['field']}: {f['group']} pred={f['pred']!r}")
                    else:
                        print("  payslip: all critical OK")
                except Exception as exc:  # noqa: BLE001
                    print(f"  payslip: EXTRACT_ERROR {exc}")
                    reports.append(
                        {
                            "case_id": name,
                            "doc": "payslip",
                            "error": str(exc),
                            "fields": [],
                        }
                    )

    # Group summary
    buckets: dict[str, list[str]] = {}
    for r in reports:
        for f in r["fields"]:
            if f["group"] in {"OK", "NULL_NO_CUE"}:
                continue
            key = f"{f['group']}::{r['doc']}.{f['field']}"
            buckets.setdefault(key, []).append(r["case_id"])

    print("\n======== GROUPED MISSES ========")
    if not buckets:
        print("None — all critical fields OK on audited cases.")
    else:
        for k, cases in sorted(buckets.items()):
            print(f"{k}: {len(cases)}  ({', '.join(cases)})")

    out = ROOT / "eval" / "hard_extract_audit.json"
    out.write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
