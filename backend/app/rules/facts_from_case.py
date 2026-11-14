"""Build Facts from eval/cases/*/case.yaml (no LLM)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from app.extract.mrz import parse_td3
from app.models import (
    ApplicationFormExtraction,
    BankStatementExtraction,
    Conf,
    DocType,
    EmploymentLetterExtraction,
    FamilyRegisterExtraction,
    FlightBookingExtraction,
    FlightSegment,
    GenericExtraction,
    HotelBookingExtraction,
    Money,
    PassportExtraction,
    PayslipExtraction,
    Transaction,
    TravelInsuranceExtraction,
)
from app.rules.context import Facts


def _d(v: Any) -> date:
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _money(v: Any) -> Money:
    if isinstance(v, Money):
        return v
    return Money(amount=float(v["amount"]), currency=str(v["currency"]).upper())


def _conf(fields: list[str], page: int = 1, confidence: float = 0.95) -> dict[str, Conf]:
    return {f: Conf(page=page, confidence=confidence) for f in fields}


def facts_from_case(case_dir: Path | str) -> Facts:
    case_dir = Path(case_dir)
    raw = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
    docs_raw = raw.get("documents") or {}
    documents: dict[DocType, list] = {}

    # Passport + MRZ
    if "passport" in docs_raw:
        p = docs_raw["passport"]
        mrz_path = case_dir / "docs" / "passport_mrz.txt"
        mrz = None
        if mrz_path.exists() and not p.get("mrz_tampered"):
            lines = mrz_path.read_text(encoding="utf-8").strip().splitlines()
            mrz = parse_td3(lines, today=_d(raw.get("submission_date", "2026-11-16")))
        elif p.get("mrz_tampered") and mrz_path.exists():
            lines = mrz_path.read_text(encoding="utf-8").strip().splitlines()
            # Flip one check digit so ICAO fails (rules-only path; image may differ)
            if len(lines) >= 2 and lines[1]:
                chars = list(lines[1])
                chars[-1] = "0" if chars[-1] != "0" else "1"
                lines[1] = "".join(chars)
            mrz = parse_td3(lines, today=_d(raw.get("submission_date", "2026-11-16")))
        pe = PassportExtraction(
            surname=p["surname"],
            given_names=p["given_names"],
            surname_ar=p.get("surname_ar"),
            given_names_ar=p.get("given_names_ar"),
            passport_number=p["passport_number"],
            nationality=p.get("nationality", "LBN"),
            date_of_birth=_d(p["date_of_birth"]),
            sex=p["sex"],
            issue_date=_d(p["issue_date"]),
            expiry_date=_d(p["expiry_date"]),
            place_of_issue=p.get("place_of_issue"),
            mrz_lines=[],
            mrz=mrz,
            field_meta=_conf(
                ["surname", "given_names", "passport_number", "date_of_birth", "expiry_date", "issue_date"]
            ),
        )
        documents[DocType.passport] = [pe]

    if "application_form" in docs_raw:
        f = docs_raw["application_form"]
        documents[DocType.application_form] = [
            ApplicationFormExtraction(
                surname=f["surname"],
                given_names=f["given_names"],
                date_of_birth=_d(f["date_of_birth"]),
                passport_number=f["passport_number"],
                expiry_date=_d(f["expiry_date"]),
                france_visas_reference=f.get("france_visas_reference"),
                intended_arrival=_d(f["intended_arrival"]) if f.get("intended_arrival") else None,
                intended_departure=_d(f["intended_departure"]) if f.get("intended_departure") else None,
                signed=f.get("signed"),
                field_meta=_conf(["surname", "given_names", "passport_number", "date_of_birth", "expiry_date"]),
            )
        ]

    if "photo" in docs_raw:
        ph = docs_raw["photo"]
        n = int(ph.get("count") or 1)
        documents[DocType.photo] = [
            GenericExtraction(doc_type=DocType.photo, names_found=[], summary=f"photo_{i}")
            for i in range(max(n, 1))
        ]

    if "flight_booking" in docs_raw:
        fl = docs_raw["flight_booking"]
        segs = [
            FlightSegment(
                from_airport=s["from_airport"],
                to_airport=s["to_airport"],
                to_country=s.get("to_country"),
                departure_date=_d(s["departure_date"]),
                flight_number=s.get("flight_number"),
            )
            for s in fl.get("segments") or []
        ]
        documents[DocType.flight_booking] = [
            FlightBookingExtraction(
                passenger_names=list(fl.get("passenger_names") or []),
                booking_reference=fl.get("booking_reference"),
                passport_number=fl.get("passport_number"),
                segments=segs,
                field_meta=_conf(["passenger_names", "segments"]),
            )
        ]

    if "hotel_booking" in docs_raw:
        h = docs_raw["hotel_booking"]
        documents[DocType.hotel_booking] = [
            HotelBookingExtraction(
                guest_names=list(h.get("guest_names") or []),
                hotel_name=h["hotel_name"],
                city=h.get("city", ""),
                country=h["country"],
                check_in=_d(h["check_in"]),
                check_out=_d(h["check_out"]),
                confirmation_number=h.get("confirmation_number"),
                prepaid_or_free_cancellation=h.get("prepaid_or_free_cancellation"),
                field_meta=_conf(["guest_names", "check_in", "check_out", "country"]),
            )
        ]

    if "travel_insurance" in docs_raw:
        ti = docs_raw["travel_insurance"]
        documents[DocType.travel_insurance] = [
            TravelInsuranceExtraction(
                insured_name=ti["insured_name"],
                date_of_birth=_d(ti["date_of_birth"]) if ti.get("date_of_birth") else None,
                passport_number=ti.get("passport_number"),
                insurer=ti["insurer"],
                policy_number=ti["policy_number"],
                coverage=_money(ti["coverage"]),
                territory=ti["territory"],
                territory_raw=ti.get("territory_raw", ti["territory"]),
                start_date=_d(ti["start_date"]),
                end_date=_d(ti["end_date"]),
                covers=list(ti.get("covers") or []),
                field_meta=_conf(["insured_name", "coverage", "territory", "start_date", "end_date"]),
            )
        ]

    if "bank_statement" in docs_raw:
        b = docs_raw["bank_statement"]
        txs = [
            Transaction(date=_d(t["date"]), description=t["description"], amount=float(t["amount"]))
            for t in b.get("transactions") or []
        ]
        documents[DocType.bank_statement] = [
            BankStatementExtraction(
                account_holder=b["account_holder"],
                bank_name=b["bank_name"],
                account_currency=str(b["account_currency"]).upper(),
                account_type_raw=b.get("account_type_raw"),
                period_start=_d(b["period_start"]),
                period_end=_d(b["period_end"]),
                issue_date=_d(b["issue_date"]),
                opening_balance=float(b["opening_balance"]),
                closing_balance=float(b["closing_balance"]),
                has_bank_stamp=bool(b.get("has_bank_stamp", False)),
                transactions=txs,
                field_meta=_conf(["account_holder", "closing_balance", "period_start", "period_end"]),
            )
        ]

    if "employment_letter" in docs_raw:
        e = docs_raw["employment_letter"]
        emp_conf = 0.4 if e.get("arabic_only") or e.get("language") == "ar" else 0.95
        documents[DocType.employment_letter] = [
            EmploymentLetterExtraction(
                employee_name=e["employee_name"],
                employer_name=e["employer_name"],
                position=e.get("position"),
                hire_date=_d(e["hire_date"]) if e.get("hire_date") else None,
                monthly_salary=_money(e["monthly_salary"]) if e.get("monthly_salary") else None,
                leave_start=_d(e["leave_start"]) if e.get("leave_start") else None,
                leave_end=_d(e["leave_end"]) if e.get("leave_end") else None,
                letter_date=_d(e["letter_date"]) if e.get("letter_date") else None,
                signed_and_stamped=e.get("signed_and_stamped"),
                language=e.get("language"),
                field_meta=_conf(
                    ["employee_name", "employer_name", "hire_date", "monthly_salary", "leave_start", "leave_end"],
                    confidence=emp_conf,
                ),
            )
        ]

    if "payslip" in docs_raw:
        slips = docs_raw["payslip"]
        if not isinstance(slips, list):
            slips = [slips]
        documents[DocType.payslip] = [
            PayslipExtraction(
                employee_name=s["employee_name"],
                employer_name=s["employer_name"],
                period_month=s["period_month"],
                net_pay=_money(s["net_pay"]),
                field_meta=_conf(["employee_name", "period_month", "net_pay"]),
            )
            for s in slips
        ]

    if "cnss_certificate" in docs_raw:
        c = docs_raw["cnss_certificate"]
        documents[DocType.cnss_certificate] = [
            GenericExtraction(
                doc_type=DocType.cnss_certificate,
                names_found=list(c.get("names_found") or []),
                summary="cnss",
            )
        ]

    if "family_register" in docs_raw:
        fr = docs_raw["family_register"]
        fam_conf = 0.95 if fr.get("translated", True) else 0.35
        documents[DocType.family_register] = [
            FamilyRegisterExtraction(
                head_of_family=fr.get("head_of_family"),
                members=list(fr.get("members") or []),
                issue_date=_d(fr["issue_date"]),
                translated=fr.get("translated"),
                field_meta=_conf(["issue_date", "members"], confidence=fam_conf),
            )
        ]

    if "travel_plan" in docs_raw:
        tp = docs_raw["travel_plan"]
        documents[DocType.travel_plan] = [
            GenericExtraction(
                doc_type=DocType.travel_plan,
                names_found=[],
                summary=tp.get("summary"),
            )
        ]

    # Optional junk / unknown extras (e.g. utility bill)
    for key in ("unknown", "extra", "unknown_extra"):
        if key not in docs_raw:
            continue
        extra = docs_raw[key]
        items = extra if isinstance(extra, list) else [extra]
        documents.setdefault(DocType.unknown, []).extend(
            [
                GenericExtraction(
                    doc_type=DocType.unknown,
                    names_found=[],
                    summary=str(item.get("summary") or item.get("file") or "unknown"),
                    anomaly_flags=["unknown_doc_type"],
                )
                for item in items
            ]
        )

    sub = raw.get("submission_date", "2026-11-16")
    return Facts(
        documents=documents,
        submission_date=_d(sub),
        profile=raw.get("profile", "employee"),
        application_id=raw.get("case_id", case_dir.name),
    )
