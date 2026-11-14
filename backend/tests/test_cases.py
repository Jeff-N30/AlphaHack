"""Rules engine vs expected.yaml — facts from case.yaml, no LLM."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.models import Status
from app.rules.checklist import load_checklist
from app.rules.engine import run
from app.rules.facts_from_case import facts_from_case

_REPO = Path(__file__).resolve().parents[2]
_CASES = _REPO / "eval" / "cases"
_CHECKLIST = _REPO / "checklists" / "fr-schengen-short-stay.yaml"

def _case_ids() -> list[str]:
    ids = []
    for p in sorted(_CASES.iterdir()):
        if not p.is_dir():
            continue
        if not (p / "case.yaml").exists() or not (p / "expected.yaml").exists():
            continue
        exp = yaml.safe_load((p / "expected.yaml").read_text(encoding="utf-8"))
        if exp and "rules" in exp and "DOC.PRESENT" in (exp.get("rules") or {}):
            ids.append(p.name)
    return ids


_FOCUS = _case_ids()


@pytest.fixture(scope="module")
def checklist():
    return load_checklist(_CHECKLIST)


@pytest.mark.parametrize("case_id", _FOCUS)
def test_case_matches_expected(checklist, case_id: str) -> None:
    case_dir = _CASES / case_id
    exp = yaml.safe_load((case_dir / "expected.yaml").read_text(encoding="utf-8"))
    facts = facts_from_case(case_dir)
    report = run(checklist, facts)

    assert report.outcome.value == exp["outcome"], (
        f"{case_id} outcome: got {report.outcome.value} want {exp['outcome']}\n"
        + _summary(report)
    )
    assert report.escalations == int(exp.get("escalations", 0)), (
        f"{case_id} escalations: got {report.escalations} want {exp.get('escalations')}"
    )

    by_id = {r.rule_id: r for r in report.results}
    skipped = set(report.skipped_rules)

    for rule_id, want in (exp.get("rules") or {}).items():
        want = str(want)
        if want == "SKIPPED":
            assert rule_id in skipped, f"{case_id}: {rule_id} should be SKIPPED"
            continue
        assert rule_id in by_id, f"{case_id}: missing result for {rule_id}"
        got = by_id[rule_id].status.value
        assert got == want, f"{case_id}: {rule_id} got {got} want {want}\n{by_id[rule_id].message}"

    for rid in exp.get("critical_rules") or []:
        if exp["rules"].get(rid) == "SKIPPED":
            assert rid in skipped
        else:
            assert by_id[rid].status.value == exp["rules"][rid]


def _summary(report) -> str:
    lines = []
    for r in report.results:
        if r.mode == "manual":
            continue
        if r.status != Status.PASS:
            lines.append(f"  {r.rule_id}: {r.status.value} — {r.message}")
    lines.append(f"  skipped={report.skipped_rules}")
    return "\n".join(lines)


@pytest.mark.parametrize("case_id", _FOCUS)
def test_manual_rules_not_in_escalations(checklist, case_id: str) -> None:
    facts = facts_from_case(_CASES / case_id)
    report = run(checklist, facts)
    for r in report.results:
        if r.mode == "manual":
            assert r.status == Status.NEEDS_HUMAN
