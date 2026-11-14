"""Doc text → typed Extraction (LLM). Start with flight / insurance / application_form.

These are the three shapes proven on the legit Jeff demo pack. Hotel/bank next.
Passport identity stays in extract/mrz.py (code), not here.
"""
from __future__ import annotations

from pathlib import Path

from app.config import Settings, get_settings
from app.extract import prompts
from app.extract.fixtures import (
    FIXTURE_APPLICATION_FORM,
    FIXTURE_FLIGHT,
    FIXTURE_INSURANCE,
)
from app.extract.llm import extract_structured
from app.models import (
    ApplicationFormExtraction,
    DocType,
    Extraction,
    FlightBookingExtraction,
    TravelInsuranceExtraction,
)


def extract_flight(
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> FlightBookingExtraction:
    settings = settings or get_settings()
    cache_src = _cache_src(source, text)
    return extract_structured(
        schema=FlightBookingExtraction,
        system=prompts.SYSTEM,
        user=prompts.FLIGHT_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:flight_booking",
        content_for_cache=cache_src,
        offline_fixture=FIXTURE_FLIGHT,
        settings=settings,
    )


def extract_insurance(
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> TravelInsuranceExtraction:
    settings = settings or get_settings()
    cache_src = _cache_src(source, text)
    return extract_structured(
        schema=TravelInsuranceExtraction,
        system=prompts.SYSTEM,
        user=prompts.INSURANCE_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:travel_insurance",
        content_for_cache=cache_src,
        offline_fixture=FIXTURE_INSURANCE,
        settings=settings,
    )


def extract_application_form(
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> ApplicationFormExtraction:
    settings = settings or get_settings()
    cache_src = _cache_src(source, text)
    return extract_structured(
        schema=ApplicationFormExtraction,
        system=prompts.SYSTEM,
        user=prompts.APPLICATION_FORM_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:application_form",
        content_for_cache=cache_src,
        offline_fixture=FIXTURE_APPLICATION_FORM,
        settings=settings,
    )


def extract_by_type(
    doc_type: DocType,
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> Extraction:
    if doc_type == DocType.flight_booking:
        return extract_flight(text, source=source, settings=settings)
    if doc_type == DocType.travel_insurance:
        return extract_insurance(text, source=source, settings=settings)
    if doc_type == DocType.application_form:
        return extract_application_form(text, source=source, settings=settings)
    raise NotImplementedError(
        f"LLM extract not wired yet for {doc_type.value} (hotel/bank/employment next)"
    )


def _cache_src(source: bytes | str | Path | None, text: str) -> bytes | str:
    if source is None:
        return text
    if isinstance(source, Path):
        return source.read_bytes()
    return source
