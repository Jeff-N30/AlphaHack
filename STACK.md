# VisaRef: stack

**Priority order:** correct → explainable → demo-able → cheap. Everything here installs in minutes, and nothing needs cloud infrastructure.

## 1. Summary
| Layer | Pick | Why | Alternative |
|---|---|---|---|
| Frontend | **Next.js 16** (App Router) + TypeScript + **Tailwind v4** + **shadcn/ui** | Polished review screen fast; shadcn gives tables, badges, dialogs (confirm modal = lock UX) | **Streamlit** if behind schedule (whole UI in ~150 lines of Python) |
| Backend | **Python 3.12+ / FastAPI** + **Pydantic v2** | Passport/MRZ, PDF and fuzzy-matching libraries are all Python; Pydantic models = LLM JSON schema = API schema | All-TS (Next.js route handlers + Zod + Vercel AI SDK), but you lose passporteye and write MRZ parsing yourself |
| Vision extraction | **Gemini 3.8 Flash** (`gemini-3.8-flash`) with JSON schema output | Strong multimodal, cheap, free tier on AI Studio for fake-data dev | **Claude Haiku 5.5** (`claude-haiku-5-5`), roughly 7× cheaper per token; benchmark on your 5 cases. **Gemini 3.1 Pro Preview** for hard scans only |
| Drafting / reasoning text | **Claude Sonnet 5.5** (`claude-sonnet-5-5`) | Natural FR/EN/Lebanese-Arabic phrasing; only phrases facts code gives it | Same Gemini model (one key fewer) |
| Passport ground truth | **passporteye** (MRZ OCR, needs `tesseract`) + **mrz** (TD3 parse and check digits) | Deterministic and checksum-verified; the answer to the judges' "main technical risk" | LLM-transcribed MRZ lines, always re-validated by `mrz` |
| PDF / images | **PyMuPDF** (render pages), **pdfplumber** (text layer of digital PDFs), **Pillow** (EXIF, resize, crops) | Digital PDFs often have a text layer, so cheaper and more exact | `pdf2image` + poppler |
| Names | **rapidfuzz** `token_sort_ratio` + own normalizer (AL/EL, titles, `/`) | Fast, deterministic thresholds | `jellyfish` (phonetic), optional |
| Dates | `python-dateutil` (`relativedelta` for "+3 months") | Correct month arithmetic | `pendulum` |
| DB | **SQLite** via **SQLModel** | Zero setup, one file, easy to delete | Supabase Postgres + Storage (only if you need hosting/auth) |
| Files | Local `data/applications/<id>/`, optional **Fernet** encryption, retention job (APScheduler) | Simple privacy story: stays on the agency machine, auto-deleted | Supabase Storage with lifecycle rules |
| Intake (optional) | **WhatsApp Cloud API** (Meta) or **Twilio WhatsApp sandbox**; email via IMAP/Gmail API | Matches the real trigger | Web upload only (fine for judging) |
| Observability / cost | Own `CostLine` table (tokens × price from `.env`) | Cost slide writes itself | **Langfuse** (traces + cost dashboards) |
| Tests / eval | **pytest** + `eval/score.py` + `eval/history.csv` | Nightly pass-rate curve | promptfoo for prompt A/B |
| Dev | **Cursor** (Agent + `.cursor/rules`), `uv` for Python deps, `pnpm` for Next.js | Fast | pip / npm |

**Versions checked 2026-11-14:** next 16.4.6, tailwindcss 4.3.5, fastapi 0.162.7, pydantic 2.14.3, google-genai 3.3.0, anthropic 2.8.0, PassportEye 2.2.2, mrz 0.6.2, RapidFuzz 3.14.6, PyMuPDF 2.1, pdfplumber 0.11.10, reportlab 5.1.0, langfuse 5.2.0 (npm/PyPI registries).
Note: the brief said "Next.js 15", but the current major version is **16**. Use 16.

## 2. Model choice: verified names and prices (USD per 1M tokens)
| Model (API id) | Input | Output (incl. thinking) | Use | Source |
|---|---|---|---|---|
| Gemini 3.8 Flash `gemini-3.8-flash` | $0.75 through 2026-12-31, then $1.50 | $3.75, then $7.50 | classify + extract | [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| Gemini 3.1 Flash-Lite `gemini-3.1-flash-lite` | $0.25 | $1.50 | cheap page classifier (optional) | same |
| Gemini 3.1 Pro Preview `gemini-3.1-pro-preview` | $2.00 (≤200k) | $12.00 | fallback for bad scans; **no free tier** | same |
| Claude Sonnet 5.5 `claude-sonnet-5-5` | $2.00 | $10.00 | drafting | [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), [models overview](https://platform.claude.com/docs/en/models/overview) |
| Claude Haiku 5.5 `claude-haiku-5-5` | $0.10 (≤100k prompt) | $0.50 | cheap extraction alternative | same |

- The Gemini free tier on AI Studio is "Free of charge", but the pricing page marks free-tier data as **"Used to improve our products: Yes"** (paid tier: No). That's fine for fake documents. **Use the paid tier for anything real.**
- A **Gemini Pro** (Google AI Pro) subscription is a consumer app plan. API usage is billed separately through AI Studio / Cloud billing. The same goes for Claude: a claude.ai subscription ≠ API credits.
- Both SDKs support structured output: Gemini via `response_schema` / JSON mode, Claude via tool-use or JSON output. Always validate with Pydantic and re-ask once on failure.

## 3. Key libraries and how they're used
```text
backend/pyproject.toml (deps)
fastapi uvicorn[standard] pydantic sqlmodel python-multipart
google-genai anthropic httpx tenacity
pymupdf pdfplumber pillow
passporteye mrz            # + system: apt install tesseract-ocr  /  brew install tesseract
rapidfuzz python-dateutil pyyaml
cryptography apscheduler
pytest pytest-asyncio
```
```text
frontend: pnpm create next-app@latest frontend --ts --tailwind --app
          pnpm dlx shadcn@latest init && pnpm dlx shadcn@latest add table badge card dialog button textarea tabs tooltip sonner
          pnpm add @tanstack/react-query recharts zod
```

### MRZ: the trick for the main technical risk
```python
from passporteye import read_mrz                      # OCR path (tesseract)
from mrz.checker.td3 import TD3CodeChecker           # checksum path

def mrz_from_image(path, llm_lines: list[str] | None):
    for source, text in (("passporteye", _pe(path)), ("llm", "\n".join(llm_lines or []))):
        if text and (chk := TD3CodeChecker(text)):     # truthy only if ALL check digits valid
            return parse(text, source)                # fields from MRZ = ground truth
    return None                                       # -> PP.MRZ_CHECKSUM NEEDS_HUMAN
```
The fake passports generated by `tools/generate_fake_docs.py` already carry valid MRZs (self-verified with `mrz`). For better OCR, drop an OCR-B font file next to the generator.

## 4. Cost per application (estimate, then measure)
Assumptions (replace with the real `usage_metadata` from the cost log after your first run):
a file is ~13 documents / ~15 page images; ~1,100 input tokens per page image (estimate, since Gemini lets you tune `media_resolution`); ~1,200 prompt+schema tokens per extraction call; ~1,200 output tokens per extraction including thinking.

| Step | Model | Input tok | Output tok | Cost |
|---|---|---|---|---|
| Classify 15 pages | gemini-3.8-flash | 21,000 | 1,500 | $0.016 + $0.006 = **$0.021** |
| Extract 13 docs | gemini-3.8-flash | 32,000 | 15,600 | $0.024 + $0.059 = **$0.083** |
| MRZ + rules | local code | – | – | $0.000 |
| Draft message | claude-sonnet-5-5 | 4,000 | 1,500 | $0.008 + $0.015 = **$0.023** |
| **Total** | | | | **≈ $0.13 / application** |

- From 2027-01-01, Gemini 3.8 Flash prices double, so the total becomes ≈ **$0.23**.
- All-Haiku 5.5 variant (if accuracy holds on your eval): ≈ **$0.015**. (Claude counts image tokens differently, so measure it.)
- **Human baseline:** 30–60 min per file (from Gloria). At an *assumed* $5/h, that's $2.50–$5.00 per file (≈ $3.75 at 45 min). **Replace with Gloria's real salary and minutes.** Gloria still spends ~3–5 min reviewing, which is the honest number to quote.
- Show it as: *"$0.13 of AI + 4 min of Gloria instead of 45 min of Gloria."*

## 5. Privacy and storage (say this on stage)
- Hackathon: **fake documents only** (generated, watermarked "SPECIMEN / FAKE").
- Files live only in `data/applications/<id>/` on the agency machine and can be Fernet-encrypted at rest. They're **auto-deleted 7 days after Approve / Send back, or after 30 days idle** (both settable in `.env`). Gloria can also delete them right away. The audit log keeps rule results and hashes, not images.
- Use the paid LLM API tiers for real data. Send pages to the LLM only, never to logs. Redact passport numbers in app logs.

## 6. All-TypeScript alternative (if the team is JS-only)
Next.js 16 route handlers + Zod schemas + Vercel AI SDK (`generateObject` with Gemini/Claude) + `better-sqlite3`/Drizzle + `pdfjs-dist`/`sharp` + `fastest-levenshtein`. MRZ: write the 7-3-1 checksum yourself (≈ 30 lines, copy the logic in `tools/generate_fake_docs.py::check_digit`) and get the MRZ lines from the LLM. You lose passporteye's independent OCR path, so the checksum becomes your only guard.
