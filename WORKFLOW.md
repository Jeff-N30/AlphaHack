# VisaRef workflow (what actually runs)

**Product:** Gloria desk for France Schengen short-stay pre-check.  
**Rule:** Llama extracts fields; **Python rules** decide PASS/FAIL; Gloria confirms.

```text
Email / seed / upload
  → store under data/applications/<id>/
  → OCR + MRZ + Llama extract (Ollama llama3.2)
  → rules engine (checklists/*.yaml)
  → AuditReport + optional send-back DRAFT
  → Gloria Approve / Send back (confirm token + audit_log)
```

## Commands that matter

| Command | What |
|---|---|
| Desk seed / `POST /demo/seed-case/{id}` | Fake case → extract → rules → queue |
| `POST /applications/{id}/run` | Upload path: same full audit → queue |
| `POST /email/inbox/read` | IMAP VISA + Llama-triaged → queue |
| `DEMO_OFFLINE=1` | Fixture extract (no Ollama); seed uses case.yaml facts |
| `pytest` in `backend/` | Rules + extract + lock tests |
| `make seed-cases && make docs` | Regenerate eval fake PDFs |

## Not in this product
- Gemini / Claude cloud LLMs  
- WhatsApp / Twilio  
- Auto TLS upload  
- Old HTML `/demo` page (Gloria desk replaces it)
