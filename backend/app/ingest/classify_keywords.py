"""Heuristic doc-type from preview text (no LLM). Filename is a hint only."""
from __future__ import annotations

import re
from pathlib import Path

from app.models import ClassifiedPage, DocType

_PATTERNS: list[tuple[DocType, list[str]]] = [
    # application_form first: France-Visas PDFs mention employer/Schengen and used to steal other labels
    (
        DocType.application_form,
        [
            r"HARMONISED APPLICATION",
            r"APPLICATION FOR SCHENGEN",
            r"FRANCE-VISAS",
            r"VISA APPLICATION",
            r"APPLICABLE VISA FEE",
            r"REQUIRED SUPPORTING DOCUMENTS TO SUBMIT",
            r"SHORT-STAY",
        ],
    ),
    (DocType.passport, [r"\bPASSPORT\b", r"P<[A-Z]{3}", r"REPUBLIC OF LEBANON", r"MACHINE READABLE"]),
    (
        DocType.flight_booking,
        [r"E-?TICKET", r"FLIGHT\s+BOOKING", r"BOOKING REFERENCE", r"BOOKING REF", r"CHECKMYTRIP", r"\bCDG\b", r"\bBEY\b"],
    ),
    (DocType.hotel_booking, [r"BOOKING CONFIRMATION", r"CHECK-?IN", r"CHECK-?OUT", r"HOTEL"]),
    (
        DocType.travel_insurance,
        [r"TRAVEL INSURANCE", r"COVER NOTE", r"REPATRIATION", r"POLICY NUMBER", r"30[\s,]?000", r"MEDICAL COVERAGE"],
    ),
    (DocType.bank_statement, [r"ACCOUNT STATEMENT", r"CLOSING BALANCE", r"\bIBAN\b", r"TRANSACTION"]),
    (
        DocType.employment_letter,
        [r"TO WHOM IT MAY CONCERN", r"EMPLOYMENT LETTER", r"EMPLOYER LETTER", r"LEAVE APPROVED", r"MONTHLY SALARY"],
    ),
    (DocType.payslip, [r"\bPAYSLIP\b", r"NET PAY", r"PAY PERIOD"]),
    (DocType.cnss_certificate, [r"\bCNSS\b", r"SOCIAL SECURITY"]),
    (DocType.family_register, [r"FAMILY REGISTER", r"EKHRAJ", r"KAID AILY", r"EXTRACT OF FAMILY"]),
    (DocType.travel_plan, [r"TRAVEL PLAN", r"ITINERARY"]),
    (DocType.photo, [r"SPECIMEN\s+(ID\s+)?PHOTO", r"\bID PHOTO\b", r"BIOMETRIC PHOTO"]),
]

_NAME_HINTS: dict[str, DocType] = {
    "passport": DocType.passport,
    "flight": DocType.flight_booking,
    "hotel": DocType.hotel_booking,
    "insurance": DocType.travel_insurance,
    "bank": DocType.bank_statement,
    "employment": DocType.employment_letter,
    "payslip": DocType.payslip,
    "cnss": DocType.cnss_certificate,
    "family": DocType.family_register,
    "ekhraj": DocType.family_register,
    "application": DocType.application_form,
    "travel_plan": DocType.travel_plan,
    "photo": DocType.photo,
}


def classify_text(text: str, *, filename: str = "", page: int = 1) -> ClassifiedPage:
    upper = (text or "").upper()
    best: DocType | None = None
    best_score = 0
    for dtype, pats in _PATTERNS:
        score = sum(1 for p in pats if re.search(p, upper, re.I))
        if score > best_score:
            best_score = score
            best = dtype

    if best is not None and best_score >= 1:
        conf = min(0.55 + 0.15 * best_score, 0.95)
        return ClassifiedPage(file=filename, page=page, doc_type=best, confidence=conf)

    stem = re.sub(r"[^a-z0-9_]+", "_", Path(filename).stem.lower())
    # ID photos are usually image-only (no OCR text). Prefer a strong filename
    # hint over an LLM guess on empty text — never trust filename when body text exists.
    short_body = len(re.sub(r"\s+", "", upper)) < 40
    for key, dtype in _NAME_HINTS.items():
        if key in stem:
            conf = 0.75 if (dtype == DocType.photo and short_body) else 0.35
            return ClassifiedPage(file=filename, page=page, doc_type=dtype, confidence=conf)

    return ClassifiedPage(file=filename, page=page, doc_type=DocType.unknown, confidence=0.2)
