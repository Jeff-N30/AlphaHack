# VisaRef: AI agent workflow

**Product:** automated visa-file audit agent for Gloria (travel-agency officer).  
**Demo:** France Schengen short-stay · fake documents only.  
**Rule:** Llama orchestrates and explains; **code tools** decide PASS/FAIL; Gloria confirms send.

### Built so far
- Mock docs: `make seed-cases && make docs` → `eval/cases/*/docs/`
- Names/dates helpers, preview (PDF text / OCR), keyword classify, storage, upload API
- `POST /applications` → `POST /applications/{id}/run` (preview + classify + MRZ)
- `POST /demo/seed-case/case01_complete` for one-click demo
- **Rules engine:** all `check:` validators in `fr-schengen-short-stay.yaml` + `tests/test_cases.py` (32 cases)
- **Not yet:** LLM field extract from images, draft message, Gloria lock UI

---

## What kind of AI agent this is

```text
┌─────────────────────────────────────────────────────────┐
│  AGENT BRAIN = Ollama llama3.2                          │
│  - Is this email visa-related?                          │
│  - What document type is this file? (from text)         │
│  - Draft follow-up message / explain to Gloria          │
│  - Choose next tool                                     │
└─────────────┬───────────────────────────────────────────┘
              │ calls tools
              ▼
┌─────────────────────────────────────────────────────────┐
│  TOOLS (deterministic code)                             │
│  - IMAP fetch / upload / store                          │
│  - Safety allowlist (pdf/png/jpg only)                  │
│  - read_preview (PDF text or OCR)                       │
│  - extract_passport_mrz (checksums)                     │
│  - extract_* parsers (bank, hotel, flight, …)           │
│  - run_checklist_rules (YAML → PASS/FAIL/NEEDS_HUMAN)   │
│  - send_draft (lock: session + one-time token)          │
└─────────────────────────────────────────────────────────┘
```

Llama is **not** trained/fine-tuned. Prompts + tools only.  
No vision model required on 8GB Mac: **OCR/PDF text → llama3.2**.

---

## End-to-end workflow (all steps)

### 0. Always on
Agent polls inbox (IMAP) on an interval **or** accepts web upload (same pipeline after store).

### 1. Intake
1. New email (or upload) arrives.  
2. **Llama:** `is_visa_related?` from subject/body/attachment names.  
3. If **no** → ignore / label not-visa.  
4. If **yes** → download attachments.

### 2. Store
1. Create `application_id`.  
2. Save under `data/applications/<id>/`.  
3. Index in SQLite (from, subject, time, file list).  
4. Optional Fernet encrypt at rest; retention purge later (7 / 30 days).

### 3. Per-file safety gate (code — not Llama)
| Check | Action |
|---|---|
| Extension in `{.pdf,.png,.jpg,.jpeg}` | allow |
| Else (`.exe`, `.zip`, …) | **reject** + flag |
| Size over limit | **reject** + flag |
| Unreadable/corrupt | **NEEDS_HUMAN** |

### 4. Get text preview (code — all supported types)
| Input | Method |
|---|---|
| Digital PDF | `pdfplumber` / PyMuPDF text layer |
| Scanned PDF (little/no text) | render pages → **Tesseract OCR** |
| PNG / JPG / JPEG | **Tesseract OCR** |
| Empty / garbage text | **NEEDS_HUMAN** (do not guess type) |

Filename is a **hint only**, never trusted alone.

### 5. Classify document type (Llama)
Preview text → Llama returns JSON only, e.g.:
```json
{"doc_type": "passport", "confidence": 0.91}
```
Allowed types:  
`passport | bank_statement | hotel_booking | flight_booking | travel_insurance | employment_letter | payslip | application_form | photo | cnss_certificate | family_register | travel_plan | unknown`

If `unknown` or confidence **&lt; 0.7** → **NEEDS_HUMAN**.

### 6. Route to the matching extract script (code)
```text
doc_type → DOC_TOOLS[doc_type](path)
```

| `doc_type` | Tool |
|---|---|
| `passport` | `extract/mrz.py` (passporteye + ICAO checksums) |
| `bank_statement` | bank PDF/OCR parser |
| `hotel_booking` | hotel parser |
| `flight_booking` | flight parser |
| `travel_insurance` | insurance parser |
| `employment_letter` | letter parser (± Llama field-fill only if parser fails later) |
| others | dedicated light extractors / presence checks |

**Passport special case:** MRZ checksum fail → **NEEDS_HUMAN** (never invent digits).

### 7. Build Facts
Merge all extractions into one `Facts` object (names, dates, balances, MRZ identity, …).

### 8. Run checklist (code — never Llama)
Load `checklists/fr-schengen-short-stay.yaml` and run pure check functions:
- required docs present / missing  
- passport validity  
- **name match** across docs (`rapidfuzz`)  
- trip dates align (flight/hotel/insurance)  
- funds sufficient (bank + stay days + FX from YAML)  
- …

Each result: `PASS` | `FAIL` | `NEEDS_HUMAN` + **evidence**.

### 9. Outcome
- All critical PASS → ready for Gloria approval  
- FAIL with `on_fail=request` → include in applicant message  
- Any doubt / low confidence / tool failure → **NEEDS_HUMAN**

### 10. Draft reply (Llama wording OK)
Code builds the fact list (missing docs + FAIL messages).  
Llama turns that into EN / FR / AR-LB text.  
Status stays **DRAFT** (pipeline cannot send).

### 11. Human lock (Gloria)
Send / Approve only via lock endpoints (session + one-time token).  
Production: human-in-the-loop. Demo may show one-click confirm.

---

## Same pipeline for every eval case

| Case | What the agent surfaces |
|---|---|
| case01 complete | clean PASS path |
| case02 missing insurance | missing-doc request |
| case03 passport validity | expiry rule FAIL / human |
| case04 name mismatch | name NEEDS_HUMAN |
| case05 wrong dates | date FAIL + draft |

Stack does not change per case — only inputs and rule outcomes.

---

## Escalation policy (always)

```text
unsure OR low confidence OR checksum fail OR extract fail
OR unsafe file OR conflicting fields
  → NEEDS_HUMAN
  → show evidence
  → do NOT invent PASS
```

---

## Stack map

| Layer | Choice |
|---|---|
| Agent brain | Ollama **`llama3.2`** (~2GB; fits 8GB Mac) |
| Vision LLM | **Not required** (OCR → text → Llama) |
| API | FastAPI on localhost |
| DB / files | SQLite + `data/applications/<id>/` |
| Passport | passporteye + Tesseract + `mrz` |
| PDF/images | PyMuPDF, pdfplumber, Pillow, Tesseract |
| Rules | YAML checklist + Python checks |
| Names/dates | rapidfuzz + dateutil |
| UI | Next.js or Streamlit |
| Train/fine-tune | **None** |

---

## Lebanon / Arabic / France edge cases (must handle)

| Case | Agent behaviour |
|---|---|
| Digital PDF | text layer → classify → parse |
| **Image inside PDF** (scan) | no text → render → **OCR** → classify |
| PNG / JPG phone photo | **OCR** → classify |
| Wrong / lying filename | **ignore name**; classify from content |
| Unsafe type (`.exe`…) | reject |
| **Ekhraj kaid aily** missing / >6 months | DOC.PRESENT / FAM.ISSUED_WITHIN_6M |
| Ekhraj **Arabic-only**, no translation | **NEEDS_HUMAN** + ask certified translation |
| Arabic-only employer letter | **NEEDS_HUMAN** |
| Bilingual FR+AR hotel/bank | try extract; escalate if fields missing |
| Names AL/EL/الحاج, Mohamad/Mohammad | **code** normalizer + rapidfuzz |
| Passport identity | **MRZ only** (Latin); Arabic visual is secondary |
| **LBP** balances | **NEEDS_HUMAN** (no LBP FX) |
| USD/EUR fresh accounts | FX from YAML |
| CNSS / payslips / travel plan | required when profile = employee |
| Unknown attachment | flag Gloria, don’t crash |
| Low OCR / low Llama confidence | **NEEDS_HUMAN** |

Eval folders: `case01`–`case32` (see `eval/README.md`). Seed more with `python tools/seed_eval_cases.py`.

---

## One-line pitch

> VisaRef is a **Llama tool-calling agent** that ingests visa emails, classifies each attachment from content, runs deterministic extract + checklist tools, drafts the follow-up, and asks the officer only to confirm send.
