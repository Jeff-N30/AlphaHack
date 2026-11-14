# VisaRef: accounts and keys

Copy `.env.example` to `.env`. **Never commit `.env`** (add it to `.gitignore` before the first commit).

## Required (for the core demo)
| # | Service | Env var(s) | Where to get it | Free tier / billing notes |
|---|---|---|---|---|
| 1 | **Google Gemini API** (extraction) | `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → Create API key | AI Studio has a free tier for Flash models, but free-tier data is "used to improve our products" ([pricing page](https://ai.google.dev/gemini-api/docs/pricing)): **fake data only.** Free tier rate limits are low; enable billing on the linked Google Cloud project for the eval runs. A Gemini Pro *app* subscription does **not** include API credits. Gemini 3.1 Pro Preview has no free tier. |
| 2 | **Anthropic Claude API** (drafting / alt extraction) | `ANTHROPIC_API_KEY` | [platform.claude.com](https://platform.claude.com) → sign up → Billing (add credits) → API keys | Pay-as-you-go credits, separate from a claude.ai subscription. $5–10 of credit is far more than the hackathon needs (≈ $0.02 per draft). |
| 3 | **Cursor** | – | You have it | Use Agent mode; `.cursor/rules/visaref.mdc` loads automatically |

You can run the whole thing on **one key**: set `DRAFT_PROVIDER=gemini` and `DRAFT_MODEL=gemini-3.8-flash`.

## App secrets you generate yourself
| Env var | How |
|---|---|
| `OFFICER_PIN` | Pick a 6-digit PIN for Gloria's demo login (this is the lock) |
| `SESSION_SECRET` | `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `FILE_ENCRYPTION_KEY` (optional) | `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |

## Optional
| Service | Env var(s) | Where | Notes |
|---|---|---|---|
| WhatsApp Cloud API (Meta) | `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN` | [developers.facebook.com](https://developers.facebook.com) → My Apps → Create app → add WhatsApp product → API setup (test number + temporary token) | Webhooks need a public HTTPS URL (use `ngrok` / `cloudflared`). Business-initiated messages need approved templates. Check Meta's current pricing page before going live. **Skip for judging**, since the "Copy message" channel works. |
| Twilio WhatsApp sandbox | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` | [console.twilio.com](https://console.twilio.com) → Messaging → Try it out → WhatsApp | Quicker than Meta for a demo; each tester joins the sandbox with a code |
| Email | `SMTP_*` (or Gmail API OAuth) | Your provider | Intake via IMAP polling; sending goes through the lock like WhatsApp |
| Langfuse | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | [cloud.langfuse.com](https://cloud.langfuse.com) → project → API keys | Free cloud tier exists (check their pricing page); the built-in `CostLine` table is enough |
| Supabase (only if hosting) | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | [supabase.com](https://supabase.com) | Not needed: SQLite is the default |
| ngrok | `NGROK_AUTHTOKEN` | [dashboard.ngrok.com](https://dashboard.ngrok.com) | Only for WhatsApp webhooks |

## System tools
- `tesseract-ocr` for passporteye: `sudo apt install tesseract-ocr` or `brew install tesseract`. On Windows, use the UB-Mannheim installer and add it to PATH.
- Python 3.12+, Node 20+ (Next.js 16), `uv` (optional), `pnpm` (optional).

## .env.example
See the `.env.example` file in this folder (all variables, with comments and current prices for cost logging).
