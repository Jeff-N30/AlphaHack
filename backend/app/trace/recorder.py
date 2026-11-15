"""Context-local execution recorder.

`span(...)` is a no-op unless a run is active (`start_run`), so callers and tests that
don't trace behave exactly as before. Recorded runs are written to
`applications/<id>/execution_trace.json`.
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator

from app.config import Settings, get_settings
from app.storage.files import app_dir

logger = logging.getLogger(__name__)

TRACE_FILE = "execution_trace.json"
TRACE_VERSION = 1

_current: ContextVar["TraceRecorder | None"] = ContextVar("visaref_trace", default=None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(value: Any, depth: int = 0) -> Any:
    """Small, safe copy of inputs/outputs (no file bytes, bounded size)."""
    if depth > 4:
        return str(value)[:200]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 600 else value[:600] + "…"
    if isinstance(value, dict):
        return {str(k): _jsonable(v, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v, depth + 1) for v in list(value)[:40]]
    return str(value)[:300]


class TraceRecorder:
    def __init__(self, application_id: str, kind: str) -> None:
        self.application_id = application_id
        self.kind = kind
        self.started_at = _now_iso()
        self.ended_at: str | None = None
        self.events: list[dict[str, Any]] = []
        self._stack: list[str] = []
        self._outs: list[dict[str, Any]] = []

    def record(
        self,
        node: str,
        *,
        label: str | None = None,
        status: str = "completed",
        started_at: str | None = None,
        ended_at: str | None = None,
        duration_ms: float | None = None,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        via: list[str] | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        """Record an instantaneous or externally-timed event."""
        now = _now_iso()
        ev = {
            "id": f"{self.kind}-{len(self.events) + 1}",
            "node": node,
            "label": label,
            "status": status,
            "started_at": started_at or now,
            "ended_at": ended_at if ended_at is not None else (started_at or now),
            "duration_ms": duration_ms,
            "inputs": _jsonable(inputs or {}),
            "outputs": _jsonable(outputs or {}),
            "via": list(via or []),
            "parent": self._stack[-1] if self._stack else None,
            "source": source or (self._stack[-1] if self._stack else None),
        }
        self.events.append(ev)
        return ev

    @contextmanager
    def span(
        self,
        node: str,
        *,
        label: str | None = None,
        inputs: dict[str, Any] | None = None,
        via: list[str] | None = None,
        source: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        ev: dict[str, Any] = {
            "id": f"{self.kind}-{len(self.events) + 1}",
            "node": node,
            "label": label,
            "status": "running",
            "started_at": _now_iso(),
            "ended_at": None,
            "duration_ms": None,
            "inputs": _jsonable(inputs or {}),
            "outputs": {},
            "via": list(via or []),
            "parent": self._stack[-1] if self._stack else None,
            "source": source,
        }
        self.events.append(ev)
        out: dict[str, Any] = {}
        t0 = time.perf_counter()
        self._stack.append(node)
        self._outs.append(out)
        try:
            yield out
            ev["status"] = out.pop("_status", "completed")
        except Exception as exc:
            ev["status"] = "error"
            ev["error"] = f"{type(exc).__name__}: {exc}"[:500]
            raise
        finally:
            self._stack.pop()
            self._outs.pop()
            ev["duration_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            ev["ended_at"] = _now_iso()
            extra_via = out.pop("_via", None)
            if extra_via:
                ev["via"] = list(dict.fromkeys([*ev["via"], *extra_via]))
            ev["outputs"] = _jsonable(out)

    def to_run(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "started_at": self.started_at,
            "ended_at": self.ended_at or _now_iso(),
            "events": self.events,
        }


def current() -> TraceRecorder | None:
    return _current.get()


@contextmanager
def span(node: str, **kw: Any) -> Iterator[dict[str, Any]]:
    """Trace a block if a run is active; otherwise yield a throwaway dict."""
    rec = _current.get()
    if rec is None:
        yield {}
        return
    with rec.span(node, **kw) as out:
        yield out


def annotate(*, via: list[str] | None = None, **fields: Any) -> None:
    """Attach fields (and touched capability nodes) to the innermost open span."""
    rec = _current.get()
    if rec is None or not rec._outs:
        return
    out = rec._outs[-1]
    out.update(fields)
    if via:
        out["_via"] = list(dict.fromkeys([*(out.get("_via") or []), *via]))


def record(node: str, **kw: Any) -> dict[str, Any] | None:
    rec = _current.get()
    if rec is None:
        return None
    return rec.record(node, **kw)


def trace_path(application_id: str, settings: Settings | None = None):
    return app_dir(application_id, settings or get_settings()) / TRACE_FILE


def load_trace(application_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    path = trace_path(application_id, settings)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@contextmanager
def start_run(
    application_id: str,
    *,
    kind: str,
    settings: Settings | None = None,
    replace: bool = False,
) -> Iterator[TraceRecorder]:
    """Activate a recorder for this context; persist it when the block exits (even on error).

    kind="pipeline" with replace=True starts a fresh trace (a re-run supersedes older runs);
    other kinds (lock actions) are appended to the existing trace.
    """
    settings = settings or get_settings()
    rec = TraceRecorder(application_id, kind)
    token = _current.set(rec)
    try:
        yield rec
    finally:
        _current.reset(token)
        rec.ended_at = _now_iso()
        try:
            path = trace_path(application_id, settings)
            existing = None if replace else load_trace(application_id, settings)
            doc = existing or {"version": TRACE_VERSION, "application_id": application_id, "runs": []}
            doc["runs"].append(rec.to_run())
            path.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 — tracing must never break the pipeline
            logger.warning("could not persist execution trace for %s: %s", application_id, exc)
