"""DEMO_OFFLINE stand-ins shaped like a real Amadeus + Euromed + France-Visas pack.

Specimen / dummy only — not a real person's live identity for production use.
Field shapes match what Jeff's legit PDFs require the LLM to fill.
"""
from __future__ import annotations

from datetime import date

from app.models import (
    ApplicationFormExtraction,
    FlightBookingExtraction,
    FlightSegment,
    Money,
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
