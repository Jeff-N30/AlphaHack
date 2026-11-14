"""VisaRef core schemas (Pydantic v2).

Rule of the house: the LLM fills *Extraction* models only. CheckResult is produced
by deterministic code in rules/ (except mode=llm_flag rules, which can only emit
NEEDS_HUMAN). Never ask the LLM for a PASS/FAIL.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


# ----------------------------------------------------------------- primitives
class Conf(BaseModel):
    """Every extracted field carries where it came from + model confidence."""
    page: int = Field(1, ge=1)
    confidence: float = Field(..., ge=0, le=1)
    raw_text: Optional[str] = Field(None, description="Verbatim snippet as printed")


class Money(BaseModel):
    amount: float
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")  # ISO 4217; no LBP logic in rules


class DocType(str, Enum):
    application_form = "application_form"
    photo = "photo"
    passport = "passport"
    flight_booking = "flight_booking"
    hotel_booking = "hotel_booking"
    travel_insurance = "travel_insurance"
    bank_statement = "bank_statement"
    employment_letter = "employment_letter"
    payslip = "payslip"
    cnss_certificate = "cnss_certificate"
    family_register = "family_register"
    travel_plan = "travel_plan"
    unknown = "unknown"


class BaseExtraction(BaseModel):
    doc_type: DocType
    language: Optional[str] = Field(None, description="ar | fr | en | mixed")
    anomaly_flags: list[str] = Field(default_factory=list, description="LLM-observed oddities only; never verdicts")
    field_meta: dict[str, Conf] = Field(default_factory=dict, description="key = field name")


# ----------------------------------------------------------------- documents
class MRZ(BaseModel):
    """Parsed deterministically (passporteye / mrz), NOT by the LLM."""
    line1: str
    line2: str
    surname: str
    given_names: str
    passport_number: str
    nationality: str
    date_of_birth: date
    sex: Literal["M", "F", "<"]
    expiry_date: date
    checksums_valid: bool
    failed_checks: list[str] = Field(default_factory=list)


class PassportExtraction(BaseExtraction):
    doc_type: Literal[DocType.passport] = DocType.passport
    surname: str
    given_names: str
    surname_ar: Optional[str] = None
    given_names_ar: Optional[str] = None
    passport_number: str
    nationality: str = Field(..., description="ISO 3166 alpha-3, e.g. LBN")
    date_of_birth: date
    sex: Literal["M", "F", "X"]
    issue_date: date
    expiry_date: date
    place_of_issue: Optional[str] = None
    mrz_lines: list[str] = Field(default_factory=list, description="As read by LLM; code re-parses")
    mrz: Optional[MRZ] = None  # filled by code


class FlightSegment(BaseModel):
    from_airport: str = Field(..., pattern=r"^[A-Z]{3}$")
    to_airport: str = Field(..., pattern=r"^[A-Z]{3}$")
    to_country: Optional[str] = Field(None, description="ISO alpha-2")
    departure_date: date
    flight_number: Optional[str] = None


class FlightBookingExtraction(BaseExtraction):
    doc_type: Literal[DocType.flight_booking] = DocType.flight_booking
    passenger_names: list[str]
    booking_reference: Optional[str] = None
    passport_number: Optional[str] = None
    segments: list[FlightSegment]


class HotelBookingExtraction(BaseExtraction):
    doc_type: Literal[DocType.hotel_booking] = DocType.hotel_booking
    guest_names: list[str]
    hotel_name: str
    city: str
    country: str = Field(..., description="ISO alpha-2")
    check_in: date
    check_out: date
    confirmation_number: Optional[str] = None
    prepaid_or_free_cancellation: Optional[bool] = None


class TravelInsuranceExtraction(BaseExtraction):
    doc_type: Literal[DocType.travel_insurance] = DocType.travel_insurance
    insured_name: str
    date_of_birth: Optional[date] = None
    passport_number: Optional[str] = None
    insurer: str
    policy_number: str
    coverage: Money
    territory: Literal["SCHENGEN", "EUROPE", "WORLDWIDE", "OTHER", "UNCLEAR"]
    territory_raw: str
    start_date: date
    end_date: date
    covers: list[Literal["emergency_medical", "hospitalisation", "repatriation", "other"]]


class Transaction(BaseModel):
    date: date
    description: str
    amount: float  # + credit, - debit
    balance_after: Optional[float] = None


class BankStatementExtraction(BaseExtraction):
    doc_type: Literal[DocType.bank_statement] = DocType.bank_statement
    account_holder: str
    bank_name: str
    account_currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    account_type_raw: Optional[str] = None  # e.g. "Fresh USD current account" (shown to Gloria, not ruled on)
    period_start: date
    period_end: date
    issue_date: date
    opening_balance: float
    closing_balance: float
    has_bank_stamp: bool
    transactions: list[Transaction] = Field(default_factory=list)


class EmploymentLetterExtraction(BaseExtraction):
    doc_type: Literal[DocType.employment_letter] = DocType.employment_letter
    employee_name: str
    employer_name: str
    position: Optional[str] = None
    hire_date: Optional[date] = None
    monthly_salary: Optional[Money] = None
    leave_start: Optional[date] = None
    leave_end: Optional[date] = None
    letter_date: Optional[date] = None
    signed_and_stamped: Optional[bool] = None


class PayslipExtraction(BaseExtraction):
    doc_type: Literal[DocType.payslip] = DocType.payslip
    employee_name: str
    employer_name: str
    period_month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    net_pay: Money


class FamilyRegisterExtraction(BaseExtraction):
    doc_type: Literal[DocType.family_register] = DocType.family_register
    head_of_family: Optional[str] = None
    members: list[str] = Field(default_factory=list)
    issue_date: date
    translated: Optional[bool] = None


class ApplicationFormExtraction(BaseExtraction):
    doc_type: Literal[DocType.application_form] = DocType.application_form
    surname: str
    given_names: str
    date_of_birth: date
    passport_number: str
    expiry_date: date
    france_visas_reference: Optional[str] = None
    intended_arrival: Optional[date] = None
    intended_departure: Optional[date] = None
    signed: Optional[bool] = None


class GenericExtraction(BaseExtraction):
    """photo, cnss_certificate, travel_plan, unknown: presence + names only."""
    names_found: list[str] = Field(default_factory=list)
    summary: Optional[str] = None


Extraction = Union[
    PassportExtraction, FlightBookingExtraction, HotelBookingExtraction,
    TravelInsuranceExtraction, BankStatementExtraction, EmploymentLetterExtraction,
    PayslipExtraction, FamilyRegisterExtraction, ApplicationFormExtraction, GenericExtraction,
]


# ----------------------------------------------------------------- classification
class ClassifiedPage(BaseModel):
    file: str
    page: int
    doc_type: DocType
    confidence: float = Field(..., ge=0, le=1)


# ----------------------------------------------------------------- checks
class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_HUMAN = "NEEDS_HUMAN"


class Evidence(BaseModel):
    doc: str = Field(..., description="file name or doc id, e.g. passport.png")
    field: str = Field(..., description="e.g. passport.expiry_date")
    value: Optional[str] = None
    page: Optional[int] = None


class CheckResult(BaseModel):
    rule_id: str
    status: Status
    evidence: list[Evidence] = Field(default_factory=list)
    message: str
    mode: Literal["code", "llm_flag", "manual"] = "code"
    on_fail: Optional[Literal["request", "flag"]] = None


class Outcome(str, Enum):
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    NEEDS_GLORIA = "NEEDS_GLORIA"
    SEND_BACK = "SEND_BACK"


class CostLine(BaseModel):
    step: str            # classify | extract:passport | draft_message ...
    model: str
    input_tokens: int
    output_tokens: int   # include thinking tokens
    usd: float


class AuditReport(BaseModel):
    application_id: str
    checklist_id: str
    checklist_version: str
    submission_date: date
    results: list[CheckResult]
    skipped_rules: list[str] = Field(default_factory=list, description="dependency doc missing / not applicable")
    outcome: Outcome
    escalations: int = Field(..., description="count of non-manual NEEDS_HUMAN + flag FAILs")
    drafts: list["ApplicantMessageDraft"] = Field(default_factory=list, description="DRAFT only; never sent by the pipeline")
    cost: list[CostLine] = Field(default_factory=list)
    total_usd: float = 0.0
    created_at: datetime


# ----------------------------------------------------------------- human lock
class DraftStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"   # set ONLY by POST /drafts/{id}/send with a Gloria session
    SENT = "SENT"
    DISCARDED = "DISCARDED"


class ApplicantMessageDraft(BaseModel):
    id: str
    application_id: str
    channel: Literal["email", "copy"]
    language: Literal["ar-LB", "fr", "en"]
    body: str
    rule_ids: list[str]
    status: DraftStatus = DraftStatus.DRAFT
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


AuditReport.model_rebuild()
