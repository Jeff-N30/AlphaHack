"""Local SQLite metadata database for VisaRef applications and documents."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.config import Settings, get_settings


class ApplicationRow(SQLModel, table=True):
    __tablename__ = "applications"

    id: str = Field(primary_key=True)
    checklist_id: str
    submission_date: date
    status: str = "created"
    outcome: str | None = None
    human_required: bool = True
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    place_of_birth: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    passport_issue_date: date | None = None
    passport_expiry_date: date | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentRow(SQLModel, table=True):
    __tablename__ = "documents"

    id: str = Field(primary_key=True)
    application_id: str = Field(foreign_key="applications.id", index=True)
    document_type: str = "unknown"
    original_filename: str
    stored_path: str
    sha256: str
    byte_size: int
    language: str | None = None
    page_count: int | None = None
    extraction_json: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TravelPlanRow(SQLModel, table=True):
    __tablename__ = "travel_plans"

    id: str = Field(primary_key=True)
    application_id: str = Field(foreign_key="applications.id", index=True)
    arrival_date: date | None = None
    departure_date: date | None = None
    destination_countries_json: str = "[]"
    itinerary_json: str = "[]"


class AccommodationRow(SQLModel, table=True):
    __tablename__ = "accommodations"

    id: str = Field(primary_key=True)
    application_id: str = Field(foreign_key="applications.id", index=True)
    provider_name: str | None = None
    city: str | None = None
    country: str | None = None
    check_in: date | None = None
    check_out: date | None = None
    confirmation_number: str | None = None
    invitation_or_hotel: str | None = None


class InsuranceRow(SQLModel, table=True):
    __tablename__ = "insurance_policies"

    id: str = Field(primary_key=True)
    application_id: str = Field(foreign_key="applications.id", index=True)
    insurer: str | None = None
    policy_number: str | None = None
    coverage_amount: float | None = None
    coverage_currency: str | None = None
    territory: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    covered_items_json: str = "[]"


class FinancialRecordRow(SQLModel, table=True):
    __tablename__ = "financial_records"

    id: str = Field(primary_key=True)
    application_id: str = Field(foreign_key="applications.id", index=True)
    bank_name: str | None = None
    account_currency: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    issue_date: date | None = None
    opening_balance: float | None = None
    closing_balance: float | None = None
    has_bank_stamp: bool | None = None
    transactions_json: str = "[]"
    source_document_id: str | None = None


class EmploymentRecordRow(SQLModel, table=True):
    __tablename__ = "employment_records"

    id: str = Field(primary_key=True)
    application_id: str = Field(foreign_key="applications.id", index=True)
    employer_name: str | None = None
    position: str | None = None
    hire_date: date | None = None
    monthly_salary: float | None = None
    salary_currency: str | None = None
    leave_start: date | None = None
    leave_end: date | None = None
    letter_date: date | None = None
    signed_and_stamped: bool | None = None


class PayslipRow(SQLModel, table=True):
    __tablename__ = "payslips"

    id: str = Field(primary_key=True)
    application_id: str = Field(foreign_key="applications.id", index=True)
    period_month: str | None = None
    net_pay: float | None = None
    currency: str | None = None
    employer_name: str | None = None
    source_document_id: str | None = None


class CivilStatusRow(SQLModel, table=True):
    __tablename__ = "civil_status_records"

    id: str = Field(primary_key=True)
    application_id: str = Field(foreign_key="applications.id", index=True)
    record_type: str = "family_register"
    issue_date: date | None = None
    translated: bool | None = None
    members_json: str = "[]"
    source_document_id: str | None = None


def _engine(settings: Settings):
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


def init_db(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if settings.database_url.startswith("sqlite:///"):
        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(_engine(settings))


def register_application(meta: dict[str, Any], settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    init_db(settings)
    row = ApplicationRow(
        id=meta["id"],
        checklist_id=meta["checklist_id"],
        submission_date=date.fromisoformat(meta["submission_date"]),
        status=meta.get("status", "created"),
    )
    with Session(_engine(settings)) as session:
        session.merge(row)
        session.commit()


def register_document(
    *,
    application_id: str,
    filename: str,
    path: Path,
    data: bytes,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    init_db(settings)
    row = DocumentRow(
        id=hashlib.sha256(f"{application_id}:{path.name}".encode("utf-8")).hexdigest()[:32],
        application_id=application_id,
        original_filename=filename,
        stored_path=str(path.relative_to(settings.data_dir)),
        sha256=hashlib.sha256(data).hexdigest(),
        byte_size=len(data),
    )
    with Session(_engine(settings)) as session:
        session.merge(row)
        session.commit()


def list_documents(application_id: str, settings: Settings | None = None) -> list[DocumentRow]:
    settings = settings or get_settings()
    init_db(settings)
    with Session(_engine(settings)) as session:
        return list(
            session.exec(
                select(DocumentRow).where(DocumentRow.application_id == application_id)
            ).all()
        )


def redact_application_sensitive_data(
    application_id: str,
    settings: Settings | None = None,
) -> int:
    """Remove personal/detail rows while retaining the application decision row."""
    settings = settings or get_settings()
    init_db(settings)
    detail_models = (
        DocumentRow,
        TravelPlanRow,
        AccommodationRow,
        InsuranceRow,
        FinancialRecordRow,
        EmploymentRecordRow,
        PayslipRow,
        CivilStatusRow,
    )
    deleted = 0
    with Session(_engine(settings)) as session:
        application = session.get(ApplicationRow, application_id)
        if application is None:
            raise FileNotFoundError(application_id)
        for model in detail_models:
            rows = list(
                session.exec(
                    select(model).where(model.application_id == application_id)
                ).all()
            )
            for row in rows:
                session.delete(row)
                deleted += 1
        for field in (
            "first_name",
            "last_name",
            "date_of_birth",
            "place_of_birth",
            "nationality",
            "passport_number",
            "passport_issue_date",
            "passport_expiry_date",
        ):
            setattr(application, field, None)
        session.add(application)
        session.commit()
    return deleted
