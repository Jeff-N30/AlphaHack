# VisaRef: prompts

Prompts are versioned (`PROMPT_VERSION`) and live in `backend/app/extract/prompts/` and `backend/app/drafts/prompts/`.
The JSON schema always comes from `schemas/models.py` (`Model.model_json_schema()`), and is never hand-written in the prompt.

---
## A. Page classification (Gemini 3.8 Flash or 3.1 Flash-Lite)
```text
SYSTEM
You label pages of a visa application file. Return JSON matching the schema.
doc_type is one of: application_form, photo, passport, flight_booking, hotel_booking, travel_insurance,
bank_statement, employment_letter, payslip, cnss_certificate, family_register, travel_plan, unknown.
Use "unknown" if unsure. confidence is 0..1 and reflects how sure you are of the label only.
Ignore watermarks such as "SPECIMEN" or "FAKE TEST DATA": they mark test documents.

USER
[image: page N of file "<filename>"]
```

## B. Document extraction (core prompt; one call per document, all its pages attached)
```text
SYSTEM
You are a meticulous document transcriber for a travel agency. You READ documents; you do NOT judge them.
Return ONLY JSON that validates against the provided schema for doc_type = {doc_type}.

Rules:
1. Copy values exactly as printed. Do not correct spellings, do not translate names, do not infer missing values.
   If a field is not visible or illegible, return null. Never guess.
2. Dates -> ISO format YYYY-MM-DD. Documents from Lebanon/France usually print DD/MM/YYYY: 05/11/2026 = 2026-11-05.
   If the day/month order is ambiguous, still convert using DD/MM and set that field's confidence <= 0.6.
3. Money -> {amount: number, currency: ISO 4217}. "€" = EUR, "$" or "USD" = USD. Keep the currency as printed.
4. Names: copy Latin-script names in UPPERCASE as printed. If an Arabic-script name is printed, also fill the *_ar field.
5. Passport: also transcribe the two MRZ lines at the bottom character by character into mrz_lines
   (44 characters each, use "<" exactly as printed). Do not fix check digits.
6. Bank statements: list every transaction row (date, description, signed amount). has_bank_stamp = true only if a
   bank stamp/seal is visibly present.
7. Insurance: territory = SCHENGEN | EUROPE | WORLDWIDE | OTHER | UNCLEAR based on the printed territory text,
   and copy that text into territory_raw. covers = only items explicitly printed.
8. For EVERY non-null field add field_meta[field] = {page, confidence (0..1), raw_text (the printed snippet)}.
9. anomaly_flags: list short factual observations ONLY if you see them (e.g. "font of closing balance differs from
   rest of page", "date appears overwritten", "stamp missing on page 2"). Never write conclusions like "valid",
   "fake", "approved", "sufficient". Ignore watermarks "SPECIMEN" / "FAKE TEST DATA" (test-data markers).
10. Do not output anything except the JSON.

USER
doc_type: {doc_type}
file: {filename}
[images: pages 1..n]
[optional: text layer from pdfplumber, labelled "TEXT LAYER (may be incomplete)"]
```
**Code after the call:** validate with Pydantic → on error, re-ask once with the validation error appended → still failing → mark the doc NEEDS_HUMAN. For passports, run `extract/mrz.py` (passporteye first, then `mrz_lines`) and **overwrite** number/DOB/expiry/sex/nationality/name with the MRZ values when the checksums are valid.

## C. Applicant message drafting (Claude Sonnet 5.5)
Code passes **facts only**, already computed:
```json
{
  "applicant_first_name": "Rana",
  "language": "en",                     // en | fr | ar-LB (Lebanese Arabic in Arabic script)
  "agency_name": "<agency>",
  "officer_name": "Gloria",
  "destination": "France (Schengen short-stay visa)",
  "appointment_date": "02/12/2026",     // or null
  "issues": [
    {"rule_id": "TRIP.HOTEL_COVERS_STAY",
     "problem": "Your hotel booking ends on 20/12/2026 but your return flight is on 23/12/2026.",
     "needed": "A hotel booking (or bookings) covering every night from 12/12/2026 to 23/12/2026."}
  ]
}
```
```text
SYSTEM
You write short WhatsApp messages for a Lebanese travel agency, on behalf of the visa officer.
You will receive a JSON list of issues that the agency's checking system already found. Your job is wording only.

Rules:
- Mention EVERY issue in the JSON and NOTHING else. Do not add requirements, advice, deadlines or legal opinions.
- Keep every date exactly as given (DD/MM/YYYY) and every amount exactly as given (e.g. "€30,000").
- Never say the visa will be refused/rejected/approved. Never mention internal rule IDs, scores or AI.
- Warm, professional, brief: greeting with first name, one line of context, numbered list of what to send, thank-you,
  signed "{officer_name} – {agency_name}".
- language "ar-LB": natural Lebanese Arabic in Arabic script, polite; keep dates, amounts, document names in Latin if clearer.
- Max 120 words. Plain text, no markdown headers.
Return JSON: {"body": "...", "language": "..."}

USER
{facts_json}
```
**Code after the call:** check that every date and amount from `issues` appears verbatim in `body`, and that none of `refused|rejected|approved|LBP` appears. If the check fails, regenerate once, then fall back to a deterministic template. Save the result as `DraftStatus.DRAFT`. **No send happens here.**

## D. Optional: internal note for Gloria (NEEDS_HUMAN summary)
```text
Summarise for the officer, in 3 bullets max, why this file needs her attention. Use only the provided check results
(rule_id, message, evidence). No recommendations beyond "check X against Y".
```

---
## E. Cursor build sequence: paste in order (Agent mode)
> Before you start, put this whole folder at the repo root. `.cursor/rules/visaref.mdc` is always on.
> After each prompt: run the tests, commit, and move on. If the agent drifts, reply "re-read .cursor/rules/visaref.mdc".

**1. Scaffold**
```
Read README.md, BUILD.md (sections 1-4), STACK.md and .cursor/rules/visaref.mdc.
Create the backend skeleton exactly as BUILD.md §4: backend/pyproject.toml (deps from STACK.md §3), backend/app/{main.py,config.py}
with pydantic-settings reading .env, empty packages ingest/ extract/ rules/ drafts/ lock/ outbound/ storage/ eval/.
Copy schemas/models.py to backend/app/models.py (keep schemas/ as the source of truth; add a test that they are identical).
Add .gitignore (data/, .env, .venv, node_modules, eval/cases/*/docs, runs/). Add `GET /health`. Add pytest config.
Don't write business logic yet. Run pytest.
```

**2. MRZ engine (main risk first)**
```
Implement backend/app/extract/mrz.py:
- read_mrz_image(path) using passporteye (handle None) -> raw 2 lines
- parse_td3(lines) -> models.MRZ using the `mrz` library's TD3CodeChecker for check digits; list failed checks
- best_mrz(image_path, llm_lines) tries passporteye then llm_lines; returns first with all checksums valid, else the best partial with checksums_valid=False
- compare_viz(mrz, passport_extraction) -> list of mismatched fields
2-digit years: DOB century = 19xx if yy > current yy else 20xx; expiry always 20xx.
Tests (tests/test_mrz.py): every eval/cases/*/docs/passport.png parses with checksums_valid=True and matches passport_mrz.txt;
a tampered string (change one expiry digit) has checksums_valid=False; passport_phone.jpg in case04 still parses (mark xfail if tesseract can't).
Run: python tools/generate_fake_docs.py --degrade first.
```

**3. Names and dates helpers**
```
Implement backend/app/rules/names.py (normalize_name, compare_names(reference, candidate, variant_threshold, fail_below) -> (Status, score, normalized pair))
and backend/app/rules/dates.py (add_months via relativedelta, inclusive_days(a,b), nights(a,b), months_covered(start,end)).
Follow .cursor/rules name rules exactly (token_sort_ratio, never token_set_ratio).
Tests: "NASSAR/KARIM MR" vs "KARIM NASSAR" -> PASS; "MOHAMMAD AL HAJJ" vs MRZ "AL HAJJ / MOHAMAD" -> NEEDS_HUMAN (~96.8);
"EL HAJJ" vs "AL-HAJJ" -> PASS; "KARIM" vs "KARIM NASSAR" -> not PASS; "GEORGES HADDAD" vs "RANA SALEH" -> FAIL.
Date tests: 2027-01-05 + 3 months = 2027-04-05; 2026-12-18..2026-12-28 = 11 days.
```

**4. Checklist loader + rules engine (no LLM)**
```
Implement backend/app/rules/engine.py and registry.py:
- load checklist YAML into a pydantic Checklist model (validate: unique ids, every `check` exists in registry, mode in code|llm_flag|manual)
- Facts = dict[DocType, list[Extraction]] + submission_date + profile
- run(checklist, facts) -> AuditReport: expand DOC.PRESENT over required_documents (respect `when` and min_count),
  skip rules whose `docs` are missing (-> skipped_rules), apply fail_status overrides, compute outcome and escalations exactly as the YAML `outcome:` section.
Then implement every `check:` named in checklists/fr-schengen-short-stay.yaml in rules/checks/{passport,identity,trip,insurance,funds,employment,civil,suspicion}.py.
sufficient_funds: days = inclusive stay days from flights; per-day amount by accommodation type (hotel booking present -> hotel);
convert closing_balance with fx_rates_to_eur; unknown currency -> NEEDS_HUMAN.
Write tests/test_cases.py: build Facts directly from each eval/cases/*/case.yaml (no LLM; MRZ from passport_mrz.txt) and assert
per-rule statuses, skipped rules and outcome equal expected.yaml. Iterate until 5/5.
```

**5. LLM adapter + cost logging**
```
Implement backend/app/extract/llm.py with a Provider protocol and GeminiProvider (google-genai) + AnthropicProvider (anthropic):
structured(model, system, parts(images/text), schema: type[BaseModel]) -> (instance, CostLine).
Use JSON-schema structured output for each provider, Pydantic validation, one re-ask on ValidationError, tenacity retries on 429/5xx,
timeouts from env. Count input/output tokens (incl. thinking) from the response usage fields; price from env vars.
Cache by sha256(images)+model+PROMPT_VERSION in data/cache/. DEMO_OFFLINE=1 -> cache only.
Unit-test with a fake provider. Do not call real APIs in unit tests.
```

**6. Ingest, classify, extract**
```
Implement ingest/render.py (PyMuPDF 200 dpi pages, Pillow EXIF transpose, max 2000px, pdfplumber text layer if present),
extract/classify.py and extract/extract.py using PROMPTS.md sections A and B verbatim (store as prompt files).
Wire the passport path to mrz.best_mrz and overwrite fields from MRZ when checksums are valid.
Create scripts/extract_eval.py: for each case, run extraction on docs/, compare every field to case.yaml, print field accuracy per doc type.
Run it on the 5 cases with EXTRACT_MODEL=gemini-3.8-flash, then with claude-haiku-5-5. Report accuracy and $ per case.
```

**7. Full pipeline + eval runner**
```
Implement backend/app/eval/run.py: for each eval/cases/*/docs run ingest -> classify -> extract -> rules -> draft and write
runs/<label>/<case_id>.json (AuditReport incl. drafts and cost). Then `python eval/score.py runs/<label> <label>`.
Add a Makefile: make docs (generate fake docs), make test, make eval LABEL=sat-night.
```

**8. Drafter**
```
Implement drafts/drafter.py per PROMPTS.md section C: build the facts JSON from FAIL results with on_fail=request
(rule message templates live in the checklist YAML `message`/fix hints), call DRAFT_MODEL, verify dates/amounts verbatim and banned words,
fallback template, save ApplicantMessageDraft(status=DRAFT). Languages: en, fr, ar-LB. Tests with a fake provider.
```

**9. Lock + audit + retention**
```
Implement lock/tokens.py (one-time confirm tokens bound to application_id+action, 120s TTL, single use),
lock/actions.py (send_draft, approve_application, override_check(reason)), outbound/{copy,whatsapp,email}.py,
storage/audit.py, storage/retention.py (APScheduler job purging files per RETENTION_* env), auth via OFFICER_PIN -> signed session cookie.
API endpoints per BUILD.md §3. tests/test_lock.py: AST-scan extract/, rules/, drafts/ for any import of app.outbound or app.lock -> fail;
send without session -> 401; without token -> 403; replayed token -> 409; SENT requires approved_by/approved_at.
```

**10. Frontend**
```
Create frontend/ with Next.js 16 (App Router, TS strict), Tailwind v4, shadcn/ui, TanStack Query.
Pages: /inbox (applications list with outcome badges + upload dialog: files + destination select from GET /checklists),
/applications/[id] (left: checks grouped by category with PASS green / FAIL red / NEEDS_HUMAN amber badges, evidence popover with page crop
and source link; right: document viewer; bottom: draft editor), /metrics (recharts line of eval/history.csv pass rate + needs_gloria, avg $/application).
Send and Approve buttons open a confirm Dialog that first POSTs /confirm-tokens, then calls the lock endpoint. Officer PIN login page.
Clean, calm, professional UI. Show "Checked in Xs · $0.0Y" on each application.
```

**11. Scale to 20 cases**
```
Following eval/README.md, add case06..case20 as case.yaml + expected.yaml by copying case01 and changing only what each scenario needs.
Regenerate docs (with --degrade for 3 of them), run tests/test_cases.py (rules-only) to 20/20, then run make eval LABEL=sat-night and print the score.
List every failing case with the reason (extraction vs rule vs draft).
```

**12. Demo hardening**
```
Add DEMO_OFFLINE replay, a seeded demo DB with case01/04/05 pre-uploaded, a /applications/{id}/run progress stream (SSE) so checks appear live,
and a one-page /about with the privacy policy (fake data, local storage, auto-delete after 7 days post-decision / 30 days idle).
Time a full run per case; target < 60 s. Fix the slowest step.
```
