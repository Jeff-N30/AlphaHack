# VisaRef: eval plan

## Two layers, so you know *what* broke
1. **Rules-only** (`backend/tests/test_cases.py`): facts are built straight from `case.yaml`, with no LLM. This has to be 100%, or there's a rules bug.
2. **Full pipeline** (`backend/app/eval/run.py` → `eval/score.py`): images → LLM → MRZ → rules → draft. Any gap between the two layers comes from extraction or drafting.

## Case format
- `case.yaml`: the fake applicant's data for each document. `tools/generate_fake_docs.py` renders it into `docs/`, so it's also the extraction ground truth.
- `expected.yaml`: `outcome`, `escalations`, `critical_rules`, per-rule `rules` (PASS | FAIL | NEEDS_HUMAN | SKIPPED), and `draft_message.must_mention` / `must_not_mention`.
- Fixed `submission_date: 2026-11-16`, so results never depend on today's date.

## Scoring (`eval/score.py`)
- A **case passes** when the outcome matches, every critical rule matches, and, if a draft is required, it contains every `must_mention` string (dates as DD/MM/YYYY) and none of the `must_not_mention` strings.
- It also reports **rule accuracy** (all rules), **cases needing Gloria** (escalations > 0) and **$/application**.
- Each run appends to `eval/history.csv` → this is the line you post Fri/Sat/Sun night:
  `Sat night: 17/20 (85%) · rule acc 97.4% · Gloria needed 4/20 · $0.12/application`

## The 5 seed cases
| Case | Scenario | Expected outcome | Key rule |
|---|---|---|---|
| case01_complete | everything valid | READY_FOR_APPROVAL | all PASS |
| case02_missing_insurance | no insurance doc | SEND_BACK | DOC.PRESENT FAIL; INS.* skipped |
| case03_passport_validity | expires 10/02/2027, return 05/01/2027 | SEND_BACK | PP.VALID_AFTER_DEPARTURE FAIL |
| case04_name_mismatch | bank says MOHAMMAD, passport MOHAMAD | NEEDS_GLORIA | ID.NAME_MATCH NEEDS_HUMAN |
| case05_wrong_dates | hotel ends 20/12, flight back 23/12 | SEND_BACK | TRIP.HOTEL_COVERS_STAY FAIL |

## Scaling cases (seeded via `python tools/seed_eval_cases.py`)

### France checklist / classic failures (06–20)
| # | Scenario | Expected |
|---|---|---|
| 06 | insurance coverage €25,000 | INS.MIN_COVERAGE FAIL → SEND_BACK |
| 07 | insurance territory "France only" (OTHER) | INS.TERRITORY FAIL → SEND_BACK |
| 08 | insurance ends 1 day before return flight | INS.COVERS_STAY FAIL → SEND_BACK |
| 09 | bank statement covers only 3 months | BANK.WINDOW FAIL → SEND_BACK |
| 10 | bank statement issued 45 days before submission | BANK.WINDOW FAIL → SEND_BACK |
| 11 | closing balance USD 500 | BANK.SUFFICIENT_FUNDS FAIL → SEND_BACK |
| 12 | large recent deposit | BANK.LARGE_RECENT_DEPOSIT NEEDS_HUMAN → NEEDS_GLORIA |
| 13 | passport issued > 10 years ago | PP.ISSUED_WITHIN_10Y FAIL → SEND_BACK |
| 14 | passport already expired | PP.NOT_EXPIRED FAIL → SEND_BACK |
| 15 | MRZ digit tampered | PP.MRZ_CHECKSUM NEEDS_HUMAN → NEEDS_GLORIA |
| 16 | one-way flight | TRIP.ROUND_TRIP FAIL → SEND_BACK |
| 17 | departure 10 days after submission | TRIP.FILING_WINDOW → NEEDS_GLORIA |
| 18 | form passport number typo | ID.FORM_MATCHES_PASSPORT FAIL → SEND_BACK |
| 19 | phone-photo + name order swap | READY_FOR_APPROVAL (robustness) |
| 20 | employer leave ends before return | EMP.LEAVE_COVERS_TRIP FAIL → SEND_BACK |

### Lebanon / Arabic / ekhraj / agent edge cases (21–32)
| # | Scenario | Expected |
|---|---|---|
| 21 | **Ekhraj kaid** older than 6 months | FAM.ISSUED_WITHIN_6M FAIL → SEND_BACK |
| 22 | **Ekhraj missing** | DOC.PRESENT FAIL → SEND_BACK |
| 23 | **Ekhraj Arabic-only, no translation** | NEEDS_GLORIA (+ ask translation) |
| 24 | **Arabic-only employment letter** | NEEDS_GLORIA (translation / name) |
| 25 | **LBP bank currency** (no FX guess) | BANK.SUFFICIENT_FUNDS NEEDS_HUMAN → NEEDS_GLORIA |
| 26 | **Scanned PDF image-only** bank | READY (rules); full pipeline must OCR |
| 27 | **Wrong filename** (passport content as hotel_booking.pdf) | READY — classify by content |
| 28 | **Bilingual FR+AR hotel** | READY_FOR_APPROVAL |
| 29 | **Missing CNSS** | DOC.PRESENT FAIL → SEND_BACK |
| 30 | **Arabic payslip month labels** | READY (rules); OCR may escalate |
| 31 | **Unknown extra doc** (utility bill) | NEEDS_GLORIA |
| 32 | **AL/EL name particles** (El-Hajj / AL HAJJ) | READY — normalizer |

Also covered by pipeline design (not always separate folders): image-inside-PDF, PNG/JPG, reject `.exe`, low-confidence OCR → NEEDS_HUMAN.

Mix aims for many SEND_BACK / some NEEDS_GLORIA / few READY — mirrors real Beirut files.

## Unseen cases (Sunday live)
Before the judging, a teammate writes two cases **without looking at the code**. Run them cold. If the system meets something it doesn't know (a new document type or a new currency), the right answer is **NEEDS_GLORIA**, not a crash and not a guess.

## Human count: plan to reduce it
Track `escalations` by rule ID across runs. The biggest sources and their fixes:
- **Name variants:** a known-variant table shown as an explanation, plus Gloria's override history (rule stays NEEDS_HUMAN when spellings differ, since the consulate wants a match).
- **Low confidence:** a capture guide in the request message ("photograph flat, no glare"), digital PDFs preferred, and a text-layer-first path.
- **Bank stamp:** per-bank templates learned from overrides.
Report: "Sat: 6/20 needed Gloria → Sun: 4/20, and here's why."
