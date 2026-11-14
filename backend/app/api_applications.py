"""Gloria queue APIs: list applications + load audit reports + file preview."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.storage.files import app_dir, load_meta


def list_applications(settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    root = settings.data_dir / "applications"
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_dir():
            continue
        meta_path = path / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        report = _load_report(path)
        audit = (report or {}).get("audit") or {}
        person = _applicant_summary(report, meta)
        drafts = audit.get("drafts") or []
        rows.append(
            {
                "id": meta.get("id", path.name),
                "applicant_name": person.get("name"),
                "trip_summary": person.get("trip"),
                "case_id": (report or {}).get("case_id") or meta.get("case_id"),
                "status": meta.get("status", "unknown"),
                "outcome": meta.get("outcome") or audit.get("outcome"),
                "human_required": meta.get("human_required", False),
                "human_action": meta.get("human_action"),
                "checklist_id": meta.get("checklist_id"),
                "submission_date": meta.get("submission_date"),
                "created_at": meta.get("created_at"),
                "email_uid": meta.get("email_uid"),
                "email_source": meta.get("email_source") or (report or {}).get("email_source"),
                "escalations": audit.get("escalations"),
                "has_report": report is not None,
                "has_draft": bool(drafts),
            }
        )
    return rows


def get_application_detail(application_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    meta = load_meta(application_id, settings)
    root = app_dir(application_id, settings)
    report = _load_report(root)
    person = _applicant_summary(report, meta)
    files = []
    raw = root / "raw"
    if raw.exists():
        files = sorted(p.name for p in raw.iterdir() if p.is_file())
    enriched = {
        **meta,
        "applicant_name": person.get("name"),
        "trip_summary": person.get("trip"),
        "case_id": (report or {}).get("case_id") or meta.get("case_id"),
    }
    return {
        "meta": enriched,
        "files": files,
        "report": report,
    }


def resolve_application_file(
    application_id: str,
    filename: str,
    settings: Settings | None = None,
) -> Path:
    """Safe path under applications/<id>/raw/ for document preview."""
    settings = settings or get_settings()
    name = Path(filename).name
    if not name or name != filename or ".." in filename:
        raise FileNotFoundError("invalid filename")
    path = app_dir(application_id, settings) / "raw" / name
    if not path.is_file():
        raise FileNotFoundError(name)
    return path


def _load_report(root: Path) -> dict[str, Any] | None:
    for name in ("email_pipeline_report.json", "ingest_report.json"):
        path = root / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def _applicant_summary(
    report: dict[str, Any] | None,
    meta: dict[str, Any] | None = None,
) -> dict[str, str | None]:
    """Best-effort name + trip line for Gloria's queue (never invents)."""
    if meta and meta.get("triage_person_name"):
        triage_name = str(meta["triage_person_name"]).strip() or None
    else:
        triage_name = None
    if not report:
        return {"name": triage_name, "trip": None}
    docs = ((report.get("llama_extract") or {}).get("docs") or {})
    form = docs.get("application_form") or {}
    flight = docs.get("flight_booking") or {}
    insurance = docs.get("travel_insurance") or {}
    bank = docs.get("bank_statement") or {}
    emp = docs.get("employment_letter") or {}

    name: str | None = None
    surname = form.get("surname")
    given = form.get("given_names")
    if surname or given:
        name = " ".join(p for p in (given, surname) if p).strip() or None
    if not name and insurance.get("insured_name"):
        name = str(insurance["insured_name"]).strip() or None
    if not name and bank.get("account_holder"):
        name = str(bank["account_holder"]).strip() or None
    if not name and emp.get("employee_name"):
        name = str(emp["employee_name"]).strip() or None
    if not name:
        passengers = flight.get("passenger_names") or []
        if passengers:
            name = str(passengers[0]).strip() or None
    if not name:
        name = triage_name

    trip: str | None = None
    segs = flight.get("segments") or []
    if segs:
        first, last = segs[0], segs[-1]
        origin = first.get("from_airport")
        dest = first.get("to_airport")
        dep = first.get("departure_date")
        ret = last.get("departure_date") if len(segs) > 1 else None
        bits = [
            b
            for b in (
                f"{origin}→{dest}" if origin and dest else None,
                dep,
                f"return {ret}" if ret else None,
            )
            if b
        ]
        trip = " · ".join(bits) if bits else None
    if not trip:
        arr = form.get("intended_arrival")
        dep = form.get("intended_departure")
        if arr or dep:
            trip = " · ".join(
                p
                for p in (
                    f"arrive {arr}" if arr else None,
                    f"leave {dep}" if dep else None,
                )
                if p
            )

    return {"name": name, "trip": trip}
