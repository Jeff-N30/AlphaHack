# VisaRef (AlphaHack 2026 · goatpackers)

Gloria’s desk: pre-check France Schengen short-stay files.  
**AI extracts → code decides PASS/FAIL → Gloria Approve / Send back.**  
Never: Gemini, WhatsApp, or TLS upload — Gloria takes the file to TLS herself.

## What matters

| Path | What |
|---|---|
| `frontend/` | Gloria desk (Next.js) |
| `backend/app/` | API, Llama extract, rules, lock, email |
| `checklists/fr-schengen-short-stay.yaml` | France rules (code, not AI) |
| `eval/cases/` | Fake applicants for seed + tests |
| `.env` | Secrets (from `.env.example`) — not in git |
| `data/` | Local SQLite metadata database, runtime apps + inbox (gitignored) |

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e backend/[dev]
brew install ollama tesseract && ollama pull llama3.2 && ollama serve
cp .env.example .env   # EXTRACT_PROVIDER=ollama, DEMO_OFFLINE=0

uvicorn app.main:app --reload --app-dir backend --port 8000
# other terminal:
cd frontend && pnpm install && pnpm dev   # → http://localhost:3000
```

On Windows, after the virtual environment and frontend dependencies are installed,
double-click `start_visaref.bat` in the repository root. It opens the backend and
the UI in separate terminal windows:

- Backend: `http://127.0.0.1:8000`
- UI: `http://localhost:3000`

### Desk
1. **Seed complete case** → Approve  
2. **Seed bank failure** → Send back (draft shown)  
3. **Upload** → drop Jeff’s PDF pack → Run audit → queue  
4. **Read inbox** → VISA / Llama-triaged → queue  

Approve / Send back use a one-time confirm token + audit log. Docs open in-panel.

Outbound email uses Gmail SMTP only after Gloria clicks Send or Approve. Set
`EMAIL_SMTP_USER=jeffnader30@gmail.com` and use a Gmail App Password in
`EMAIL_IMAP_PASSWORD`; the address entered in the desk is the applicant
recipient. The SMTP account is never treated as the applicant; for inbox
applications, the applicant recipient comes from the incoming message `From`
address.

The desk has a compact MVP lock screen that checks `OFFICER_PIN` via
`POST /auth/officer` (empty PIN in `.env` accepts any value for local demo).
An unlocked browser session expires after four hours — this is a UI gate only;
Approve / Send still need one-time confirm tokens. The local database remains
regular SQLite.

After an approved case, an officer can explicitly `POST
/applications/{id}/redact` with `{"confirm": true}`. This removes uploaded
documents, extraction reports, email details, and detailed database rows while
retaining the application ID, checklist, dates, status, outcome, and audit
record.

## Pipeline

```text
PDF / passport image
  → OCR or PDF text
  → Llama fills Extraction JSON (never PASS/FAIL)
  → Python rules → AuditReport
  → Gloria confirms (lock)
```

## Product rules
1. AI extracts fields only — never PASS/FAIL  
2. Passport identity from MRZ checksums  
3. Gloria clicks Approve / Send back  
4. No TLS upload from VisaRef  
