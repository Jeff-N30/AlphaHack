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

_HOTEL_SHOT = """
EXAMPLE INPUT:
BOOKING CONFIRMATION Hotel Specimen Montmartre Paris France
Guest: KARIM NASSAR Confirmation HB-000913
Check-in 18/12/2026 Check-out 28/12/2026 Prepaid / free cancellation

EXAMPLE JSON:
{"doc_type":"hotel_booking","language":"en","anomaly_flags":[],"guest_names":["KARIM NASSAR"],"hotel_name":"Hotel Specimen Montmartre","city":"Paris","country":"FR","check_in":"2026-12-18","check_out":"2026-12-28","confirmation_number":"HB-000913","prepaid_or_free_cancellation":true,"field_meta":{}}
"""

HOTEL_USER = """Document type: hotel booking / reservation confirmation.
Extract guest_names, hotel_name, city, country (ISO alpha-2), check_in, check_out,
optional confirmation_number, prepaid_or_free_cancellation.
Numeric dates are DAY/MONTH/YEAR (European) for BOTH check_in and check_out.
Examples: 04/02/2026 → 2026-02-04; 10/02/2026 → 2026-02-10 (NOT 2026-10-10).
check_out must be after check_in.
""" + _HOTEL_SHOT + """
--- DOCUMENT TEXT ---
<<<TEXT>>>
"""

_BANK_SHOT = """
EXAMPLE INPUT:
Banque Specimen du Liban Statement Fresh USD current account
Account holder KARIM NASSAR Currency USD
Period 01/05/2026 to 31/10/2026 Issued 05/11/2026
Opening 3400.00 Closing 6200.00 Bank stamp present
28/05/2026 SALARY 1800.00  28/08/2026 SALARY 1800.00

EXAMPLE JSON:
{"doc_type":"bank_statement","language":"en","anomaly_flags":[],"account_holder":"KARIM NASSAR","bank_name":"Banque Specimen du Liban","account_currency":"USD","account_type_raw":"Fresh USD current account","period_start":"2026-05-01","period_end":"2026-10-31","issue_date":"2026-11-05","opening_balance":3400.0,"closing_balance":6200.0,"has_bank_stamp":true,"transactions":[{"date":"2026-05-28","description":"SALARY","amount":1800.0,"balance_after":null},{"date":"2026-08-28","description":"SALARY","amount":1800.0,"balance_after":null}],"field_meta":{}}
"""

BANK_USER = """Document type: bank account statement / relevé bancaire.
Extract account_holder, bank_name, account_currency (ISO 4217 as printed — never invent LBP FX),
optional account_type_raw, period_start, period_end, issue_date,
opening_balance, closing_balance, has_bank_stamp, and transactions
(date, description, amount as +credit / -debit, optional balance_after).
Numeric dates are DAY/MONTH/YEAR. Copy amounts as printed; do not convert currency.
""" + _BANK_SHOT + """
--- DOCUMENT TEXT ---
<<<TEXT>>>
"""

_EMP_SHOT = """
EXAMPLE INPUT:
TO WHOM IT MAY CONCERN
This is to certify that KARIM NASSAR has been employed with Specimen Soft SAL
as Software Engineer since 01/03/2020. Monthly salary: 1800 USD.
Leave of absence approved from 18/12/2026 to 28/12/2026 for tourism to France.
Letter date: 05/11/2026. HR Manager (signed and stamped).

EXAMPLE JSON:
{"doc_type":"employment_letter","language":"en","anomaly_flags":[],"employee_name":"KARIM NASSAR","employer_name":"Specimen Soft SAL","position":"Software Engineer","hire_date":"2020-03-01","monthly_salary":{"amount":1800.0,"currency":"USD"},"leave_start":"2026-12-18","leave_end":"2026-12-28","letter_date":"2026-11-05","signed_and_stamped":true,"field_meta":{}}
"""

EMPLOYMENT_USER = """Document type: employer / employment letter (not the Schengen application form).
Extract employee_name, employer_name, optional position, hire_date, monthly_salary {{amount, currency}},
leave_start, leave_end, letter_date, signed_and_stamped.
Numeric dates are DAY/MONTH/YEAR. Currency ISO 4217 as printed.
""" + _EMP_SHOT + """
--- DOCUMENT TEXT ---
<<<TEXT>>>
"""

_PAY_SHOT = """
EXAMPLE INPUT:
PAYSLIP / BULLETIN DE PAIE
Employer: Specimen Soft SAL  Employee: KARIM NASSAR
Period (YYYY-MM): 2026-10  Net pay: 1800.00 USD

EXAMPLE JSON:
{"doc_type":"payslip","language":"en","anomaly_flags":[],"employee_name":"KARIM NASSAR","employer_name":"Specimen Soft SAL","period_month":"2026-10","net_pay":{"amount":1800.0,"currency":"USD"},"field_meta":{}}
"""

PAYSLIP_USER = """Document type: payslip / bulletin de paie.
Extract employee_name, employer_name, period_month as YYYY-MM, net_pay {{amount, currency}}.
If only month name + year printed, convert to YYYY-MM (October 2026 → 2026-10).
""" + _PAY_SHOT + """
--- DOCUMENT TEXT ---
<<<TEXT>>>
"""

_FAM_SHOT = """
EXAMPLE INPUT:
EXTRACT OF FAMILY REGISTER — Ekhraj Kaid Aily — CERTIFIED TRANSLATION
Head of family: NASSAR JOSEPH
Members: KARIM NASSAR, RANA NASSAR
Issue date of extract: 15/06/2026  Translated: true

EXAMPLE JSON:
{"doc_type":"family_register","language":"en","anomaly_flags":[],"head_of_family":"NASSAR JOSEPH","members":["KARIM NASSAR","RANA NASSAR"],"issue_date":"2026-06-15","translated":true,"field_meta":{}}
"""

FAMILY_REGISTER_USER = """Document type: family register extract / ekhraj kaid aily (civil status).
Extract optional head_of_family, members list, issue_date, optional translated (true if EN/FR translation noted).
Numeric dates are DAY/MONTH/YEAR.
""" + _FAM_SHOT + """
--- DOCUMENT TEXT ---
<<<TEXT>>>
"""
