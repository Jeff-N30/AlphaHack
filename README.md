# Vera  
**AlphaHack 2026 · goatpackers**

*Vera works the file. Gloria makes the call.*  
*Boring PDF grind → automated. AI bill → $0 (local Ollama).*

Gloria’s visa desk pre-checks France Schengen short-stay packs.  
**Llama 3.2 extracts → Python rules decide PASS/FAIL → Gloria Approve / Send back.**  
Never: cloud Gemini/Claude, WhatsApp, or TLS upload — Gloria walks the file into TLScontact herself.

**Judges:** product narrative → [`REPORT.md`](REPORT.md) · pipeline sketch → [`WORKFLOW.md`](WORKFLOW.md)

---

## Repository structure

```text
visaref-spec/                    # repo folder name (product = Vera)
├── REPORT.md                    # judge report (problem, Llama, edges, $0)
├── WORKFLOW.md                  # what actually runs
├── README.md                    # this file
├── Makefile                     # seed / docs helpers
├── .env.example                 # copy → .env (never commit .env)
├── start_visaref.bat            # Windows: backend + UI
│
├── frontend/                    # Vera desk (Next.js App Router)
│   ├── app/                     # routes
│   ├── components/visaref/      # queue, audit, PIN gate, lock UI
│   └── public/                  # Vera branding assets
│
├── backend/
│   ├── app/
│   │   ├── extract/             # Llama only (classify, OCR path, schemas)
│   │   ├── rules/checks/        # pure PASS/FAIL functions (no LLM)
│   │   ├── drafts/              # send-back / ready draft text
│   │   ├── lock/                # ONLY place that can Approve / Send
│   │   ├── outbound/            # SMTP — imported by lock only
│   │   ├── ingest/              # IMAP / email → queue
│   │   ├── storage/             # files + SQLite
│   │   └── trace/               # execution graph for the desk
│   └── tests/                   # rules, MRZ, lock AST scan, cases
│
├── checklists/
│   └── fr-schengen-short-stay.yaml   # destination law-as-params
├── schemas/
│   └── models.py                # shared Pydantic shapes
│
├── eval/
│   ├── cases/                   # ~32 synthetic cases (case.yaml + expected)
│   ├── score.py / extract_eval.py
│   └── README.md
│
├── data/                        # gitignored runtime (apps, DB, inbox)
│   └── edge_cases/              # TRACKED live demo swaps (EDGE 01–03)
│
└── tools/                       # fake docs, Jeff pack, edge seed helpers
```

| Layer | Job |
|---|---|
| **Llama 3.2 (Ollama)** | Read pages → typed fields + drafts. Never PASS/FAIL. |
| **Code** | Checklist rules, MRZ ICAO, dates, money, name match. |
| **Gloria** | Human lock: look-items, Approve / Send back, TLS. |

---

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e "backend/[dev]"
brew install ollama tesseract && ollama pull llama3.2 && ollama serve
cp .env.example .env   # EXTRACT_PROVIDER=ollama, set OFFICER_PIN

uvicorn app.main:app --reload --app-dir backend --port 8000
# other terminal:
cd frontend && pnpm install && pnpm dev   # → http://localhost:3000
```

Windows: after venv + frontend deps, double-click `start_visaref.bat`.

- Backend: `http://127.0.0.1:8000`  
- UI: `http://localhost:3000`  
- Officer PIN: set `OFFICER_PIN` in `.env` (empty PIN accepts any value for local demo only)

### Desk demo paths
1. **Seed complete case** → Approve  
2. **Seed bank failure** → Send back (draft shown)  
3. **Upload** → drop document pack → Run audit → queue  
4. **Read inbox** → subject contains `VISA` → queue  
5. **Edge demos** → `python tools/run_edge_case.py --list` then e.g. `edge01_mrz_checksum`

Approve / Send back require a **one-time confirm token** + audit log. Docs open in-panel.

Outbound email uses Gmail SMTP only after Gloria clicks. Set IMAP/SMTP in `.env` from `.env.example`. The desk address field is the **applicant recipient** — never the agency SMTP account.

After an approved case, **Mark done & delete data** calls `POST /applications/{id}/complete` and strips sensitive files while keeping outcome audit.

---

## Pipeline

```text
Email / seed / upload
  → classify + OCR (scans)
  → Llama 3.2 → typed Extraction JSON (never PASS/FAIL)
  → MRZ tool (ICAO check digits)
  → Python rules (checklist YAML) → AuditReport + DRAFT
  → Gloria lock (confirm token) → SMTP if she confirms
```

## Product rules
1. AI extracts fields only — never PASS/FAIL  
2. Passport identity from MRZ checksums  
3. Gloria clicks Approve / Send back  
4. No TLS upload from Vera  
5. Local Ollama only — **$0** cloud LLM bill  

## Tests (safe smoke)

```bash
cd backend && pytest -q
# rules-only eval (no LLM):
pytest tests/test_cases.py tests/test_mrz.py tests/test_lock.py -q
```
