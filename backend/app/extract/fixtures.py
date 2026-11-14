"""DEMO_OFFLINE stand-ins shaped like a real Amadeus + Euromed + France-Visas pack.

Specimen / dummy only — not a real person's live identity for production use.
Field shapes match what Jeff's legit PDFs require the LLM to fill.
"""
from __future__ import annotations

from datetime import date

from app.models import (
    ApplicationFormExtraction,
    BankStatementExtraction,
    FlightBookingExtraction,
    FlightSegment,
    HotelBookingExtraction,
    Money,
    Transaction,
    TravelInsuranceExtraction,
)

# Same trip shape as the legit demo pack: BEY↔CDG Feb 2026, Schengen insurance covering stay.
FIXTURE_FLIGHT = FlightBookingExtraction(
    language="en",
    anomaly_flags=[],
    passenger_names=["JEFF DEMO NADER"],
    booking_reference="YM3MB6",
    passport_number=None,
    segments=[
        FlightSegment(
            from_airport="BEY",
            to_airport="CDG",
            to_country="FR",
            departure_date=date(2026, 2, 4),
            flight_number="ME211",
        ),
        FlightSegment(
            from_airport="CDG",
            to_airport="BEY",
            to_country="LB",
            departure_date=date(2026, 2, 10),
            flight_number="ME212",
        ),
    ],
    field_meta={},
)

FIXTURE_INSURANCE = TravelInsuranceExtraction(
    language="en",
    anomaly_flags=[],
    insured_name="JEFF DEMO NADER",
    date_of_birth=date(2003, 6, 3),
    passport_number="LR0000999",
    insurer="Euromed Brokers s.a.l (specimen)",
    policy_number="AM-EURO-W-0000",
    coverage=Money(amount=100_000, currency="USD"),
    territory="SCHENGEN",
    territory_raw="France, Schengen States / Worldwide Excluding US, CA, JP, AU and Singapore",
    start_date=date(2026, 2, 4),
    end_date=date(2026, 3, 6),
    covers=["emergency_medical", "hospitalisation", "repatriation"],
    field_meta={},
)

FIXTURE_APPLICATION_FORM = ApplicationFormExtraction(
    language="en",
    anomaly_flags=[],
    surname="NADER",
    given_names="JEFF",
    date_of_birth=date(2003, 6, 3),
    passport_number="LR0000999",
    expiry_date=date(2034, 12, 15),
    france_visas_reference=None,
    intended_arrival=date(2026, 2, 4),
    intended_departure=date(2026, 2, 10),
    signed=True,
    field_meta={},
)

FIXTURE_HOTEL = HotelBookingExtraction(
    language="en",
    anomaly_flags=[],
    guest_names=["JEFF DEMO NADER"],
    hotel_name="Hotel Specimen Montmartre (FAKE)",
    city="Paris",
    country="FR",
    check_in=date(2026, 2, 4),
    check_out=date(2026, 2, 10),
    confirmation_number="HB-DEMO-001",
    prepaid_or_free_cancellation=True,
    field_meta={},
)

FIXTURE_BANK = BankStatementExtraction(
    language="en",
    anomaly_flags=[],
    account_holder="JEFF DEMO NADER",
    bank_name="Banque Specimen du Liban (FAKE)",
    account_currency="USD",
    account_type_raw="Fresh USD current account",
    period_start=date(2025, 8, 1),
    period_end=date(2026, 1, 31),
    issue_date=date(2026, 2, 1),
    opening_balance=3400.0,
    closing_balance=6200.0,
    has_bank_stamp=True,
    transactions=[
        Transaction(date=date(2025, 11, 28), description="SALARY", amount=1800.0),
        Transaction(date=date(2025, 12, 28), description="SALARY", amount=1800.0),
    ],
    field_meta={},
)
