"""Boundary unit tests for key checklist checks."""
from __future__ import annotations

from datetime import date

from app.models import (
    BankStatementExtraction,
    DocType,
    FlightBookingExtraction,
    FlightSegment,
    HotelBookingExtraction,
    Money,
    PassportExtraction,
    Status,
    TravelInsuranceExtraction,
)
from app.rules.context import Facts, RuleContext
from app.rules.checks.funds import statement_window, sufficient_funds
from app.rules.checks.insurance import insurance_min_coverage
from app.rules.checks.passport import passport_valid_after_departure
from app.rules.checks.trip import stay_length_max
from app.rules.dates import add_months, inclusive_days
from app.rules.names import compare_names


def _ctx(sub: date = date(2026, 11, 16)) -> RuleContext:
    return RuleContext(
        submission_date=sub,
        checklist_id="fr",
        checklist_version="0",
        fx_rates_to_eur={"EUR": 1.0, "USD": 0.86},
    )


def test_exactly_3_months_after_return() -> None:
    assert add_months(date(2027, 1, 5), 3) == date(2027, 4, 5)


def test_exactly_90_days_stay() -> None:
    assert inclusive_days(date(2026, 1, 1), date(2026, 3, 31)) == 90
    facts = Facts(
        documents={
            DocType.flight_booking: [
                FlightBookingExtraction(
                    passenger_names=["A"],
                    segments=[
                        FlightSegment(
                            from_airport="BEY",
                            to_airport="CDG",
                            departure_date=date(2026, 1, 1),
                        ),
                        FlightSegment(
                            from_airport="CDG",
                            to_airport="BEY",
                            departure_date=date(2026, 3, 31),
                        ),
                    ],
                )
            ]
        },
        submission_date=date(2025, 12, 1),
    )
    r = stay_length_max(facts, {"max_days": 90}, _ctx(date(2025, 12, 1)))
    assert r.status == Status.PASS


def test_insurance_exactly_30000() -> None:
    facts = Facts(
        documents={
            DocType.travel_insurance: [
                TravelInsuranceExtraction(
                    insured_name="A",
                    insurer="X",
                    policy_number="1",
                    coverage=Money(amount=30000, currency="EUR"),
                    territory="SCHENGEN",
                    territory_raw="Schengen",
                    start_date=date(2026, 12, 1),
                    end_date=date(2026, 12, 10),
                    covers=["emergency_medical", "hospitalisation", "repatriation"],
                )
            ]
        }
    )
    r = insurance_min_coverage(facts, {"min_amount": 30000, "currency": "EUR"}, _ctx())
    assert r.status == Status.PASS


def test_name_thresholds_85_70() -> None:
    st, score, _ = compare_names("MOHAMAD AL HAJJ", "MOHAMMAD AL HAJJ")
    assert st == Status.NEEDS_HUMAN
    assert score >= 85
    st2, score2, _ = compare_names("KARIM", "KARIM NASSAR")
    assert st2 != Status.PASS
    st3, score3, _ = compare_names("GEORGES HADDAD", "RANA SALEH")
    assert st3 == Status.FAIL
    assert score3 < 70


def test_name_match_refuses_invalid_mrz() -> None:
    """Failed MRZ checksums must not drive a FAIL against pack names (no OCR junk)."""
    from app.models import MRZ
    from app.rules.checks.identity import name_consistency

    mrz = MRZ(
        line1="P<LBNBAR<<JOE<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<",
        line2="LR41164833LBN0208144M35061561002339074<<<<12",
        surname="BAR",
        given_names="JOE SSS SKKKK",
        passport_number="LR4116483",
        nationality="LBN",
        date_of_birth=date(2002, 8, 14),
        sex="M",
        expiry_date=date(2035, 6, 15),
        checksums_valid=False,
        failed_checks=["final hash"],
    )
    facts = Facts(
        documents={
            DocType.passport: [
                PassportExtraction(
                    surname="BAR",
                    given_names="JOE SSS SKKKK",
                    nationality="LBN",
                    passport_number="LR4116483",
                    date_of_birth=date(2002, 8, 14),
                    sex="M",
                    issue_date=date(2015, 6, 15),
                    expiry_date=date(2035, 6, 15),
                    mrz=mrz,
                )
            ],
            DocType.flight_booking: [
                FlightBookingExtraction(
                    passenger_names=["Jeff Nader"],
                    segments=[
                        FlightSegment(
                            from_airport="BEY",
                            to_airport="CDG",
                            departure_date=date(2026, 12, 1),
                        ),
                    ],
                )
            ],
        }
    )
    r = name_consistency(
        facts,
        {"compare": ["flight_booking"], "variant_threshold": 85, "fail_below": 70},
        _ctx(),
    )
    assert r.status == Status.NEEDS_HUMAN
    assert "MRZ" in (r.message or "")
    assert "SSS" not in (r.message or "")
    assert "Jeff" not in (r.message or "")


def test_bank_window_exactly_6_months() -> None:
    facts = Facts(
        documents={
            DocType.bank_statement: [
                BankStatementExtraction(
                    account_holder="A",
                    bank_name="B",
                    account_currency="USD",
                    period_start=date(2026, 5, 1),
                    period_end=date(2026, 10, 31),
                    issue_date=date(2026, 11, 5),
                    opening_balance=1,
                    closing_balance=1000,
                    has_bank_stamp=True,
                )
            ]
        },
        submission_date=date(2026, 11, 16),
    )
    r = statement_window(facts, {"months": 6, "max_age_days": 31}, _ctx())
    assert r.status == Status.PASS


def test_sufficient_funds_hotel_65() -> None:
    facts = Facts(
        documents={
            DocType.hotel_booking: [
                HotelBookingExtraction(
                    guest_names=["A"],
                    hotel_name="H",
                    city="Paris",
                    country="FR",
                    check_in=date(2026, 12, 18),
                    check_out=date(2026, 12, 28),
                )
            ],
            DocType.flight_booking: [
                FlightBookingExtraction(
                    passenger_names=["A"],
                    segments=[
                        FlightSegment(
                            from_airport="BEY", to_airport="CDG", departure_date=date(2026, 12, 18)
                        ),
                        FlightSegment(
                            from_airport="CDG", to_airport="BEY", departure_date=date(2026, 12, 28)
                        ),
                    ],
                )
            ],
            DocType.bank_statement: [
                BankStatementExtraction(
                    account_holder="A",
                    bank_name="B",
                    account_currency="USD",
                    period_start=date(2026, 5, 1),
                    period_end=date(2026, 10, 31),
                    issue_date=date(2026, 11, 5),
                    opening_balance=0,
                    closing_balance=6200,
                    has_bank_stamp=True,
                )
            ],
        },
        submission_date=date(2026, 11, 16),
    )
    r = sufficient_funds(
        facts, {"eur_per_day": {"hotel": 65, "no_proof": 120, "attestation_accueil": 32.5}}, _ctx()
    )
    assert r.status == Status.PASS


def test_passport_valid_exactly_3_months() -> None:
    ret = date(2027, 1, 5)
    expiry = add_months(ret, 3)  # exactly 3 months
    facts = Facts(
        documents={
            DocType.passport: [
                PassportExtraction(
                    surname="A",
                    given_names="B",
                    passport_number="LR0000001",
                    nationality="LBN",
                    date_of_birth=date(1990, 1, 1),
                    sex="M",
                    issue_date=date(2020, 1, 1),
                    expiry_date=expiry,
                )
            ],
            DocType.flight_booking: [
                FlightBookingExtraction(
                    passenger_names=["A"],
                    segments=[
                        FlightSegment(
                            from_airport="BEY", to_airport="CDG", departure_date=date(2026, 12, 20)
                        ),
                        FlightSegment(
                            from_airport="CDG", to_airport="BEY", departure_date=ret
                        ),
                    ],
                )
            ],
        }
    )
    r = passport_valid_after_departure(facts, {"months": 3}, _ctx())
    assert r.status == Status.PASS
