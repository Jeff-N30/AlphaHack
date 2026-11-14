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

### Desk
1. **Seed complete case** → Approve  
2. **Seed bank failure** → Send back (draft shown)  
3. **Upload** → drop Jeff’s PDF pack → Run audit → queue  
4. **Read inbox** → VISA / Llama-triaged → queue  

Approve / Send back use a one-time confirm token + audit log. Docs open in-panel.

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
