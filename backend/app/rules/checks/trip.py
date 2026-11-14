from __future__ import annotations

from typing import Any

from app.models import DocType
from app.rules.checks._util import as_date, ev, fail, needs_human, ok, trip_dates
from app.rules.context import Facts, RuleContext
from app.rules.dates import add_months, inclusive_days
from app.rules.registry import register


@register("flight_round_trip")
def flight_round_trip(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    flight = facts.first(DocType.flight_booking)
    assert flight is not None
    home = set(params.get("home_airports") or ["BEY"])
    segs = list(getattr(flight, "segments", []) or [])
    evidence = [ev("flight_booking", "segments", len(segs))]
    if len(segs) < 2:
        return fail("TRIP.ROUND_TRIP", "Need outbound and return segments", evidence=evidence)
    first, last = segs[0], segs[-1]
    out_ok = first.from_airport in home
    back_ok = last.to_airport in home
    dates_ok = as_date(last.departure_date) >= as_date(first.departure_date)
    leaves_home = first.to_airport not in home
    if out_ok and back_ok and dates_ok and leaves_home:
        return ok("TRIP.ROUND_TRIP", "Round-trip from home airport", evidence=evidence)
    return fail("TRIP.ROUND_TRIP", "Flight is not a round trip from home", evidence=evidence)


@register("stay_length_max")
def stay_length_max(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    arrival, ret = trip_dates(facts)
    assert arrival and ret
    days = inclusive_days(arrival, ret)
    mx = int(params.get("max_days", 90))
    evidence = [ev("flight_booking", "stay_days", days)]
    if days <= mx:
        return ok("TRIP.MAX_90_DAYS", f"Stay {days} days <= {mx}", evidence=evidence)
    return fail("TRIP.MAX_90_DAYS", f"Stay {days} days exceeds {mx}", evidence=evidence)


@register("filing_window")
def filing_window(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    arrival, _ = trip_dates(facts)
    assert arrival
    min_days = int(params.get("min_days_before_departure", 15))
    max_months = int(params.get("max_months_before_departure", 6))
    delta = (arrival - ctx.submission_date).days
    earliest = add_months(ctx.submission_date, max_months)
    evidence = [ev("flight_booking", "days_before_departure", delta)]
    if delta < min_days:
        return needs_human(
            "TRIP.FILING_WINDOW",
            f"Departure only {delta} days after filing (min {min_days})",
            evidence=evidence,
        )
    if arrival > earliest:
        return needs_human(
            "TRIP.FILING_WINDOW",
            f"Departure {arrival} more than {max_months} months after filing",
            evidence=evidence,
        )
    return ok("TRIP.FILING_WINDOW", f"Filing window OK ({delta} days)", evidence=evidence)


@register("accommodation_covers_stay")
def accommodation_covers_stay(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    hotel = facts.first(DocType.hotel_booking)
    arrival, ret = trip_dates(facts)
    assert hotel and arrival and ret
    cin = as_date(hotel.check_in)
    cout = as_date(hotel.check_out)
    evidence = [
        ev("hotel_booking", "check_in", cin),
        ev("hotel_booking", "check_out", cout),
        ev("flight_booking", "arrival", arrival),
        ev("flight_booking", "return", ret),
    ]
    # check-in <= arrival, check-out >= return (hotel night of return not required if departing that day —
    # expected case05: hotel ends 20, return 23 → FAIL. So checkout must be >= return date.
    if cin <= arrival and cout >= ret:
        return ok("TRIP.HOTEL_COVERS_STAY", "Hotel covers stay", evidence=evidence)
    msg = params.get("message") or "Hotel {checkin}->{checkout} does not cover stay {arrival}->{return}."
    msg = (
        msg.replace("{checkin}", cin.strftime("%d/%m/%Y"))
        .replace("{checkout}", cout.strftime("%d/%m/%Y"))
        .replace("{arrival}", arrival.strftime("%d/%m/%Y"))
        .replace("{return}", ret.strftime("%d/%m/%Y"))
    )
    return fail("TRIP.HOTEL_COVERS_STAY", msg, evidence=evidence)


@register("hotel_country_in")
def hotel_country_in(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    hotel = facts.first(DocType.hotel_booking)
    assert hotel is not None
    allowed = set(params.get("countries") or ["FR"])
    country = str(hotel.country).upper()
    evidence = [ev("hotel_booking", "country", country)]
    if country in allowed:
        return ok("TRIP.HOTEL_IN_DESTINATION", f"Hotel in {country}", evidence=evidence)
    return needs_human(
        "TRIP.HOTEL_IN_DESTINATION",
        f"Hotel country {country} not in {sorted(allowed)}",
        evidence=evidence,
    )
