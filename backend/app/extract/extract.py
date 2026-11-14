"""Doc text → typed Extraction (LLM).

Passport identity stays in extract/mrz.py (code), not here.
"""
from __future__ import annotations

from pathlib import Path

from app.config import Settings, get_settings
from app.extract import prompts
from app.extract.fixtures import (
    FIXTURE_APPLICATION_FORM,
    FIXTURE_BANK,
    FIXTURE_EMPLOYMENT,
    FIXTURE_FAMILY_REGISTER,
    FIXTURE_FLIGHT,
    FIXTURE_HOTEL,
    FIXTURE_INSURANCE,
    FIXTURE_PAYSLIP,
)
from app.extract.llm import extract_structured
from app.models import (
    ApplicationFormExtraction,
    BankStatementExtraction,
    DocType,
    EmploymentLetterExtraction,
    Extraction,
    FamilyRegisterExtraction,
    FlightBookingExtraction,
    GenericExtraction,
    HotelBookingExtraction,
    PayslipExtraction,
    TravelInsuranceExtraction,
)

_GENERIC_TYPES = {
    DocType.cnss_certificate,
    DocType.photo,
    DocType.travel_plan,
    DocType.unknown,
}


def extract_flight(
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> FlightBookingExtraction:
    settings = settings or get_settings()
    return extract_structured(
        schema=FlightBookingExtraction,
        system=prompts.SYSTEM,
        user=prompts.FLIGHT_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:flight_booking",
        content_for_cache=_cache_src(source, text),
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
    return extract_structured(
        schema=TravelInsuranceExtraction,
        system=prompts.SYSTEM,
        user=prompts.INSURANCE_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:travel_insurance",
        content_for_cache=_cache_src(source, text),
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
    return extract_structured(
        schema=ApplicationFormExtraction,
        system=prompts.SYSTEM,
        user=prompts.APPLICATION_FORM_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:application_form",
        content_for_cache=_cache_src(source, text),
        offline_fixture=FIXTURE_APPLICATION_FORM,
        settings=settings,
    )


def extract_hotel(
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> HotelBookingExtraction:
    settings = settings or get_settings()
    return extract_structured(
        schema=HotelBookingExtraction,
        system=prompts.SYSTEM,
        user=prompts.HOTEL_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:hotel_booking",
        content_for_cache=_cache_src(source, text),
        offline_fixture=FIXTURE_HOTEL,
        settings=settings,
    )


def extract_bank(
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> BankStatementExtraction:
    settings = settings or get_settings()
    return extract_structured(
        schema=BankStatementExtraction,
        system=prompts.SYSTEM,
        user=prompts.BANK_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:bank_statement",
        content_for_cache=_cache_src(source, text),
        offline_fixture=FIXTURE_BANK,
        settings=settings,
    )


def extract_employment(
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> EmploymentLetterExtraction:
    settings = settings or get_settings()
    return extract_structured(
        schema=EmploymentLetterExtraction,
        system=prompts.SYSTEM,
        user=prompts.EMPLOYMENT_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:employment_letter",
        content_for_cache=_cache_src(source, text),
        offline_fixture=FIXTURE_EMPLOYMENT,
        settings=settings,
    )


def extract_payslip(
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> PayslipExtraction:
    settings = settings or get_settings()
    return extract_structured(
        schema=PayslipExtraction,
        system=prompts.SYSTEM,
        user=prompts.PAYSLIP_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:payslip",
        content_for_cache=_cache_src(source, text),
        offline_fixture=FIXTURE_PAYSLIP,
        settings=settings,
    )


def extract_family_register(
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> FamilyRegisterExtraction:
    settings = settings or get_settings()
    return extract_structured(
        schema=FamilyRegisterExtraction,
        system=prompts.SYSTEM,
        user=prompts.FAMILY_REGISTER_USER.replace("<<<TEXT>>>", text[:20_000]),
        step="extract:family_register",
        content_for_cache=_cache_src(source, text),
        offline_fixture=FIXTURE_FAMILY_REGISTER,
        settings=settings,
    )


def extract_generic(
    doc_type: DocType,
    text: str,
    *,
    source: bytes | str | Path | None = None,
    settings: Settings | None = None,
) -> GenericExtraction:
    """Presence-only docs (CNSS / photo / travel plan) — no field verdicts."""
    _ = source, settings
    if doc_type not in _GENERIC_TYPES:
        doc_type = DocType.unknown
    snippet = " ".join((text or "").split())[:160]
    return GenericExtraction(
        doc_type=doc_type,
        language="en",
        anomaly_flags=[],
        names_found=[],
        summary=snippet or doc_type.value,
        field_meta={},
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
    if doc_type == DocType.hotel_booking:
        return extract_hotel(text, source=source, settings=settings)
    if doc_type == DocType.bank_statement:
        return extract_bank(text, source=source, settings=settings)
    if doc_type == DocType.employment_letter:
        return extract_employment(text, source=source, settings=settings)
    if doc_type == DocType.payslip:
        return extract_payslip(text, source=source, settings=settings)
    if doc_type == DocType.family_register:
        return extract_family_register(text, source=source, settings=settings)
    if doc_type in _GENERIC_TYPES:
        return extract_generic(doc_type, text, source=source, settings=settings)
    raise NotImplementedError(f"LLM extract not wired for {doc_type.value}")


def _cache_src(source: bytes | str | Path | None, text: str) -> bytes | str:
    if source is None:
        return text
    if isinstance(source, Path):
        return source.read_bytes()
    return source
