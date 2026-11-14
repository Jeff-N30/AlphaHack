"""VisaRef API — intake + preview/classify/MRZ slice."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.ingest.pipeline import process_application
from app.ingest.render import allowed_suffix
from app.storage.files import create_application, load_meta, store_upload

app = FastAPI(title="VisaRef", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_REPO = Path(__file__).resolve().parents[2]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/checklists")
def list_checklists() -> list[dict[str, str]]:
    settings = get_settings()
    out: list[dict[str, str]] = []
    for path in sorted(settings.checklist_dir.glob("*.yaml")):
        out.append({"id": path.stem, "file": path.name})
    return out


@app.post("/applications")
async def create_app(
    files: list[UploadFile] = File(...),
    checklist_id: str = Form("fr-schengen-short-stay"),
    submission_date: str = Form("2026-11-16"),
) -> dict:
    try:
        sub = date.fromisoformat(submission_date)
    except ValueError as exc:
        raise HTTPException(400, f"bad submission_date: {exc}") from exc

    settings = get_settings()
    if not (settings.checklist_dir / f"{checklist_id}.yaml").exists():
        raise HTTPException(400, f"unknown checklist_id: {checklist_id}")

    meta = create_application(checklist_id=checklist_id, submission_date=sub, settings=settings)
    saved: list[str] = []
    rejected: list[dict[str, str]] = []
    for uf in files:
        name = uf.filename or "upload.bin"
        data = await uf.read()
        if not allowed_suffix(Path(name)):
            rejected.append({"file": name, "reason": "unsupported_type"})
            continue
        path = store_upload(meta["id"], name, data, settings=settings)
        saved.append(path.name)

    return {
        "id": meta["id"],
        "checklist_id": checklist_id,
        "submission_date": sub.isoformat(),
        "files": saved,
        "rejected": rejected,
    }


@app.post("/applications/{application_id}/run")
def run_application(application_id: str) -> dict:
    try:
        load_meta(application_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    return process_application(application_id)


@app.get("/applications/{application_id}")
def get_application(application_id: str) -> dict:
    settings = get_settings()
    try:
        meta = load_meta(application_id, settings)
    except FileNotFoundError as exc:
        raise HTTPException(404, "application not found") from exc
    report_path = settings.data_dir / "applications" / application_id / "ingest_report.json"
    report = None
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return {"meta": meta, "ingest_report": report}


@app.post("/demo/seed-case/{case_id}")
def seed_case(case_id: str) -> dict:
    """Load eval case docs → ingest (OCR/MRZ) → rules AuditReport."""
    from app.ingest.pipeline import seed_from_eval_case
    from app.rules.checklist import load_checklist
    from app.rules.engine import run
    from app.rules.facts_from_case import facts_from_case

    case_dir = _REPO / "eval" / "cases" / case_id
    if not (case_dir / "case.yaml").exists():
        raise HTTPException(404, f"unknown case: {case_id}")
    aid = seed_from_eval_case(case_dir)
    ingest = process_application(aid)
    checklist = load_checklist(_REPO / "checklists" / "fr-schengen-short-stay.yaml")
    audit = run(checklist, facts_from_case(case_dir))
    return {
        "id": aid,
        "case_id": case_id,
        "ingest_report": ingest,
        "audit": audit.model_dump(mode="json"),
    }


@app.get("/demo")
def demo_page():
    """Hackathon demo UI — run one eval case and show outcome."""
    html = (_REPO / "tools" / "demo.html").read_text(encoding="utf-8")
    return HTMLResponse(html)
