"""Versioned extract prompts + few-shots. Bump PROMPT_VERSION when these change."""

SYSTEM = """You extract visa-file fields into ONE JSON object matching the given schema.
Rules:
- Copy values from the document text only. Do not invent passport numbers, dates, or amounts.
- Never output PASS, FAIL, valid, sufficient, expired, or compliant — fields only.
- Airports = IATA 3 letters (BEY, CDG). Countries = ISO alpha-2 (FR, LB).
- Currencies = ISO 4217 (USD, EUR). Never convert. Never use LBP unless printed.
- Dates = YYYY-MM-DD in the JSON. Source docs use European day-first (Lebanon/France):
  "10/12/2026" and "10-12-2026" mean 10 December 2026 → 2026-12-10 (NOT October 12).
  "05/12/2026" → 2026-12-05. Prefer month names when present ("10 December 2026").
  Never swap day and month.
- Names: keep order as printed; uppercase OK. Strip titles MR/MRS/MS later in code.
- If a field is missing in the text, use null only when the schema allows; else omit or empty list.
- anomaly_flags: oddities only (blurry, missing stamp, currency weird) — never a verdict.
"""

_FLIGHT_SHOT = """
EXAMPLE INPUT (Amadeus-style):
Traveler KARIM NASSAR Booking ref: FAKE13
Wednesday 18 December 2026 Middle East Airlines XX 0201
Departure Beirut (BEY) Arrival Paris Charles de Gaulle (CDG)
Tuesday 28 December 2026 XX 0202 Departure CDG Arrival BEY

EXAMPLE JSON:
{"doc_type":"flight_booking","language":"en","anomaly_flags":[],"passenger_names":["KARIM NASSAR"],"booking_reference":"FAKE13","passport_number":null,"segments":[{"from_airport":"BEY","to_airport":"CDG","to_country":"FR","departure_date":"2026-12-18","flight_number":"XX0201"},{"from_airport":"CDG","to_airport":"BEY","to_country":"LB","departure_date":"2026-12-28","flight_number":"XX0202"}],"field_meta":{}}
"""

FLIGHT_USER = """Document type: flight booking / e-ticket / Amadeus itinerary.
Extract passenger_names, booking_reference, optional passport_number, and ALL segments
(from_airport, to_airport, to_country, departure_date, flight_number).
Outbound first, return last. Round-trip = at least 2 segments.
Numeric dates are DAY/MONTH/YEAR (European). Example: printed 10/12/2026 → departure_date 2026-12-10.
""" + _FLIGHT_SHOT + """
--- DOCUMENT TEXT ---
<<<TEXT>>>
"""

_INS_SHOT = """
EXAMPLE INPUT:
TRAVEL INSURANCE COVER NOTE
Beneficiary KARIM NASSAR DOB 12/03/1994 Passport LR0482913
Period of Coverage: 18 Dec 2026 to 28 Dec 2026
Destination: France, Schengen States Medical Coverage: 30,000 EUR
Covers emergency medical, hospitalization, repatriation

EXAMPLE JSON:
{"doc_type":"travel_insurance","language":"en","anomaly_flags":[],"insured_name":"KARIM NASSAR","date_of_birth":"1994-03-12","passport_number":"LR0482913","insurer":"Specimen Assurance","policy_number":"TI-2026-2913","coverage":{"amount":30000,"currency":"EUR"},"territory":"SCHENGEN","territory_raw":"France, Schengen States","start_date":"2026-12-18","end_date":"2026-12-28","covers":["emergency_medical","hospitalisation","repatriation"],"field_meta":{}}
"""

INSURANCE_USER = """Document type: Schengen / travel medical insurance cover note.
Extract insured_name, date_of_birth, passport_number, insurer, policy_number,
coverage {{amount, currency}}, territory (SCHENGEN|EUROPE|WORLDWIDE|OTHER|UNCLEAR),
territory_raw, start_date, end_date, covers.
If amount is 100,000 USD and destination Schengen → territory SCHENGEN, currency USD.
""" + _INS_SHOT + """
--- DOCUMENT TEXT ---
<<<TEXT>>>
"""

_FORM_SHOT = """
EXAMPLE INPUT:
Harmonised application form Application for Schengen Visa
1.Surname: NASSAR  3.First name(s): KARIM
4.Date of birth: 12-03-1994
13.Number of travel document: LR0482913  15.Valid until: 09-05-2032
Intended arrival 18/12/2026 departure 28/12/2026 Signature present

EXAMPLE JSON:
{"doc_type":"application_form","language":"en","anomaly_flags":[],"surname":"NASSAR","given_names":"KARIM","date_of_birth":"1994-03-12","passport_number":"LR0482913","expiry_date":"2032-05-09","france_visas_reference":null,"intended_arrival":"2026-12-18","intended_departure":"2026-12-28","signed":true,"field_meta":{}}
"""

APPLICATION_FORM_USER = """Document type: Harmonised Schengen / France-Visas application form
(not an employment letter — ignore occupation/employer fields for extraction type).
Extract surname, given_names, date_of_birth, passport_number, expiry_date,
optional france_visas_reference, intended_arrival, intended_departure, signed.
Numeric dates are DAY/MONTH/YEAR. Example: intended travel 10/12/2026 → 2026-12-10 (December), never 2026-10-12.
""" + _FORM_SHOT + """
--- DOCUMENT TEXT ---
<<<TEXT>>>
"""
