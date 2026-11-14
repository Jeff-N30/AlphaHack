#!/usr/bin/env python3
"""Seed case06+ from case01_complete with Lebanon / France edge scenarios.

Does NOT regenerate docs/ images — only case.yaml + expected.yaml.
Run: python tools/seed_eval_cases.py
Then: python tools/generate_fake_docs.py  (for cases that need docs)
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "eval" / "cases"
BASE = CASES / "case01_complete"

PASS_RULES = {
    "DOC.PRESENT": "PASS",
    "PP.MRZ_CHECKSUM": "PASS",
    "PP.MRZ_MATCHES_VIZ": "PASS",
    "PP.NOT_EXPIRED": "PASS",
    "PP.ISSUED_WITHIN_10Y": "PASS",
    "PP.VALID_AFTER_DEPARTURE": "PASS",
    "ID.NAME_MATCH": "PASS",
    "ID.FORM_MATCHES_PASSPORT": "PASS",
    "ID.DOB_MATCH": "PASS",
    "ID.PASSPORT_NO_MATCH": "PASS",
    "TRIP.ROUND_TRIP": "PASS",
    "TRIP.MAX_90_DAYS": "PASS",
    "TRIP.FILING_WINDOW": "PASS",
    "TRIP.HOTEL_COVERS_STAY": "PASS",
    "TRIP.HOTEL_IN_DESTINATION": "PASS",
    "INS.MIN_COVERAGE": "PASS",
    "INS.TERRITORY": "PASS",
    "INS.COVERS_STAY": "PASS",
    "INS.MEDICAL_REPATRIATION": "PASS",
    "BANK.WINDOW": "PASS",
    "BANK.STAMPED": "PASS",
    "BANK.SUFFICIENT_FUNDS": "PASS",
    "BANK.LARGE_RECENT_DEPOSIT": "PASS",
    "EMP.LETTER_FIELDS": "PASS",
    "EMP.LEAVE_COVERS_TRIP": "PASS",
    "EMP.PAYSLIPS_RECENT": "PASS",
    "FAM.ISSUED_WITHIN_6M": "PASS",
    "SUS.DOC_ANOMALY": "PASS",
    "SUS.LOW_CONFIDENCE": "PASS",
}


def load_base() -> dict:
    return yaml.safe_load((BASE / "case.yaml").read_text(encoding="utf-8"))


def write_case(case_id: str, title: str, mutate, expected: dict) -> None:
    data = load_base()
    data["case_id"] = case_id
    data["title"] = title
    mutate(data)
    out = CASES / case_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "case.yaml").write_text(
        "# FAKE APPLICANT. Invented for AlphaHack 2026 / Lebanon→France edge cases.\n"
        + yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    rules = copy.deepcopy(PASS_RULES)
    rules.update(expected.get("rules_overrides", {}))
    exp = {
        "case_id": case_id,
        "outcome": expected["outcome"],
        "escalations": expected.get("escalations", 0),
        "critical_rules": expected["critical_rules"],
        "rules": rules,
        "manual_rules_ignored": ["PP.BLANK_PAGES", "PHOTO.ISO"],
        "draft_message": expected.get(
            "draft_message",
            {
                "required": expected["outcome"] == "SEND_BACK",
                "must_mention": expected.get("must_mention", []),
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
        ),
        "notes": expected.get("notes", ""),
        "tags": expected.get("tags", []),
    }
    (out / "expected.yaml").write_text(
        yaml.safe_dump(exp, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"wrote {case_id}")


def main() -> None:
    # --- already in eval/README 06-20 ---
    write_case(
        "case06_insurance_low_coverage",
        "Insurance coverage EUR 25,000 (< 30,000)",
        lambda d: d["documents"]["travel_insurance"]["coverage"].update(
            {"amount": 25000, "currency": "EUR"}
        ),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["INS.MIN_COVERAGE"],
            "rules_overrides": {"INS.MIN_COVERAGE": "FAIL"},
            "must_mention": ["insurance", "30,000"],
            "tags": ["insurance", "france"],
        },
    )
    write_case(
        "case07_insurance_france_only",
        "Insurance territory France only (OTHER)",
        lambda d: (
            d["documents"]["travel_insurance"].update(
                {"territory": "OTHER", "territory_raw": "France only"}
            )
        ),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["INS.TERRITORY"],
            "rules_overrides": {"INS.TERRITORY": "FAIL"},
            "must_mention": ["insurance", "Schengen"],
            "tags": ["insurance", "france"],
        },
    )
    write_case(
        "case08_insurance_ends_early",
        "Insurance ends one day before return",
        lambda d: d["documents"]["travel_insurance"].update({"end_date": "2026-12-27"}),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["INS.COVERS_STAY"],
            "rules_overrides": {"INS.COVERS_STAY": "FAIL"},
            "must_mention": ["insurance", "28/12/2026"],
            "tags": ["insurance", "dates"],
        },
    )
    write_case(
        "case09_bank_only_3_months",
        "Bank statement covers only 3 months",
        lambda d: d["documents"]["bank_statement"].update({"period_start": "2026-08-01"}),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["BANK.WINDOW"],
            "rules_overrides": {"BANK.WINDOW": "FAIL"},
            "must_mention": ["bank", "6"],
            "tags": ["bank"],
        },
    )
    write_case(
        "case10_bank_too_old",
        "Bank statement issued 45 days before submission",
        lambda d: d["documents"]["bank_statement"].update({"issue_date": "2026-10-01"}),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["BANK.WINDOW"],
            "rules_overrides": {"BANK.WINDOW": "FAIL"},
            "must_mention": ["bank"],
            "tags": ["bank"],
        },
    )
    write_case(
        "case11_insufficient_funds",
        "USD 500 closing for ~11-day stay — not enough",
        lambda d: d["documents"]["bank_statement"].update({"closing_balance": 500.0}),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["BANK.SUFFICIENT_FUNDS"],
            "rules_overrides": {"BANK.SUFFICIENT_FUNDS": "FAIL"},
            "must_mention": ["funds", "bank"],
            "tags": ["bank", "funds"],
        },
    )
    write_case(
        "case12_large_recent_deposit",
        "Large USD deposit 10 days before statement end",
        lambda d: d["documents"]["bank_statement"]["transactions"].append(
            {
                "date": "2026-10-25",
                "description": "CASH DEPOSIT (FAKE)",
                "amount": 9000.0,
            }
        ),
        {
            "outcome": "NEEDS_GLORIA",
            "escalations": 1,
            "critical_rules": ["BANK.LARGE_RECENT_DEPOSIT"],
            "rules_overrides": {"BANK.LARGE_RECENT_DEPOSIT": "NEEDS_HUMAN"},
            "draft_message": {
                "required": False,
                "must_mention": [],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
            "tags": ["bank", "lebanon"],
            "notes": "Suspicious recent large deposit → Gloria",
        },
    )
    write_case(
        "case13_passport_older_than_10y",
        "Passport issued more than 10 years before submission",
        lambda d: d["documents"]["passport"].update({"issue_date": "2015-01-10"}),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["PP.ISSUED_WITHIN_10Y"],
            "rules_overrides": {"PP.ISSUED_WITHIN_10Y": "FAIL"},
            "must_mention": ["passport"],
            "tags": ["passport"],
        },
    )
    write_case(
        "case14_passport_expired",
        "Passport already expired at submission",
        lambda d: d["documents"]["passport"].update({"expiry_date": "2026-10-01"}),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["PP.NOT_EXPIRED"],
            "rules_overrides": {
                "PP.NOT_EXPIRED": "FAIL",
                "PP.VALID_AFTER_DEPARTURE": "FAIL",
                "ID.FORM_MATCHES_PASSPORT": "FAIL",
            },
            "must_mention": ["passport", "expir"],
            "tags": ["passport"],
        },
    )
    write_case(
        "case15_mrz_tamper",
        "One MRZ digit altered (checksum must fail)",
        lambda d: d["documents"]["passport"].update(
            {"passport_number": "LR0482919", "mrz_tampered": True}
        ),
        {
            "outcome": "NEEDS_GLORIA",
            "escalations": 1,
            "critical_rules": ["PP.MRZ_CHECKSUM"],
            "rules_overrides": {"PP.MRZ_CHECKSUM": "NEEDS_HUMAN"},
            "draft_message": {
                "required": False,
                "must_mention": [],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
            "tags": ["passport", "mrz", "security"],
            "notes": "Generator should break MRZ check digit when mrz_tampered set.",
        },
    )
    write_case(
        "case16_one_way_flight",
        "One-way flight only",
        lambda d: d["documents"]["flight_booking"].update(
            {
                "segments": [
                    {
                        "from_airport": "BEY",
                        "to_airport": "CDG",
                        "to_country": "FR",
                        "departure_date": "2026-12-18",
                        "flight_number": "AF565",
                    }
                ]
            }
        ),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["TRIP.ROUND_TRIP"],
            "rules_overrides": {"TRIP.ROUND_TRIP": "FAIL"},
            "must_mention": ["flight", "return"],
            "tags": ["trip"],
        },
    )
    write_case(
        "case17_filing_too_late",
        "Departure only 10 days after submission",
        lambda d: (
            d["documents"]["flight_booking"]["segments"][0].update(
                {"departure_date": "2026-11-26"}
            ),
            d["documents"]["flight_booking"]["segments"][1].update(
                {"departure_date": "2026-12-06"}
            ),
            d["documents"]["hotel_booking"].update(
                {"check_in": "2026-11-26", "check_out": "2026-12-06"}
            ),
            d["documents"]["travel_insurance"].update(
                {"start_date": "2026-11-26", "end_date": "2026-12-06"}
            ),
            d["documents"]["application_form"].update(
                {
                    "intended_arrival": "2026-11-26",
                    "intended_departure": "2026-12-06",
                }
            ),
        ),
        {
            "outcome": "NEEDS_GLORIA",
            "escalations": 1,
            "critical_rules": ["TRIP.FILING_WINDOW"],
            "rules_overrides": {"TRIP.FILING_WINDOW": "NEEDS_HUMAN"},
            "draft_message": {
                "required": False,
                "must_mention": [],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
            "tags": ["trip", "tls"],
        },
    )
    write_case(
        "case18_form_passport_typo",
        "Application form passport number typo",
        lambda d: d["documents"]["application_form"].update(
            {"passport_number": "LR0482918"}
        ),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["ID.FORM_MATCHES_PASSPORT"],
            "rules_overrides": {"ID.FORM_MATCHES_PASSPORT": "FAIL"},
            "must_mention": ["passport", "form"],
            "tags": ["identity"],
        },
    )
    write_case(
        "case19_phone_photo_name_order",
        "Phone-photo style + hotel name order NASSAR KARIM (still PASS)",
        lambda d: (
            d["documents"]["hotel_booking"].update({"guest_names": ["NASSAR KARIM"]}),
            d.update({"degrade_docs": True}),
        ),
        {
            "outcome": "READY_FOR_APPROVAL",
            "critical_rules": ["ID.NAME_MATCH", "DOC.PRESENT"],
            "tags": ["robustness", "ocr"],
            "draft_message": {
                "required": False,
                "must_mention": [],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
        },
    )
    write_case(
        "case20_leave_ends_early",
        "Employer leave ends before return flight",
        lambda d: d["documents"]["employment_letter"].update({"leave_end": "2026-12-25"}),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["EMP.LEAVE_COVERS_TRIP"],
            "rules_overrides": {"EMP.LEAVE_COVERS_TRIP": "FAIL"},
            "must_mention": ["leave", "employer"],
            "tags": ["employment"],
        },
    )

    # --- Lebanon / Arabic / ekhraj / bilingual edge cases ---
    write_case(
        "case21_ekhraj_too_old",
        "Ekhraj kaid aily older than 6 months",
        lambda d: d["documents"]["family_register"].update({"issue_date": "2026-01-01"}),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["FAM.ISSUED_WITHIN_6M"],
            "rules_overrides": {"FAM.ISSUED_WITHIN_6M": "FAIL"},
            "must_mention": ["family", "ekhraj", "6"],
            "tags": ["lebanon", "ekhraj", "civil"],
            "notes": "Family register extract must be ≤ 6 months (EU list / local practice).",
        },
    )
    write_case(
        "case22_ekhraj_missing",
        "Missing ekhraj kaid aily entirely",
        lambda d: d["documents"].pop("family_register", None),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["DOC.PRESENT"],
            "rules_overrides": {
                "DOC.PRESENT": "FAIL",
                "FAM.ISSUED_WITHIN_6M": "SKIPPED",
            },
            "must_mention": ["family", "register"],
            "tags": ["lebanon", "ekhraj", "missing"],
        },
    )
    write_case(
        "case23_ekhraj_no_translation",
        "Ekhraj Arabic-only, no translation flag",
        lambda d: d["documents"]["family_register"].update(
            {
                "translated": False,
                "language": "ar",
                "summary": "إخراج قيد عائلي (FAKE) — no certified translation attached",
            }
        ),
        {
            "outcome": "NEEDS_GLORIA",
            "escalations": 1,
            "critical_rules": ["SUS.LOW_CONFIDENCE"],
            "rules_overrides": {"SUS.LOW_CONFIDENCE": "NEEDS_HUMAN"},
            "draft_message": {
                "required": True,
                "must_mention": ["translation", "family", "register"],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
            "tags": ["lebanon", "arabic", "ekhraj", "translation"],
            "notes": "Gloria confirms whether certified FR/EN translation is present.",
        },
    )
    write_case(
        "case24_arabic_only_employment_letter",
        "Employer letter Arabic-only body",
        lambda d: d["documents"]["employment_letter"].update(
            {
                "language": "ar",
                "employee_name": "كريم نصار",
                "employer_name": "شركة العينة ش.م.ل (وهمية)",
                "needs_translation": True,
            }
        ),
        {
            "outcome": "NEEDS_GLORIA",
            "escalations": 1,
            "critical_rules": ["SUS.LOW_CONFIDENCE", "ID.NAME_MATCH"],
            "rules_overrides": {
                "SUS.LOW_CONFIDENCE": "NEEDS_HUMAN",
                "ID.NAME_MATCH": "NEEDS_HUMAN",
            },
            "draft_message": {
                "required": True,
                "must_mention": ["translation", "employer"],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
            "tags": ["lebanon", "arabic", "employment"],
        },
    )
    write_case(
        "case25_lbp_bank_currency",
        "Bank statement in LBP — never guess FX",
        lambda d: d["documents"]["bank_statement"].update(
            {
                "account_currency": "LBP",
                "opening_balance": 100_000_000.0,
                "closing_balance": 120_000_000.0,
            }
        ),
        {
            "outcome": "NEEDS_GLORIA",
            "escalations": 1,
            "critical_rules": ["BANK.SUFFICIENT_FUNDS"],
            "rules_overrides": {"BANK.SUFFICIENT_FUNDS": "NEEDS_HUMAN"},
            "draft_message": {
                "required": True,
                "must_mention": ["USD", "EUR", "bank"],
                "must_not_mention": ["refused", "rejected"],
            },
            "tags": ["lebanon", "bank", "lbp", "fx"],
            "notes": "No LBP logic in rules — unknown/LBP → NEEDS_HUMAN.",
        },
    )
    write_case(
        "case26_scanned_pdf_image_only",
        "Bank PDF is image-only scan (no text layer)",
        lambda d: d["documents"]["bank_statement"].update(
            {"scan_only": True, "text_layer": False}
        ),
        {
            "outcome": "READY_FOR_APPROVAL",
            "critical_rules": ["BANK.SUFFICIENT_FUNDS"],
            "tags": ["ocr", "scanned_pdf", "robustness"],
            "notes": "Pipeline must render→OCR. If OCR fails in full eval → escalate; rules-only uses case.yaml facts.",
            "draft_message": {
                "required": False,
                "must_mention": [],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
        },
    )
    write_case(
        "case27_wrong_filename_passport",
        "Passport bytes named hotel_booking.pdf (content classify must win)",
        lambda d: d["documents"]["passport"].update(
            {"file": "hotel_booking.pdf", "actual_type": "passport", "misleading_filename": True}
        ),
        {
            "outcome": "READY_FOR_APPROVAL",
            "critical_rules": ["PP.MRZ_CHECKSUM", "DOC.PRESENT"],
            "tags": ["classify", "filename", "agent"],
            "notes": "Agent must classify from content, not filename.",
            "draft_message": {
                "required": False,
                "must_mention": [],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
        },
    )
    write_case(
        "case28_bilingual_fr_ar_hotel",
        "Hotel confirmation mixed French + Arabic",
        lambda d: d["documents"]["hotel_booking"].update(
            {
                "language": "mixed",
                "hotel_name": "Hôtel Étoile / فندق النجمة (FAKE)",
                "city": "Paris",
            }
        ),
        {
            "outcome": "READY_FOR_APPROVAL",
            "critical_rules": ["TRIP.HOTEL_COVERS_STAY"],
            "tags": ["arabic", "french", "bilingual"],
            "draft_message": {
                "required": False,
                "must_mention": [],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
        },
    )
    write_case(
        "case29_missing_cnss",
        "Employee profile missing CNSS certificate",
        lambda d: d["documents"].pop("cnss_certificate", None),
        {
            "outcome": "SEND_BACK",
            "critical_rules": ["DOC.PRESENT"],
            "rules_overrides": {"DOC.PRESENT": "FAIL"},
            "must_mention": ["CNSS", "social"],
            "tags": ["lebanon", "employment", "cnss"],
        },
    )
    def _arabic_payslips(d: dict) -> None:
        labels = ["آب 2026", "أيلول 2026", "تشرين الأول 2026"]
        for slip, label in zip(d["documents"]["payslip"], labels, strict=True):
            slip["language"] = "ar"
            slip["period_label_ar"] = label

    write_case(
        "case30_arabic_payslip_months",
        "Payslips with Arabic month labels (still parseable via case facts)",
        _arabic_payslips,
        {
            "outcome": "READY_FOR_APPROVAL",
            "critical_rules": ["EMP.PAYSLIPS_RECENT"],
            "tags": ["arabic", "payslip", "lebanon"],
            "draft_message": {
                "required": False,
                "must_mention": [],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
            "notes": "Full pipeline may NEEDS_HUMAN if OCR of Arabic months fails.",
        },
    )
    write_case(
        "case31_unknown_doc_type",
        "Extra unrelated PDF (utility bill) — classify unknown",
        lambda d: d["documents"].update(
            {
                "unknown_extra": {
                    "file": "electricity_bill.pdf",
                    "doc_type": "unknown",
                    "summary": "EDL electricity bill SPECIMEN — not a visa supporting doc",
                }
            }
        ),
        {
            "outcome": "NEEDS_GLORIA",
            "escalations": 1,
            "critical_rules": ["SUS.DOC_ANOMALY"],
            "rules_overrides": {"SUS.DOC_ANOMALY": "NEEDS_HUMAN"},
            "draft_message": {
                "required": False,
                "must_mention": [],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
            "tags": ["classify", "unknown", "agent"],
            "notes": "Extra unknown attachment should not crash; flag for Gloria.",
        },
    )
    write_case(
        "case32_al_el_name_particles",
        "MRZ AL-HAJJ vs docs El Hajj spacing variants — should PASS normalize",
        lambda d: (
            d["applicant"].update(
                {"surname": "AL HAJJ", "given_names": "KARIM", "surname_ar": "الحاج"}
            ),
            d["documents"]["passport"].update(
                {"surname": "AL HAJJ", "given_names": "KARIM", "surname_ar": "الحاج"}
            ),
            d["documents"]["bank_statement"].update({"account_holder": "KARIM EL-HAJJ"}),
            d["documents"]["hotel_booking"].update({"guest_names": ["KARIM ALHAJJ"]}),
            d["documents"]["employment_letter"].update({"employee_name": "KARIM AL HAJJ"}),
            d["documents"]["flight_booking"].update({"passenger_names": ["AL HAJJ/KARIM"]}),
            d["documents"]["travel_insurance"].update({"insured_name": "KARIM AL-HAJJ"}),
            d["documents"]["application_form"].update(
                {"surname": "AL HAJJ", "given_names": "KARIM"}
            ),
        ),
        {
            "outcome": "READY_FOR_APPROVAL",
            "critical_rules": ["ID.NAME_MATCH"],
            "tags": ["lebanon", "names", "al-el"],
            "draft_message": {
                "required": False,
                "must_mention": [],
                "must_not_mention": ["refused", "rejected", "LBP"],
            },
            "notes": "Normalizer must treat AL/EL/AL- as same particle.",
        },
    )
    print("done — seeded case06..case32")


if __name__ == "__main__":
    main()
