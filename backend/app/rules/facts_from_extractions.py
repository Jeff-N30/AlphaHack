"""Build Facts from live pipeline extractions (MRZ + Llama), not case.yaml."""
from __future__ import annotations

from datetime import date
from typing import Iterable

from dateutil.relativedelta import relativedelta

from app.models import (
    Conf,
    DocType,
    Extraction,
    MRZ,
    PassportExtraction,
)
from app.rules.context import Facts


def passport_from_mrz(mrz: MRZ, *, page: int = 1) -> PassportExtraction:
    """Passport identity from ICAO MRZ only. issue_date estimated (low confidence)."""
    sex = mrz.sex if mrz.sex in {"M", "F"} else "X"
    # Lebanese biometric passports are typically 10y; mark low confidence so rules can escalate
    issue_date = mrz.expiry_date - relativedelta(years=10)
    meta = {
        k: Conf(page=page, confidence=0.95 if k != "issue_date" else 0.4, raw_text=None)
        for k in (
            "surname",
            "given_names",
            "passport_number",
            "date_of_birth",
            "expiry_date",
            "issue_date",
        )
    }
    return PassportExtraction(
        surname=mrz.surname,
        given_names=mrz.given_names,
        passport_number=mrz.passport_number,
        nationality=mrz.nationality,
        date_of_birth=mrz.date_of_birth,
        sex=sex,  # type: ignore[arg-type]
        issue_date=issue_date,
        expiry_date=mrz.expiry_date,
        mrz_lines=[mrz.line1, mrz.line2],
        mrz=mrz,
        field_meta=meta,
    )


def facts_from_extractions(
    extractions: Iterable[Extraction],
    *,
    submission_date: date,
    application_id: str,
    profile: str = "employee",
) -> Facts:
    documents: dict[DocType, list[Extraction]] = {}
    for ex in extractions:
        documents.setdefault(ex.doc_type, []).append(ex)
    return Facts(
        documents=documents,
        submission_date=submission_date,
        profile=profile,
        application_id=application_id,
    )
