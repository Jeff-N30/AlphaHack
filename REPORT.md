# Vera  
**AlphaHack 2026 · goatpackers**  
*Vera works the file. Gloria makes the call.*  
*Boring PDF grind → automated. AI bill → $0.*

---

## 1. The problem

### 1.1 What a “visa file” actually is

In Lebanon, a France Schengen short-stay application is not one form. It is a **stack of interdependent documents** that must agree with each other and with EU / France-Visas / TLScontact Beirut practice:

- Passport bio page (MRZ + visual zone)  
- France-Visas application printout (signed)  
- Round-trip flight reservation  
- Hotel (or equivalent accommodation) covering the stay  
- Schengen travel medical insurance (≥ **EUR 30,000**, territory, dates)  
- Personal bank statement (typically **six months**, stamped, recent)  
- Employment letter + payslip + CNSS (for employees)  
- Family register extract (*ekhraj kaid aily*), recent enough  
- ID photos + tourism travel plan  

If **one** piece is wrong — insurance in USD, bank too old, hotel ending a day early, passenger name ≠ passport, trip filed too late — the file is not “almost fine.” It is a **failed appointment**, a stressed client, and an agency that looks incompetent.

### 1.2 The boring, repetitive PDF grind

Gloria runs the visa desk. She is the manager — the person clients trust, the person who will eventually walk a folder into TLScontact. Around her, employees drown in **the same boring PDF loop**, file after file, day after day.

It is not creative work. It is not “advisory.” It is **repetitive document labor**:

1. Open passport. Squint at MRZ. Hope the scan is readable.  
2. Open the form. Compare surname spelling character by character.  
3. Open flight. Check BEY→CDG dates against hotel and insurance.  
4. Open bank. Count months. Check issue date. Guess if the stamp “counts.”  
5. Open insurance. Is EUR 30k printed, or is it USD dressed up as “enough”?  
6. Flip back to the passport. Flip to the hotel. Flip to the bank again.  
7. Write an email listing what is missing — from memory.  
8. Client sends version 2 → **repeat the entire stack**.  

Same clicks. Same fields. Same checklist. **Boring. Repetitive. Easy to mess up when you are tired.**

**Configured reality in our product baseline:** about **45 minutes of human time per messy file**. That is how long careful cross-checking takes when a person is the OCR engine, the rules engine, and the email drafter at once.

At ten files a day, that is **seven hours** of PDF archaeology — before Gloria has done the judgment work that only a manager should do.

### 1.3 Who pays for the mistakes

| Failure | Who hurts |
|---|---|
| Incomplete pack discovered at TLS | Client loses slot; agency looks unprepared |
| Name mismatch across insurance / flight | Refusal risk; emergency rebooking |
| Stale bank or family register | Same — caught late = expensive |
| Junior staff miss a rule Gloria knows by heart | Manager rework; team demoralization |
| “ChatGPT said you’re fine” then TLS says no | Liability + destroyed trust |

The industry does **not** need a model that predicts embassy mood. It needs a system that **never lies about what is on the page**, **never invents FX**, and **never sends the client a message without a human**.

### 1.4 The human cost for employees

**Boring repetitive PDF work burns people out.** Smart juniors become tired page-flippers. They did not join a travel agency to re-read closing balances and MRZ lines a hundred times a week. Gloria, as manager, cannot coach, sell, or handle real exceptions because she is trapped in the same stack.

Meanwhile the industry’s default “AI” answer is: pay a cloud LLM vendor per token, leak passport scans to a third party, and hope the model does not invent a PASS.

**The problem, in one line:**  
visa desks drown in boring, checkable PDF work that humans should not grind by hand — while the work that *requires* a human (judgment, client trust, TLS) gets starved — and paying for cloud AI makes that worse, not cheaper.

---

## 2. The answer: Vera + Gloria

### 2.1 Roles

| Role | Who | Responsibility |
|---|---|---|
| **Vera** | AI agent — **the product** | Ingest, read, extract, run rules, draft, queue |
| **Gloria** | Human manager — desk lead / mom of the operation | **Mandatory human intervention**: look-items, Approve / Send back, TLS |

Vera prepares. Gloria decides. That split is the entire product philosophy.

### 2.2 What Vera does (AI agent + orchestration)

Vera is not a chatbot pasted on a folder. She is an **orchestrated agent** whose eyes are **local Llama 3.2 (Ollama)** and whose judgment is **code + Gloria**.

1. Pulls visa mail (or upload / seed packs)  
2. **Orchestrates** the pack: classify pages → OCR scans → call Llama per document type  
3. Llama returns **typed fields only** (names, dates, amounts, coverages) — never PASS/FAIL  
4. Passport identity: **MRZ + ICAO 9303 check digits** (tooling, not model vibes)  
5. Python rules run the France/TLS checklist on those facts  
6. Builds an audit + drafts ready / send-back email text (Llama helps draft; Gloria owns Send)  
7. Stops. She does **not** send. She does **not** approve. She does **not** upload to TLS.

### 2.3 What Gloria does (human intervention)

- Opens Vera’s queue — not a blank Downloads folder  
- Reviews **must-fix** failures and **look with your eye** items (✓ / ✕)  
- Confirms low-confidence extractions (e.g. passport issue date) and photo quality  
- Clicks **Approve & email** or **Send email** under a **one-time confirm token** (120s, replay → 409)  
- Every action lands in an **audit log** (officer, action, timestamp, body sha256)  
- Takes the approved physical/digital pack to TLScontact herself  

If Gloria does not click, nothing leaves the agency. That is intentional.

### 2.4 Time saved — how Vera helps employees

| Before | After |
|---|---|
| ~45 min / file of **boring PDF flipping** | Vera digests in minutes; Gloria spends ~**2–5 min** on look-items + decision |
| Juniors exhausted on repetitive reads | Staff work Vera’s queue: clear fails vs look-items |
| Gloria buried in every page | Gloria intervenes where Vera escalates |
| Send-backs written from scratch | Vera drafts; Gloria edits and sends |
| Errors found at TLS | Errors found **before** the appointment |
| Pay cloud AI per token (or pay nothing and stay manual) | **$0** to run Vera’s brain — free local Ollama |

**Order of magnitude:** for files Vera can fully score, human minutes drop on the order of **~80–90%**. Hard edge cases still escalate — that is a feature. Employees keep their judgment for what matters; Vera eats the grind.

**What the team feels**

- Less PDF archaeology  
- Fewer angry clients from avoidable mistakes  
- Clearer training (“this rule failed because…”)  
- Gloria remains the authority — Vera is the tireless junior who never hits Send alone  

---

## 3. Product thesis (non-negotiables)

1. **AI extracts. Code decides. Gloria locks.**  
   The LLM never outputs PASS/FAIL. Low confidence → NEEDS_HUMAN.  
2. **MRZ-first identity.**  
   Failed checksum → flag Gloria; never silently trust LLM-read names.  
3. **No unsupervised outbound.**  
   No WhatsApp bot. No auto-TLS. Email only after Gloria’s confirm token.  
4. **No LBP fantasy FX.**  
   Unknown currency or destination → NEEDS_HUMAN. Reference currency is checklist EUR.  
5. **Destination logic lives in YAML.**  
   France today; Spain/Italy tomorrow without rewriting the agent brain.

---

## 4. How Llama orchestrates the file

Vera’s agent loop is **orchestration around Llama 3.2** — not “ask the model if the visa is fine.”

**Orchestration graph**

1. **Intake** — email / upload / seed lands as a pack of pages  
2. **Triage** — route VISA mail; drop empty / unrelated noise  
3. **Classify** — keywords first; **Llama** when the page is ambiguous (wrong name, bilingual, scan)  
4. **Prepare pages** — text PDFs parsed; image-only / phone scans rendered + OCR’d so Llama sees usable input  
5. **Extract (Llama 3.2, local Ollama)** — one typed call per document family: form, passport visual zone, flight, hotel, insurance, bank, employment, payslip, family register…  
6. **MRZ tool** — machine-readable zone decoded with ICAO check digits (separate from Llama)  
7. **Facts assembly** — validated schemas + confidence scores become the only inputs to rules  
8. **Rules engine (code)** — checklist PASS / FAIL / NEEDS_HUMAN with evidence  
9. **Draft (Llama-assisted text)** — ready or send-back wording → queue as DRAFT only  
10. **Gloria lock** — look-items ✓/✕ → Approve & email or Send email (confirm token + audit log)

**Why this orchestration wins**

| Layer | Job | Forbidden |
|---|---|---|
| **Llama 3.2** | See the page. Pull fields. Flag “looks odd.” Draft language. | Decide compliance. Invent FX. Hit Send. |
| **Code** | Apply France/TLS law-as-params. Date math. Money math. Name match. | Call cloud APIs. Guess missing docs. |
| **Gloria** | Human intervention on every outbound action + photo / stamp judgment | Be replaced by the model |

**Not a free agent:** Llama never loops itself into Approve. Background jobs **cannot** call the lock. The desk execution graph shows judges exactly which Llama steps and which checks ran — **$0** cloud bill, local Ollama only.

---

## 5. Llama 3.2 — eyes of the agent

### 5.1 What we use Llama for

| Step | Llama’s job |
|---|---|
| **Ambiguous classify** | “Is this a bank stamp page or a payslip?” when keywords disagree |
| **Structured extract** | Typed JSON: insured name, coverage EUR, hotel checkout, closing balance, leave dates… |
| **Soft flags** | Stamp / anomaly style signals → **NEEDS_HUMAN only**, never FAIL |
| **Email draft** | Human-readable send-back / ready text from the audit (Gloria edits + confirms) |

Every Llama call hits one gateway: schema validation, retries, cost line (still **$0** locally), and a content-hash cache so the same PDF can demo offline without re-burning GPU.

### 5.2 What Llama is never allowed to do

- Output PASS / FAIL / “file is compliant”  
- Override a failed MRZ checksum with “the name looks right”  
- Invent a currency rate (especially LBP)  
- Send mail, approve a file, or upload to TLS  

**AI extracts. Code decides. Gloria locks.** That sentence is the product.

### 5.3 Code after Llama (brain)

Stay ≤ 90 days, filing window, hotel covers stay, insurance ≥ EUR 30k + territory + cover items, bank six-month window and age, funds sufficiency, large deposit flag, employment leave covers trip, payslip recency, family register age, cross-doc name match (token-sort fuzzy match with checklist thresholds — never the looser set-ratio that hides real mismatches).

### 5.4 Gloria (hands)

Approve, send back, flag, SMTP, TLS. Manual rules (e.g. photo quality) always wait for her eyes — Llama can only escalate those.

---

## 6. Rules & scripting (the moat)

Checklist: France Schengen short-stay (destination YAML params only).  
Cited sources (by name, not URLs): France-Visas, EU Commission supporting-docs list for Lebanon, Service-Public, TLS Beirut practice.

| Mode | Allowed outcomes |
|---|---|
| code | PASS / FAIL / NEEDS_HUMAN |
| llm_flag | PASS or NEEDS_HUMAN only |
| manual | Always NEEDS_HUMAN (not counted as “escalation panic”) |

Each check is a small pure function: facts + params + submission date → result.  
No network. No LLM. No “today’s clock” inside the rule — only the submission date on the file.  
Missing required docs → skipped rules, not invented FAILs.  
Evidence points at document / field / value / page so Gloria can open the right page.

**Eval:** ~30 synthetic cases; unit tests on every check; rules are scored on hand-built facts (no LLM) against expected outcomes so rules bugs never hide behind extraction noise.

---

## 7. Edge cases — this is where Vera actually wins

Happy-path demos are cheap. Real desks drown in **weird, overlapping, easy-to-miss failures**. Vera is built for that mess: Llama 3.2 reads the pages, orchestration + rules decide, ~30 scored cases — and a hard rule: **if she is unsure, she escalates; she never invents a PASS**.

Below: the **20 sharpest** problems we actually solve. Not slogans — failure modes that burn appointments.

### A. System intelligence (how Vera thinks under pressure)

| # | Problem | What Vera does |
|---|---|---|
| **1** | Inbox noise (empty / unrelated mail) | Triage drops junk. No fake application from a random forward. |
| **2** | Wrong filename, right document | Reads **content**, not the label. A passport misnamed as an invoice still routes as passport. |
| **3** | Junk mixed into the pack | Unknown types stay unknown. A utility bill cannot poison insurance or bank facts. |
| **4** | Phone photos & image-only scans | Render → OCR → Llama extract — same pipeline as clean text PDFs. |
| **5** | Tampered / unreadable MRZ | ICAO check digits are law. Bad checksum → Gloria. Never “the photo looks fine.” |
| **6** | Lebanese / Arabic name chaos | AL/EL particles, flipped given/family, accents — Llama pulls strings; **code** fuzzy-matches. |
| **7** | LLM says “looks OK,” math says no | Passport validity, hotel/insurance/flight windows, filing window — pure date math wins. |
| **8** | “Enough money?” vibes | Llama reads the number; engine applies balance × stay × checklist rate. |
| **9** | Weak / blurry extraction | Low confidence → needs Gloria. A shaky read can never silently become PASS. |
| **10** | AI that wants to send | Hard lock: only Gloria’s one-time confirm can Approve / Send back. |

### B. Checklist reality (what actually kills France/TLS files)

| # | Problem | What Vera does |
|---|---|---|
| **11** | Same person, different spellings across docs | Cross-doc identity check (passport ↔ insurance ↔ flight) → clear mismatch or officer compare. |
| **12** | Form typo vs passport | France-Visas printout must match the passport exactly — Vera catches the one-letter trap. |
| **13** | Itinerary dates that do not agree | Flight / hotel / insurance / form trip windows cross-checked; inconsistency → must-fix. |
| **14** | Insurance under EUR 30,000 | Threshold fail. Replace policy or Gloria decides — no “USD is probably fine.” |
| **15** | “France only” medical cover | Territory too narrow for a Schengen trip → fail / escalate. |
| **16** | Cover ends one day early | Full-stay span is computed, not eyeballed. One missing day = catch. |
| **17** | Bank statement too old or too short | Issue age + six-month window from the Lebanon EU supporting-docs practice. |
| **18** | Suspicious large recent deposit | Flagged for Gloria context — Vera does not rubber-stamp sudden inflows. |
| **19** | One-way ticket or filing window wrong | Missing return proof, or trip too soon / too far for filing rules → caught before TLS. |
| **20** | Exotic / unlisted currency | No invented FX. Unknown currency → Gloria. **Never** a fake LBP rate. |

**And we go further than these twenty:** expired / over-10-year passport, leave that ends mid-trip, ekhraj age / missing / translation, Arabic employment letters, payslip month windows, missing CNSS, bilingual hotels, incomplete packs (Jason: passport-only), stale vs coherent Jeff packs.

**Point for judges:** Llama 3.2 eats the boring PDF grind; orchestration turns it into evidence. Long tail of visa-desk failures — Gloria acts in minutes.

**Live film set:** EDGE 01–03, Jason incomplete, Jeff Dec email — same principles, real scans.

---

## 8. What Gloria sees (Vera’s desk)

- PIN gate → **Vera** desk branding  
- Queue Vera prepared: needs Gloria / approved / sent back  
- Split UI: **must fix** vs **look with your eye**  
- In-panel document preview  
- Applicant email + Vera’s draft → Gloria’s Send / Approve  
- Execution graph of the run  
- Optional redact after decision (keep outcome audit, strip sensitive docs)

---

## 9. Cost: literally $0 for the AI

This is the part that matters for a real agency.

| Bill | Vera |
|---|---|
| OpenAI / Claude / Gemini API | **$0 — we do not use them** |
| Per-file extract fee | **$0** |
| GPU cloud / inference cluster | **$0** |
| WhatsApp / Twilio / Meta | **$0 — not in the product** |
| TLS API integration | **$0 — Gloria takes the file herself** |
| What you need | A laptop + **free** local Ollama + Vera |

**You do not have to pay for anything to run the brain.** No token meter. No subscription to a model vendor. No cloud invoice when Jeff emails another pack. Local model, local rules, local desk. Marginal cost of reading another PDF stack: **free**.

| Topic | Stance |
|---|---|
| **Inference** | Ollama on-device — **$0 cloud LLM** |
| **Channels** | No paid messaging platforms |
| **TLS** | No paid auto-upload |
| **Privacy** | Agency-held files; mask PII in logs |
| **Employees** | Escape boring repetitive PDF grinding; Gloria keeps judgment |
| **If you productize** | Optional seats / checklist packs — the *engine* still does not burn tokens |

Vera multiplies Gloria’s team **without** multiplying headcount **and without paying anyone for AI**.

---

## 10. Live judge narrative

1. **Problem first** — show edges + incomplete Jason: this is today’s pain.  
2. **Vera at work** — live email of a coherent Jeff pack; watch extract + rules.  
3. **Gloria intervenes** — two look-items, ✓, Approve & email.  
4. **Closing line:**  
   *“Vera worked the file. Code applied the law. Gloria intervened — and only she can send.”*

---

## 11. Closing

Visa desks do not fail because people are lazy. They fail because **boring repetitive PDF work** eats the day — and paying cloud AI to “guess PASS” makes it expensive *and* unsafe.

**Llama 3.2** reads the stack.  
**Orchestration** decides — code on facts, Gloria on Send.  
**Human intervention on every outbound action.**  
**AI cost to run: $0.**  
**Tens of minutes back per file — so employees do skilled work, not page-flipping.**

That is the product.

---

*Product name: **Vera**. Gloria is the human manager.*
