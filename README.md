# VisaRef: AI visa application audit officer (AlphaHack 2026 · team goatpackers)

> Gloria, a visa officer at a Lebanese travel agency, spends **30–60 min per file** checking passports,
> bank statements, flights, hotels and insurance before each TLScontact appointment. VisaRef does the
> checking in about a minute, shows evidence for every check, drafts the "please send us…" message, and **waits
> for Gloria to click** Approve or Send.

**Demo scope:** France · Schengen short-stay (type C) · tourism · employee · filed at TLScontact Beirut.
**Architecture scope:** any destination. Each one is a checklist YAML in `checklists/` and adding the UK is a new file, not new code.

## What's in this package
| File | What it's for |
|---|---|
| `BUILD.md` | Deep dive: architecture, data flow, modules, folder layout, build order with time boxes, demo script, pitch per twist, risks |
| `STACK.md` | Stack + reasoning + alternatives, model choice, **cost per application** (sourced) |
| `KEYS.md` + `.env.example` | Every account and key, where to get it, free-tier notes |
| `.cursor/rules/visaref.mdc` | Cursor project rules (always on): lock rule, "AI extracts, code decides", privacy, tests |
| `PROMPTS.md` | Extraction and drafting prompts + **12 Cursor agent prompts to paste in order** |
| `checklists/fr-schengen-short-stay.yaml` | France checklist: 31 rules, each one tagged `code` / `llm_flag` / `manual`, with source URLs |
| `schemas/models.py` | Pydantic v2 models: every document extraction, `CheckResult`, `AuditReport`, draft + lock state |
| `eval/cases/case0X_*/` | 5 fake applicants (`case.yaml`) + expected per-rule results (`expected.yaml`) |
| `eval/README.md` | Eval plan: scaling to 20 cases, pass rate, human count, nightly posting |
| `eval/score.py` | Working scorer (pass rate, rule accuracy, human count, cost) → `eval/history.csv` |
| `tools/generate_fake_docs.py` | Renders fake docs from `case.yaml`: passport PNG with **valid ICAO MRZ** (self-verified), PDFs for the rest |

## 5-minute start
```bash
# 1) put this folder at the root of your repo, open it in Cursor
python -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt
python tools/generate_fake_docs.py            # -> eval/cases/*/docs/ (MRZ self-check prints "valid")
python eval/score.py --selftest               # scorer sanity check -> 5/5
cp .env.example .env                          # add GEMINI_API_KEY + ANTHROPIC_API_KEY (see KEYS.md)
# 2) In Cursor Agent, paste PROMPTS.md -> "Cursor build sequence" prompt 1, then 2, 3...
```

### Read VISA emails (full pipeline)

Unread IMAP messages whose subject contains `VISA` are pulled, then run end-to-end:

`save attachments → OCR/classify/MRZ → Llama field extract → TLS checklist rules (code)`

Attachments land under `data/email_inbox/<uid>/`; the audit is stored on the new
application as `email_pipeline_report.json`. Manual trigger: `POST /email/inbox/read`.

1. Gmail: enable 2-Step Verification, then create a Google **App Password**.
2. Copy `.env.example` → `.env` and set `EMAIL_IMAP_USER` / `EMAIL_IMAP_PASSWORD`.
3. Start the backend (`uvicorn app.main:app --reload --app-dir backend`).
4. Watcher polls every `EMAIL_POLL_INTERVAL_S` (default 30). Console prints each
   processed uid + checklist `outcome`.

## The four rules that win this
1. **AI extracts, code decides.** LLMs turn pixels into JSON. Python decides PASS/FAIL. The LLM can only *raise* a flag.
2. **MRZ checksums are the truth anchor.** Passport data is re-derived from the MRZ and verified with ICAO check digits, so a misread digit can't slip through quietly.
3. **The lock lives in code.** The pipeline can only create `DRAFT`s. Only the `/send` and `/approve` endpoints, with Gloria's session and a one-time confirm token, can change state.
4. **Measure every night.** `eval/score.py` prints the pass rate, how many cases needed Gloria, and the cost per application. Post that line.

All test data is fake. Nothing in this package is legal or immigration advice. Gloria checks the official France-Visas personalised list for each applicant.
