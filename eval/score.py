#!/usr/bin/env python3
"""Score VisaRef runs against eval/cases/*/expected.yaml.

  python eval/score.py runs/2026-11-14_night          # dir of <case_id>.json AuditReports
  python eval/score.py --selftest                     # sanity check of this script

A case PASSES when: outcome matches AND every critical_rule status matches
AND (if a draft is required) the draft contains every must_mention string and none of must_not_mention.
Also reported: rule-level accuracy, human count (cases with escalations > 0), avg/total cost.
Appends one line to eval/history.csv so you can post the Fri/Sat/Sun curve.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"


def load_expected():
    return {p.parent.name: yaml.safe_load(p.read_text()) for p in sorted(CASES.glob("*/expected.yaml"))}


def statuses(report: dict) -> dict:
    s = {r["rule_id"]: r["status"] for r in report.get("results", []) if r.get("mode") != "manual"}
    for rid in report.get("skipped_rules", []):
        s[rid] = "SKIPPED"
    return s


def draft_text(report: dict) -> str:
    return " ".join(d.get("body", "") for d in report.get("drafts", []))


def score_case(exp: dict, rep: dict) -> dict:
    got = statuses(rep)
    reasons = []
    if rep.get("outcome") != exp["outcome"]:
        reasons.append(f"outcome {rep.get('outcome')} != {exp['outcome']}")
    for rid in exp["critical_rules"]:
        if got.get(rid) != exp["rules"][rid]:
            reasons.append(f"{rid} {got.get(rid)} != {exp['rules'][rid]}")
    dm = exp.get("draft_message", {})
    if dm.get("required"):
        body = draft_text(rep).lower()
        if not body:
            reasons.append("draft missing")
        reasons += [f"draft lacks '{m}'" for m in dm.get("must_mention", []) if m.lower() not in body]
        reasons += [f"draft has '{m}'" for m in dm.get("must_not_mention", []) if m.lower() in body]
    rule_hits = sum(1 for rid, st in exp["rules"].items() if got.get(rid) == st)
    return {"pass": not reasons, "reasons": reasons, "rule_hits": rule_hits, "rule_total": len(exp["rules"]),
            "escalations": rep.get("escalations", 0), "usd": rep.get("total_usd", 0.0)}


def run(run_dir: Path, label: str):
    exp = load_expected()
    rows = []
    for cid, e in exp.items():
        f = run_dir / f"{cid}.json"
        if not f.exists():
            rows.append((cid, {"pass": False, "reasons": ["no report"], "rule_hits": 0, "rule_total": len(e["rules"]), "escalations": 0, "usd": 0}))
            continue
        rows.append((cid, score_case(e, json.loads(f.read_text()))))
    n = len(rows)
    passed = sum(r["pass"] for _, r in rows)
    humans = sum(1 for _, r in rows if r["escalations"] > 0)
    acc = sum(r["rule_hits"] for _, r in rows) / max(1, sum(r["rule_total"] for _, r in rows))
    cost = sum(r["usd"] for _, r in rows)
    print(f"\n{'case':32} {'result':6} {'esc':>3} {'usd':>7}  reasons")
    for cid, r in rows:
        print(f"{cid:32} {'PASS' if r['pass'] else 'FAIL':6} {r['escalations']:>3} {r['usd']:>7.4f}  {'; '.join(r['reasons'])}")
    print(f"\nPASS RATE {passed}/{n} = {passed / n:.0%} | rule accuracy {acc:.1%} | cases needing Gloria {humans}/{n} "
          f"| cost total ${cost:.3f}, avg ${cost / n:.4f}/application")
    hist = ROOT / "history.csv"
    new = not hist.exists()
    with hist.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["timestamp", "label", "cases", "passed", "pass_rate", "rule_accuracy", "needs_gloria", "avg_usd"])
        w.writerow([datetime.now().isoformat(timespec="minutes"), label, n, passed, f"{passed / n:.3f}", f"{acc:.3f}", humans, f"{cost / n:.4f}"])
    return passed == n


def selftest():
    """Build perfect reports from expected.yaml and confirm 100%."""
    tmp = ROOT / ".selftest"
    tmp.mkdir(exist_ok=True)
    for cid, e in load_expected().items():
        results = [{"rule_id": k, "status": v, "mode": "code", "message": ""} for k, v in e["rules"].items() if v != "SKIPPED"]
        body = " ".join(e.get("draft_message", {}).get("must_mention", []))
        rep = {"outcome": e["outcome"], "results": results, "escalations": e["escalations"], "total_usd": 0.1,
               "skipped_rules": [k for k, v in e["rules"].items() if v == "SKIPPED"], "drafts": [{"body": body}] if body else []}
        (tmp / f"{cid}.json").write_text(json.dumps(rep))
    ok = run(tmp, "selftest")
    (ROOT / "history.csv").unlink(missing_ok=True)
    for f in tmp.glob("*.json"):
        f.unlink()
    tmp.rmdir()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = Path(sys.argv[1])
    run(d, sys.argv[2] if len(sys.argv) > 2 else d.name)
