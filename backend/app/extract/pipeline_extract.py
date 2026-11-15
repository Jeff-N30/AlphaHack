"""After ingest: MRZ + Llama extract → list[Extraction] for the rules engine."""
from __future__ import annotations

import logging
from typing import Any

from app.config import Settings, get_settings
from app.extract.extract import extract_by_type
from app.ingest.render import read_preview
from app.models import DocType, Extraction, MRZ
from app.rules.facts_from_extractions import passport_from_mrz
from app.storage.files import app_dir
from app.trace.recorder import record as trace_record
from app.trace.recorder import span as trace_span

logger = logging.getLogger(__name__)

EXTRACTABLE = {
    DocType.flight_booking,
    DocType.travel_insurance,
    DocType.application_form,
    DocType.hotel_booking,
    DocType.bank_statement,
    DocType.employment_letter,
    DocType.payslip,
    DocType.family_register,
    DocType.cnss_certificate,
    DocType.photo,
    DocType.travel_plan,
}


def extract_application_docs(
    application_id: str,
    ingest: dict[str, Any],
    *,
    settings: Settings | None = None,
) -> tuple[list[Extraction], dict[str, Any]]:
    """Return (extractions, llama_docs_by_type) from classified files + MRZ."""
    settings = settings or get_settings()
    extractions: list[Extraction] = []
    llama_docs: dict[str, Any] = {}
    raw = app_dir(application_id, settings) / "raw"

    for entry in ingest.get("files") or []:
        mrz_raw = entry.get("mrz")
        if not mrz_raw:
            continue
        try:
            extractions.append(passport_from_mrz(MRZ.model_validate(mrz_raw)))
            trace_record(
                "extract:passport",
                label="Passport fields (MRZ)",
                inputs={"file": entry.get("file")},
                outputs={"source": "mrz", "fields": sorted((mrz_raw or {}).keys())[:20]},
                via=["op:mrz"],
                source=f"file:{entry.get('file')}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("bad MRZ on %s: %s", entry.get("file"), exc)
            trace_record(
                "extract:passport",
                label="Passport fields (MRZ)",
                status="error",
                inputs={"file": entry.get("file")},
                outputs={"error": str(exc)[:300]},
                source=f"file:{entry.get('file')}",
            )

    for entry in ingest.get("files") or []:
        if entry.get("rejected"):
            continue
        fname = entry.get("file") or ""
        path = raw / fname
        if not path.exists():
            continue
        cls = (entry.get("classification") or {}).get("doc_type")
        try:
            dtype = DocType(cls) if cls else DocType.unknown
        except ValueError:
            dtype = DocType.unknown
        if dtype not in EXTRACTABLE:
            from app.extract.classify import classify_document

            prev = read_preview(path, max_pages=4)
            dtype = classify_document(prev.text, filename=fname, settings=settings).doc_type
        if dtype not in EXTRACTABLE:
            continue
        try:
            with trace_span(
                f"extract:{dtype.value}",
                label=f"Extract {dtype.value.replace('_', ' ')}",
                inputs={"file": fname, "doc_type": dtype.value},
                source=f"file:{fname}",
            ) as ex_out:
                prev = read_preview(path, max_pages=6)
                ex = extract_by_type(dtype, prev.text, source=path, settings=settings)
                dumped = ex.model_dump(mode="json")
                ex_out["fields"] = sorted(
                    k for k, v in dumped.items()
                    if v not in (None, [], {}, "") and k not in {"field_meta", "doc_type"}
                )[:30]
                ex_out["anomaly_flags"] = dumped.get("anomaly_flags") or []
            extractions.append(ex)
            # payslips: keep list under same key
            if dtype == DocType.payslip:
                bucket = llama_docs.setdefault("payslip", [])
                if isinstance(bucket, list):
                    bucket.append(ex.model_dump(mode="json"))
            else:
                llama_docs[dtype.value] = ex.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            logger.warning("extract failed %s: %s", fname, exc)

    return extractions, llama_docs
