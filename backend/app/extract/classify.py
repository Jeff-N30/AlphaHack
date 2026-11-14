"""Decide doc_type from file text: strong keywords first, else Llama.

Filename is never trusted alone. Unknown / low confidence → Gloria later.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.extract.llm import extract_structured
from app.ingest.classify_keywords import classify_text
from app.models import ClassifiedPage, DocType

# Above this, keywords are good enough — skip Llama (cheap + stable).
_KEYWORD_TRUST = 0.70


class DocTypePrediction(BaseModel):
    """LLM-only payload; file/page attached by caller."""

    doc_type: DocType
    confidence: float = Field(..., ge=0, le=1)


_SYSTEM = """You classify one visa-supporting document from its text.
Return JSON only: doc_type + confidence (0-1).
Allowed doc_type values exactly:
application_form, photo, passport, flight_booking, hotel_booking, travel_insurance,
bank_statement, employment_letter, payslip, cnss_certificate, family_register,
travel_plan, unknown.
Rules:
- Use the document body, not the filename.
- France-Visas / Harmonised Schengen application → application_form (not employment_letter).
- Amadeus / e-ticket / BEY-CDG itinerary → flight_booking.
- Travel insurance cover note → travel_insurance.
- If unsure, doc_type=unknown and confidence < 0.5.
- Never invent PASS/FAIL.
"""

_USER = """Classify this document.

--- TEXT (may be OCR, truncated) ---
<<<TEXT>>>
"""


def classify_document(
    text: str,
    *,
    filename: str = "",
    page: int = 1,
    settings: Settings | None = None,
) -> ClassifiedPage:
    """Keyword fast-path when clear; otherwise Llama (offline → keyword fixture)."""
    settings = settings or get_settings()
    kw = classify_text(text, filename=filename, page=page)

    if kw.doc_type != DocType.unknown and kw.confidence >= _KEYWORD_TRUST:
        return ClassifiedPage(
            file=filename,
            page=page,
            doc_type=kw.doc_type,
            confidence=kw.confidence,
        )

    # Ambiguous or unknown → ask Llama (DEMO_OFFLINE replays keyword as fixture)
    fixture = DocTypePrediction(doc_type=kw.doc_type, confidence=kw.confidence)
    try:
        pred = extract_structured(
            schema=DocTypePrediction,
            system=_SYSTEM,
            user=_USER.replace("<<<TEXT>>>", (text or "")[:12_000]),
            step="classify:doc_type",
            content_for_cache=f"classify|{filename}|{(text or '')[:4000]}",
            offline_fixture=fixture,
            settings=settings,
        )
    except Exception:
        return kw

    # Prefer unknown over a weak wrong guess
    if pred.doc_type == DocType.unknown or pred.confidence < 0.45:
        if kw.doc_type != DocType.unknown and kw.confidence >= pred.confidence:
            return kw
        return ClassifiedPage(
            file=filename,
            page=page,
            doc_type=DocType.unknown,
            confidence=min(pred.confidence, 0.4),
        )

    return ClassifiedPage(
        file=filename,
        page=page,
        doc_type=pred.doc_type,
        confidence=pred.confidence,
    )
