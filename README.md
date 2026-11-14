# VisaRef (AlphaHack 2026 · goatpackers)

Gloria’s desk: pre-check France Schengen short-stay files.  
**AI extracts → code decides PASS/FAIL → Gloria Approve / Send back.**  
Never: Gemini, WhatsApp, or TLS upload — Gloria takes the file to TLS herself.

## Jeff: only these folders matter

| Path | What it is |
|---|---|
| `frontend/` | Gloria desk UI (Next.js) — open this in the browser |
| `backend/` | API + rules + Llama extract + email |
| `checklists/fr-schengen-short-stay.yaml` | The France rules (code, not AI) |
| `eval/cases/` | Fake applicants for demo seed |
| `.env` | Your secrets (copy from `.env.example`) — **not in git** |
| `data/` | Runtime files (gitignored) — applications + email inbox |

Ignore for now: `BUILD.md`, `PROMPTS.md`, `KEYS.md` WhatsApp stuff, empty `drafts/` / `lock/` / `outbound/`.

## Run the desk (what actually works)

```bash
# 1) Python
python3 -m venv .venv && source .venv/bin/activate
pip install -e backend/[dev]

# 2) Llama (required for live extract / email triage)
brew install ollama
ollama pull llama3.2
ollama serve

# 3) OCR for passport images / scanned PDFs
brew install tesseract

# 4) Env
cp .env.example .env
# set EXTRACT_PROVIDER=ollama, DEMO_OFFLINE=0
# optional: EMAIL_IMAP_* for Gmail

# 5) Backend
uvicorn app.main:app --reload --app-dir backend --port 8000

# 6) Frontend (other terminal)
cd frontend && pnpm install && pnpm dev
# → http://localhost:3000
```

### Demo on the desk
1. **Seed complete case** → Approve (look-items only)  
2. **Seed bank failure** → Send back (balance too low)  

### Email
- Subject contains `VISA` → full pipeline → Gloria queue  
- Empty / other subject → Llama triage → `data/email_inbox/needs_review/` (not desk yet)  

## How images / PDFs get “understood”

```text
passport.png / scanned PDF
    → Tesseract OCR (or PDF text layer)
    → Llama fills fields (form / flight / insurance)
    → Python rules PASS/FAIL
```

If Tesseract or Ollama is missing, images look like “nothing works.”

## Product rules
1. AI extracts JSON only — never PASS/FAIL  
2. Passport identity from MRZ checksums  
3. Gloria clicks Approve / Send back  
4. No TLS upload from VisaRef  
