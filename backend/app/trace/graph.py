"""Build the agent execution graph for one application.

Nodes come only from real sources: the checklist YAML (rules), the check REGISTRY,
the extractor set (EXTRACTABLE + MRZ passport), the application's own files, the
pipeline/lock/outbound components, and Settings (what is configured). Statuses and
replay events come from execution_trace.json (timestamped instrumentation); older
applications without a trace fall back to report-derived, *untimed* events.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.extract.pipeline_extract import EXTRACTABLE
from app.rules.checklist import load_checklist
from app.rules.registry import REGISTRY, ensure_loaded
from app.storage.files import app_dir, load_meta
from app.trace.recorder import load_trace

_REPO = Path(__file__).resolve().parents[3]

# cluster → display category
CLUSTERS = {
    "intake": "Intake",
    "documents": "Documents",
    "extraction": "Extraction",
    "model": "Model",
    "facts": "Facts",
    "rules": "Validation rules",
    "checks": "Check functions",
    "decision": "Decision",
    "human": "Human lock",
    "delivery": "Delivery",
    "storage": "Storage",
}

# complexity weight per kind (1 = trivial check … 5 = multi-step stage)
_COMPLEXITY = {
    "stage": 5, "gate": 5, "intake": 2, "op": 3, "file": 1.5, "extractor": 3,
    "llm": 4, "rule": 1.5, "check": 1, "lock": 2.5, "outbound": 2.5, "store": 2,
}


def _iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class _G:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[tuple[str, str], dict[str, Any]] = {}

    def node(self, nid: str, label: str, cluster: str, kind: str, *, component: str | None = None,
             description: str | None = None, **data: Any) -> None:
        if nid in self.nodes:
            self.nodes[nid]["data"].update({k: v for k, v in data.items() if v is not None})
            return
        self.nodes[nid] = {
            "id": nid,
            "label": label,
            "cluster": cluster,
            "category": CLUSTERS[cluster],
            "kind": kind,
            "component": component,
            "description": description,
            "data": {k: v for k, v in data.items() if v is not None},
            "configured": True,
        }

    def edge(self, a: str, b: str, kind: str = "flow") -> None:
        if a in self.nodes and b in self.nodes and a != b and (b, a) not in self.edges:
            self.edges.setdefault((a, b), {"source": a, "target": b, "kind": kind})


def _environment(settings: Settings, meta: dict[str, Any], ingest: dict[str, Any] | None,
                 checklist_path: Path) -> tuple[_G, Any]:
    g = _G()
    imap_ok = bool(settings.email_imap_host and settings.email_imap_user and settings.email_imap_password)
    smtp_ok = bool(settings.email_imap_user and settings.email_imap_password)

    # intake
    g.node("intake:upload", "Desk upload", "intake", "intake", component="POST /applications",
           description="Officer uploads PDFs/images from the desk.")
    g.node("intake:seed", "Demo case seed", "intake", "intake", component="POST /demo/seed-case/{case}",
           description="Loads an eval case's documents into a new application.")
    g.node("intake:email", "Email inbox", "intake", "intake",
           component="ingest.email_pipeline.process_visa_inbox",
           description="Reads VISA-subject emails over IMAP and saves attachments.")
    g.node("intake:watcher", "Email watcher", "intake", "intake",
           component="ingest.email_watcher.watch_email_inbox",
           description="Background IMAP poller started with the API.")
    g.nodes["intake:email"]["configured"] = imap_ok
    g.nodes["intake:watcher"]["configured"] = imap_ok
    g.node("store:files", "Application store", "storage", "store", component="storage.files",
           description="meta.json + raw/ originals per application.")

    # documents
    g.node("stage:ingest", "Ingest", "documents", "stage", component="ingest.pipeline.process_application",
           description="Preview, classify and MRZ-read every attachment.")
    g.node("op:render", "Render / preview", "documents", "op", component="ingest.render.read_preview",
           description="Text layer or rasterised page preview per document.")
    g.node("op:classify", "Classify", "documents", "op", component="extract.classify.classify_document",
           description="Keyword / Llama document-type classification.")
    g.node("op:mrz", "MRZ reader", "documents", "op", component="extract.mrz.best_mrz",
           description="ICAO 9303 TD3 machine-readable zone with checksums.")
    files = [f.get("file") for f in (ingest or {}).get("files") or [] if f.get("file")]
    if not files:
        files = [f.get("name") for f in meta.get("files") or [] if isinstance(f, dict) and f.get("name")]
    for name in files:
        g.node(f"file:{name}", name, "documents", "file", component=f"raw/{name}",
               description="Source document received with the application.")

    # model
    g.node("llm:ollama", f"{settings.extract_provider} · {settings.extract_model}", "model", "llm",
           component="extract.llm (Ollama)", description="Typed-field extraction only; never decides PASS/FAIL.",
           provider=settings.extract_provider, model=settings.extract_model,
           demo_offline=settings.demo_offline)
    g.node("store:llm_cache", "Extraction cache", "storage", "store", component="extract.llm cache",
           description="Content-hashed extraction results (and offline fixtures).")

    # extraction
    g.node("stage:extract", "Extraction", "extraction", "stage",
           component="extract.pipeline_extract.extract_application_docs",
           description="Typed fields per classified document.")
    for dt in sorted([d.value for d in EXTRACTABLE] + ["passport"]):
        g.node(f"extract:{dt}", dt.replace("_", " "), "extraction", "extractor",
               component="extract.mrz → passport_from_mrz" if dt == "passport" else f"extract.extract_by_type({dt})",
               description=f"Extractor for {dt.replace('_', ' ')} documents.")

    # facts
    g.node("stage:facts", "Facts", "facts", "stage", component="rules.facts_from_extractions",
           description="Normalise extractions into rule facts.")
    g.node("op:facts_extract", "From extractions", "facts", "op",
           component="rules.facts_from_extractions.facts_from_extractions")
    g.node("op:facts_case", "From case file", "facts", "op", component="rules.facts_from_case.facts_from_case",
           description="Offline demo: gold case.yaml facts.")

    # rules + checks
    ensure_loaded()
    checklist = load_checklist(checklist_path)
    g.node("stage:rules", "Rules engine", "rules", "stage", component="rules.engine.run",
           description=f"Checklist {checklist.id} v{checklist.version}, rule by rule.",
           checklist=checklist.id, version=checklist.version)
    for name in sorted(REGISTRY):
        g.node(f"check:{name}", name, "checks", "check", component=f"rules.checks · {name}",
               description="Registered check function.")
    for rule in checklist.rules:
        g.node(f"rule:{rule.id}", rule.id, "rules", "rule", component=f"check:{rule.check}",
               description=rule.message, check=rule.check, mode=rule.mode, on_fail=rule.on_fail,
               docs=list(rule.docs), fail_status=rule.fail_status, source=rule.source,
               params={k: v for k, v in rule.params.items()})

    # decision / human / delivery
    g.node("stage:outcome", "Outcome", "decision", "stage", component="rules.engine._compute_outcome",
           description="PASS/FAIL/NEEDS_HUMAN → READY / NEEDS_GLORIA / SEND_BACK.")
    g.node("stage:drafts", "Draft writer", "decision", "op", component="drafts.drafter.attach_drafts",
           description="Applicant message draft (never auto-sent).")
    g.node("store:report", "Audit report", "storage", "store", component="email_pipeline_report.json")
    g.node("gate:human", "Gloria review", "human", "gate", component="human lock",
           description="Pipeline stops; only Gloria can approve or send back.")
    g.node("lock:confirm_token", "Confirm token", "human", "lock", component="POST /confirm-tokens",
           description="One-time token required for every lock action.")
    g.node("lock:approve", "Approve", "human", "lock", component="lock.actions.approve_application")
    g.node("lock:send_back", "Send back", "human", "lock", component="lock.actions.send_draft")
    g.node("lock:review", "Flag for review", "human", "lock", component="lock.actions.mark_review")
    g.node("outbound:smtp", "SMTP delivery", "delivery", "outbound", component="outbound.deliver",
           description="Emails the approved draft to the applicant.",
           host=settings.email_smtp_host)
    g.nodes["outbound:smtp"]["configured"] = smtp_ok
    g.node("store:audit_log", "Audit log", "storage", "store", component="audit_log.jsonl",
           description="Append-only record of every human lock action.")

    # edges: intake
    g.edge("intake:watcher", "intake:email")
    for src in ("intake:upload", "intake:seed", "intake:email"):
        g.edge(src, "store:files")
        g.edge(src, "stage:ingest")
    g.edge("store:files", "stage:ingest", "data")
    # documents
    for f in (ingest or {}).get("files") or []:
        name = f.get("file")
        if not name:
            continue
        g.edge("stage:ingest", f"file:{name}")
        if not f.get("rejected"):
            g.edge(f"file:{name}", "op:render", "uses")
            g.edge(f"file:{name}", "op:classify", "uses")
        if "mrz" in f or f.get("mrz_note"):
            g.edge(f"file:{name}", "op:mrz", "uses")
        dt = (f.get("classification") or {}).get("doc_type")
        if dt == "passport" and ("mrz" in f):
            g.edge("op:mrz", "extract:passport")
        if dt:
            g.edge(f"file:{name}", f"extract:{dt}", "data")
    if not (ingest or {}).get("files"):
        for name in files:
            g.edge("stage:ingest", f"file:{name}")
    g.edge("stage:ingest", "op:render", "uses")
    g.edge("stage:ingest", "op:classify", "uses")
    g.edge("stage:ingest", "op:mrz", "uses")
    g.edge("op:classify", "llm:ollama", "uses")
    g.edge("stage:ingest", "stage:extract")
    # extraction
    for nid in list(g.nodes):
        if nid.startswith("extract:"):
            g.edge("stage:extract", nid)
            if nid != "extract:passport":
                g.edge(nid, "llm:ollama", "uses")
                g.edge(nid, "store:llm_cache", "uses")
            g.edge(nid, "stage:facts", "data")
    g.edge("stage:extract", "stage:facts")
    g.edge("stage:facts", "op:facts_extract", "uses")
    g.edge("stage:facts", "op:facts_case", "uses")
    g.edge("stage:facts", "stage:rules")
    # rules
    for rule in checklist.rules:
        rid = f"rule:{rule.id}"
        g.edge("stage:rules", rid)
        g.edge(rid, f"check:{rule.check}", "uses")
        for d in rule.docs:
            g.edge(f"extract:{d}", rid, "data")
    g.edge("stage:rules", "stage:outcome")
    g.edge("stage:outcome", "stage:drafts")
    g.edge("stage:drafts", "store:report")
    g.edge("store:report", "gate:human")
    g.edge("gate:human", "lock:confirm_token")
    for a in ("lock:approve", "lock:send_back", "lock:review"):
        g.edge("lock:confirm_token", a)
        g.edge(a, "store:audit_log", "data")
    g.edge("lock:approve", "outbound:smtp")
    g.edge("lock:send_back", "outbound:smtp")
    g.edge("stage:drafts", "llm:ollama", "uses")
    return g, checklist


def _legacy_events(meta: dict[str, Any], report: dict[str, Any] | None, audit_rows: list[dict[str, Any]],
                   g: _G) -> list[dict[str, Any]]:
    """Untimed events reconstructed from the stored reports (no invented timings)."""
    ev: list[dict[str, Any]] = []

    def add(node: str, status: str = "completed", ts: str | None = None, source: str | None = None,
            outputs: dict[str, Any] | None = None, inputs: dict[str, Any] | None = None,
            via: list[str] | None = None) -> None:
        if node not in g.nodes:
            return
        ev.append({"id": f"legacy-{len(ev) + 1}", "node": node, "label": g.nodes[node]["label"],
                   "status": status, "started_at": ts, "ended_at": ts, "duration_ms": None,
                   "inputs": inputs or {}, "outputs": outputs or {}, "via": via or [], "source": source,
                   "parent": None, "untimed": ts is None})

    if not report:
        return ev
    intake = "intake:email" if meta.get("email_uid") or meta.get("email_source") else (
        "intake:seed" if report.get("case_id") or meta.get("case_id") else "intake:upload")
    add(intake, ts=meta.get("created_at"))
    ingest = report.get("ingest_report") or {}
    add("stage:ingest", source=intake, outputs={"files": len(ingest.get("files") or [])})
    for f in ingest.get("files") or []:
        cls = f.get("classification") or {}
        via = [] if f.get("rejected") else ["op:render", "op:classify"]
        if "mrz" in f or f.get("mrz_note"):
            via.append("op:mrz")
        add(f"file:{f.get('file')}", "skipped" if f.get("rejected") else "completed", source="stage:ingest",
            outputs={"doc_type": cls.get("doc_type"), "classification": {"confidence": cls.get("confidence")},
                     "mrz": "valid" if f.get("mrz") else f.get("mrz_note")}, via=via)
    add("stage:extract", source="stage:ingest")
    llama = report.get("llama_extract") or {}
    for dt in (llama.get("docs") or {}):
        add(f"extract:{dt}", source="stage:extract", via=["store:llm_cache"])
    if any(f.get("mrz") for f in ingest.get("files") or []):
        add("extract:passport", source="op:mrz", via=["op:mrz"])
    fs = report.get("facts_source") or meta.get("facts_source")
    add("stage:facts", source="stage:extract", outputs={"source": fs},
        via=["op:facts_case"] if fs and "case" in fs else ["op:facts_extract"])
    audit = report.get("audit") or {}
    add("stage:rules", source="stage:facts")
    status_map = {"PASS": "passed", "FAIL": "failed", "NEEDS_HUMAN": "needs_human"}
    for r in audit.get("results") or []:
        rid = r.get("rule_id")
        rule = g.nodes.get(f"rule:{rid}")
        via = [f"check:{rule['data'].get('check')}"] if rule else []
        add(f"rule:{rid}", status_map.get(r.get("status"), "completed"), source="stage:rules",
            outputs={"status": r.get("status"), "message": r.get("message"), "evidence": r.get("evidence")},
            via=via)
    for rid in audit.get("skipped_rules") or []:
        add(f"rule:{rid}", "skipped", source="stage:rules", outputs={"reason": "required documents missing"})
    add("stage:outcome", source="stage:rules", outputs={"outcome": audit.get("outcome"),
                                                         "escalations": audit.get("escalations")})
    add("stage:drafts", source="stage:outcome", outputs={"drafts": len(audit.get("drafts") or [])})
    add("store:report", ts=audit.get("created_at"), source="stage:drafts")
    add("gate:human", "awaiting", source="store:report",
        outputs={"human_status": report.get("human_status"), "human_action": report.get("human_action")})
    for row in audit_rows:
        node = {"approve": "lock:approve", "send_back": "lock:send_back", "review": "lock:review"}.get(row.get("action"))
        if not node:
            continue
        add(node, ts=row.get("ts"), source="lock:confirm_token", outputs={"officer": row.get("officer")})
        if row.get("delivery"):
            add("outbound:smtp", ts=row.get("ts"), source=node, outputs=row.get("delivery"))
        add("store:audit_log", ts=row.get("ts"), source=node)
        add("gate:human", "resolved", ts=row.get("ts"), source=node, outputs={"action": row.get("action")})
    return ev


def build_execution_graph(application_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    meta = load_meta(application_id, settings)
    root = app_dir(application_id, settings)
    report = _load_json(root / "email_pipeline_report.json")
    ingest = (report or {}).get("ingest_report") or _load_json(root / "ingest_report.json")
    checklist_path = settings.checklist_dir / f"{meta.get('checklist_id') or 'fr-schengen-short-stay'}.yaml"
    if not checklist_path.exists():
        checklist_path = settings.checklist_dir / "fr-schengen-short-stay.yaml"
    g, checklist = _environment(settings, meta, ingest, checklist_path)

    from app.lock.audit_log import read_audit_log  # read-only; keeps trace importable from pipeline code

    audit_rows = [r for r in read_audit_log(settings, limit=100000) if r.get("application_id") == application_id]

    trace = load_trace(application_id, settings)
    timing_available = bool(trace and trace.get("runs"))
    if timing_available:
        events: list[dict[str, Any]] = []
        for run in trace["runs"]:
            for e in run.get("events") or []:
                events.append({**e, "run": run.get("kind")})
    else:
        events = _legacy_events(meta, report, audit_rows, g)

    # attach incoming-node + offsets; drop events for nodes not in the environment (none expected)
    events = [e for e in events if e.get("node") in g.nodes]
    t0 = next((_iso(e.get("started_at")) for e in events if _iso(e.get("started_at"))), None)
    prev_node: str | None = None
    for i, e in enumerate(events):
        e["seq"] = i + 1
        frm = e.get("source") or e.get("parent") or prev_node
        e["from"] = frm if frm in g.nodes and frm != e["node"] else None
        if e["from"]:
            g.edge(e["from"], e["node"], "flow")
        st, en = _iso(e.get("started_at")), _iso(e.get("ended_at"))
        e["offset_ms"] = round((st - t0).total_seconds() * 1000, 3) if (st and t0) else None
        if e.get("duration_ms") is None and st and en:
            e["duration_ms"] = round((en - st).total_seconds() * 1000, 3)
        prev_node = e["node"]

    # ----- statuses -----
    status_now = str(meta.get("status") or "")
    approved = status_now.startswith("approved")
    sent_back = status_now.startswith("sent_back")
    outcome = meta.get("outcome") or ((report or {}).get("audit") or {}).get("outcome")
    pipeline_error = any(e.get("status") == "error" and e.get("run", "pipeline") == "pipeline" for e in events)

    per_node: dict[str, list[dict[str, Any]]] = {}
    touched: set[str] = set()
    for e in events:
        per_node.setdefault(e["node"], []).append(e)
        for v in e.get("via") or []:
            if v in g.nodes:
                touched.add(v)
                g.edge(e["node"], v, "uses")

    gate_resolved = any(e["status"] == "resolved" for e in per_node.get("gate:human", []))
    human_done = approved or sent_back or gate_resolved

    for nid, n in g.nodes.items():
        evs = per_node.get(nid, [])
        statuses = {e.get("status") for e in evs}
        warning = False
        if nid == "gate:human":
            st = "completed" if human_done else ("awaiting" if evs else "pending")
        elif "error" in statuses and not statuses & {"completed", "passed"}:
            st = "error"
        elif statuses & {"failed", "needs_human"}:
            warning = True
            st = "completed" if human_done else "attention"
        elif evs and statuses <= {"skipped"}:
            st = "skipped"
        elif evs or nid in touched:
            st = "completed"
        elif not n["configured"]:
            st = "disabled"
        else:
            st = "available"
        n["status"] = st
        n["warning"] = warning
        n["event_count"] = len(evs)
        timed = [float(e["duration_ms"]) for e in evs if e.get("duration_ms") is not None]
        n["total_ms"] = round(sum(timed), 3) if timed else None

    if not human_done and not pipeline_error and (report is not None):
        nxt = {"READY_FOR_APPROVAL": ["lock:approve"], "SEND_BACK": ["lock:send_back"]}.get(
            str(outcome), ["lock:approve", "lock:send_back", "lock:review"])
        for nid in ["lock:confirm_token", *nxt, "store:audit_log", "outbound:smtp"]:
            if g.nodes[nid]["status"] in {"available"}:
                g.nodes[nid]["status"] = "pending"
            elif g.nodes[nid]["status"] == "disabled":
                g.nodes[nid]["pending_but_unconfigured"] = True

    # rule results (real) for the detail panel
    audit = (report or {}).get("audit") or {}
    for r in audit.get("results") or []:
        n = g.nodes.get(f"rule:{r.get('rule_id')}")
        if n:
            n["data"]["result"] = {"status": r.get("status"), "message": r.get("message"),
                                   "evidence": r.get("evidence") or []}
    for f in (ingest or {}).get("files") or []:
        n = g.nodes.get(f"file:{f.get('file')}")
        if n:
            prev = f.get("preview") or {}
            n["data"].update({"doc_type": (f.get("classification") or {}).get("doc_type"),
                              "confidence": (f.get("classification") or {}).get("confidence"),
                              "preview_method": prev.get("method"), "pages": len(prev.get("pages") or []),
                              "mrz": bool(f.get("mrz")), "rejected": bool(f.get("rejected"))})

    # ----- sizes: complexity + connections + workload -----
    degree: dict[str, int] = {nid: 0 for nid in g.nodes}
    for (a, b) in g.edges:
        degree[a] += 1
        degree[b] += 1
    for nid, n in g.nodes.items():
        c = _COMPLEXITY.get(n["kind"], 1)
        work = math.log1p(float(n.get("total_ms") or 0)) / 3 + 0.3 * math.log1p(n["event_count"])
        n["degree"] = degree[nid]
        n["size"] = round(min(4.0, 0.55 + 0.32 * c + 0.28 * math.sqrt(degree[nid]) + work * 0.35), 3)

    # ----- summary -----
    pipe = [e for e in events if e.get("run", "pipeline") == "pipeline" and _iso(e.get("started_at"))]
    pipe_start = _iso(pipe[0]["started_at"]) if pipe else None
    pipe_end = max((_iso(e.get("ended_at")) or _iso(e.get("started_at")) for e in pipe), default=None) if pipe else None
    all_t = [x for e in events for x in (_iso(e.get("started_at")), _iso(e.get("ended_at"))) if x]
    attention = [
        {"rule_id": r.get("rule_id"), "status": r.get("status"), "message": r.get("message")}
        for r in audit.get("results") or [] if r.get("status") in {"FAIL", "NEEDS_HUMAN"}
    ]
    if approved:
        state, title = "approved", "Approved by " + str(meta.get("last_officer") or "Gloria")
        explanation = meta.get("human_action") or "Human decision recorded; execution completed."
    elif sent_back:
        state, title = "sent_back", "Sent back"
        explanation = meta.get("human_action") or "Send-back emailed by the officer."
    elif pipeline_error:
        state, title = "error", "Execution error"
        bad = next(e for e in events if e.get("status") == "error")
        explanation = f"{bad.get('label') or bad['node']}: {bad.get('error') or 'failed'}"
    elif report is None:
        state, title, explanation = "not_run", "Not run yet", "No pipeline report for this application."
    elif outcome == "READY_FOR_APPROVAL":
        state, title = "pending_approval", "Pending approval"
        explanation = ("All automated checks passed. The agent stopped safely: only Gloria can approve "
                       "and send the applicant email.")
    elif outcome == "SEND_BACK":
        state, title = "safe_pause", "Paused safely: send-back needed"
        explanation = (f"{sum(1 for a in attention if a['status'] == 'FAIL')} check(s) failed. The agent drafted "
                       "a request to the applicant but cannot send it; Gloria must review and send back.")
    else:
        state, title = "safe_pause", "Paused safely: needs review"
        explanation = (f"{len(attention)} flag(s) need Gloria's judgement (NEEDS_HUMAN). This is not an "
                       "agent failure; the human lock is required by design.")

    return {
        "application_id": application_id,
        "applicant_name": meta.get("applicant_name"),
        "nodes": list(g.nodes.values()),
        "edges": list(g.edges.values()),
        "events": events,
        "clusters": CLUSTERS,
        "summary": {
            "state": state,
            "title": title,
            "explanation": explanation,
            "outcome": outcome,
            "status": status_now,
            "human_action": meta.get("human_action"),
            "attention": attention,
            "event_count": len(events),
            "timing_available": timing_available,
            "pipeline_ms": round((pipe_end - pipe_start).total_seconds() * 1000, 3) if pipe_start and pipe_end else None,
            "total_ms": round((max(all_t) - min(all_t)).total_seconds() * 1000, 3) if all_t else None,
            "started_at": min(all_t).isoformat() if all_t else None,
            "checklist": {"id": checklist.id, "version": checklist.version, "rules": len(checklist.rules)},
            "registry": {"checks": len(REGISTRY), "extractors": len(EXTRACTABLE) + 1},
            "facts_source": meta.get("facts_source"),
            "demo_offline": settings.demo_offline,
        },
    }
