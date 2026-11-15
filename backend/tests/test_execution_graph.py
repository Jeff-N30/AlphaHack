"""Execution trace instrumentation + graph builder."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.audit_pipeline import audit_application
from app.config import Settings
from app.ingest.pipeline import seed_from_eval_case
from app.lock.tokens import clear_tokens_for_tests
from app.trace.graph import build_execution_graph
from app.trace.recorder import load_trace, span

_REPO = Path(__file__).resolve().parents[2]
_CASE01 = _REPO / "eval" / "cases" / "case01_complete"


@pytest.fixture()
def offline_settings(tmp_path: Path) -> Settings:
    clear_tokens_for_tests()
    return Settings(
        data_dir=tmp_path / "data",
        checklist_dir=_REPO / "checklists",
        demo_offline=True,
        prompt_version="test-graph",
        email_imap_host="",
        email_imap_user="",
        email_imap_password="",
    )


def test_span_is_noop_without_active_run() -> None:
    with span("stage:ingest") as out:
        out["x"] = 1  # must not raise or record anywhere


@pytest.mark.skipif(not (_CASE01 / "docs" / "flight_booking.pdf").exists(), reason="run make docs")
def test_pipeline_writes_timestamped_trace_and_graph(offline_settings: Settings) -> None:
    aid = seed_from_eval_case(_CASE01, settings=offline_settings)
    report = audit_application(aid, settings=offline_settings, case_id="case01_complete")

    trace = load_trace(aid, offline_settings)
    assert trace and trace["runs"][0]["kind"] == "pipeline"
    events = trace["runs"][0]["events"]
    nodes = [e["node"] for e in events]
    assert nodes[0] == "intake:seed"
    assert "stage:ingest" in nodes and "stage:rules" in nodes
    assert nodes[-1] == "gate:human" and events[-1]["status"] == "awaiting"
    rule_events = [e for e in events if e["node"].startswith("rule:")]
    assert len(rule_events) == len(report["audit"]["results"]) + len(report["audit"]["skipped_rules"])
    assert all(e["started_at"] and e["duration_ms"] is not None for e in rule_events)

    g = build_execution_graph(aid, offline_settings)
    ids = {n["id"] for n in g["nodes"]}
    # environment comes from the checklist + registry, not just executed steps
    assert {f"rule:{r['rule_id']}" for r in report["audit"]["results"]} <= ids
    assert "outbound:smtp" in ids and "intake:email" in ids
    by_id = {n["id"]: n for n in g["nodes"]}
    assert by_id["gate:human"]["status"] == "awaiting"
    assert by_id["intake:email"]["status"] == "disabled"  # IMAP not configured
    assert by_id["intake:upload"]["status"] == "available"  # real capability, unused here
    assert g["summary"]["timing_available"] is True
    assert g["summary"]["state"] in {"pending_approval", "safe_pause"}
    assert all(e["seq"] == i + 1 for i, e in enumerate(g["events"]))
    sizes = {n["size"] for n in g["nodes"]}
    assert len(sizes) > 5  # sizes vary with complexity/connections/workload
