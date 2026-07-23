# SpendWise
Privacy-first financial intelligence, with entity extraction and budget coaching running entirely on the local host — not in the cloud.

SpendWise is an event-driven, agentic AI financial assistant that lives inside WhatsApp. It reads incoming bank SMS alerts, extracts the transaction details, checks them against your budget, and only messages you back when something needs attention. The AI model that does this never sends your transaction data to an external provider.

Install: clone the repo, add the local model file, configure your `.env`, and run the FastAPI webhook (full steps below).

## Problem statement

Traditional finance apps are passive and privacy-hostile at the same time:

- **Manual entry fatigue.** You have to type in amounts, merchants, and categories by hand. Most people abandon tracking within two weeks.
- **The post-mortem problem.** Budgeting apps tell you that you overspent *after* the money is gone. There is no real-time intercept.
- **The privacy dilemma.** Cloud-based finance assistants require uploading raw SMS bank alerts, statements, and spending habits to third-party model providers (OpenAI, Anthropic, etc.), which is a real data-harvesting and security risk for sensitive financial information.

SpendWise's answer to all three: automatic ingestion, proactive alerts before a limit is breached, and 100% local inference so raw financial data never leaves the user's environment.

## Solution overview

SpendWise is one system delivered as three cooperating agents behind a single WhatsApp number:

- **The Auditor** — ingress sanitizer. Runs local, zero-shot entity extraction on noisy bank SMS text and maps it into a standardized `{amount, category, merchant}` JSON schema.
- **The Coach** — proactive guardian. Runs continuous budget-sustainability math and, on a breach, simulates a proportional rebalancing across the user's other categories.
- **The Gatekeeper** — traffic controller. Handles commands (`/status`, `Confirm`, `/reset-all-data`) and manages secure state-machine transitions.

Why WhatsApp: zero-download friction (no new app, no new account) and always-on delivery through infrastructure the user already checks constantly, without adding to notification fatigue since SpendWise only speaks up when it matters.

## Architecture

```
[User's Phone / SMS Bank Alert]
          │ (Forwarded via Android SMS Forwarder app)
          ▼
[Twilio / FastAPI Webhook Gateway]
          │ (Async background hand-off)
          ▼
[LangGraph Stateful Orchestrator]
   ├── Node 1: Gatekeeper (validates command & access)
   ├── Node 2: Auditor  (local Phi-3 entity extraction & sanitization)
   └── Node 3: Coach    (budget math, guardrails & rebalancing)
          │
          ├──> Local Model Memory (llama.cpp / RAM)
          └──> Persistent Storage (Supabase PostgreSQL audit logs)
```

Built on FastAPI (webhooks), LangGraph (deterministic state orchestration), and llama.cpp (local inference).

## Local AI at a glance

| Stage | Local input | Model & runtime | Local output | Data sent to cloud |
|---|---|---|---|---|
| Entity extraction | Raw incoming bank SMS text | Phi-3-mini-4k-instruct, 4-bit GGUF quant, via `llama.cpp` in-process | Standardized `{amount, category, merchant}` JSON | None — extraction never leaves the process |
| Budget coaching | Extracted transaction + current budget state | Deterministic Python guardrail logic (no LLM call) | Rebalancing proposal / coaching message | Only the resulting WhatsApp message text, sent via Twilio |

Both stages run in local process memory. There is no cloud inference API in the critical path — the only outbound traffic is the Twilio message delivery and the Supabase audit write, neither of which carries the AI prompt.

## The privacy boundary

SpendWise enforces a strict physical separation between the communication rails and the intelligence layer:

- **Transport layer (cloud).** Twilio handles WhatsApp message distribution; Supabase handles encrypted relational storage of audit logs.
- **Inference layer (local edge).** The quantized Phi-3-mini model (`Phi-3-mini-4k-instruct-q4.gguf`) runs entirely within local process memory. No prompt payload containing transaction strings is ever sent to an external LLM API.

This means the cloud services only ever see what's needed to route a message and store a log entry — never the raw SMS text or the model's reasoning over it.

## How the agents work

**Auditor — entity extraction.** On each inbound SMS forward, the Auditor formats the raw string into a zero-shot extraction prompt (`temperature=0.0`, strict system instructions to return only JSON) and runs it against the local Phi-3 instance. A regex-based cleanup pass (`_clean_json`) strips any stray text so the result parses as clean JSON. If the local model is unavailable, a deterministic fallback keyword dictionary (`fallback_categorize_by_text`) guarantees the pipeline still produces a categorization instead of failing silently.

**Coach — budget guardrail and rebalancing.** After extraction, the Coach checks the transaction against the relevant category's monthly limit. If it causes a deficit, `simulate_rebalancing` computes a proportional reduction across every *other* category weighted by each one's remaining headroom, and proposes new limits that absorb the deficit without touching the breached category itself. Every automated change is written to an immutable `budget_history` audit row before any WhatsApp message goes out.

**Gatekeeper — command routing.** Intercepts inbound webhook requests, validates the sender and command, and drives the LangGraph state machine so that confirmations, resets, and status checks can't race with an in-flight transaction.

## Implemented feature set

- Zero-touch ingestion of forwarded bank SMS alerts, no manual entry.
- Local, zero-shot transaction entity extraction with a deterministic keyword fallback for 100% classification resilience.
- Continuous budget-sustainability checks with proactive, pre-breach alerts.
- Automatic proportional rebalancing proposals when a category runs over.
- Immutable, event-sourced audit log (`budget_history`) for every AI-driven budget change.
- WhatsApp-native commands: `/status`, `Confirm`, `/reset-all-data`.
- Asynchronous webhook hand-off so Twilio never times out waiting on inference.

## Requirements

- Python 3.9+
- A Supabase account (PostgreSQL storage)
- A Twilio account with WhatsApp Sandbox access
- An Android device with an SMS-forwarding app (e.g. "SMS Forwarder") to relay bank notifications to the webhook
- ~2.3 GB free RAM/disk for the local GGUF model
- `ngrok` (or equivalent) to tunnel the local webhook to Twilio during development

## Model setup (required before first run)

1. Download `Phi-3-mini-4k-instruct-q4.gguf` (4-bit GGUF quantization) from Hugging Face.
2. Place it inside the `/models` directory.
3. Confirm the final path is `models/Phi-3-mini-4k-instruct-q4.gguf`, or point `LOCAL_LLM_FILE_PATH` at a different location.

The quantized model has a ~2.3 GB footprint — roughly 40% smaller than an unquantized load — and sustains ~12–15 tokens/sec on a standard consumer CPU, which keeps entity extraction well under the timeout budget described below.

## Setup instructions

**1. Clone and install dependencies**

```bash
git clone https://github.com/annie230606/SpendWise
cd SpendWise
pip install -r requirements.txt
```

**2. Configure environment**

Create a `.env` file (see `.env.example` for the full list) with at minimum:

```
LOCAL_LLM_FILE_PATH=models/Phi-3-mini-4k-instruct-q4.gguf
TWILIO_ACCOUNT_SID=<your-twilio-account-sid>
TWILIO_AUTH_TOKEN=<your-twilio-auth-token>
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
SUPABASE_URL=<your-supabase-project-url>
SUPABASE_KEY=<your-supabase-service-key>
```

Keep real secrets only in `.env` (never commit it) or your deployment's secret manager.

**3. Set up the database**

Run `sql/schema.sql` against your Supabase project to create the `budget_history` audit table and any supporting budget/transaction tables.

**4. Run the webhook**

```bash
uvicorn api.webhook:app --reload --port 8000
```

**5. Expose it to Twilio**

```bash
ngrok http 8000
```

Point your Twilio WhatsApp Sandbox's inbound webhook at the resulting `https://<ngrok-id>.ngrok.io/sms-alert` URL.

**6. Configure the Android SMS forwarder**

Install an SMS-forwarding app on the Android device that receives bank alerts, and point it at your exposed `/sms-alert` endpoint.

## Usage

- **Onboarding.** Send "Hi" to your Twilio WhatsApp number.
- **Automatic logging.** Once forwarding is configured, bank SMS alerts are parsed and logged with no further action needed.
- **Check status.** Send `/status` to view current budget balances.
- **Reset.** Send `/reset-all-data` to clear the database and start over.

## Sample behavior

Incoming forwarded SMS:

```
Debit Alert: A/C X541 used for 500.00 at SWIGGY
```

Expected result: the Auditor extracts `{"amount": 500.00, "category": "Food & Dining", "merchant": "SWIGGY"}`, the Coach checks it against the Food & Dining budget, and — only if this pushes the category into deficit — a WhatsApp message proposing a rebalancing across other categories is sent. Otherwise, SpendWise stays silent.

## Challenges encountered and mitigations

**WhatsApp webhook timeouts.** LLM inference takes 2–4 seconds, which was enough for Twilio to drop or resend the connection. Mitigated with FastAPI `BackgroundTasks`: the webhook returns `200 OK` immediately and the agent pipeline runs downstream.

**LLM inference latency on consumer CPUs.** Unquantized models were too slow and memory-heavy for a laptop-class target. Mitigated by adopting a 4-bit GGUF quantization of Phi-3-mini, cutting memory needs by ~40% while holding ~12–15 tokens/sec.

**Inconsistent bank SMS formats.** Different banks send wildly different string layouts for the same event (e.g. "Paid INR 500 to Swiggy" vs. "Debit Alert: A/C X541 used for 500.00 at SWIGGY"). Mitigated by pairing the zero-shot extraction prompt with a deterministic keyword-based fallback categorizer, so classification never hard-fails.

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.9+ |
| Web framework | FastAPI |
| Orchestration | LangGraph |
| Local inference | `llama.cpp`, Phi-3-mini-4k-instruct (4-bit GGUF) |
| Database | Supabase (PostgreSQL) |
| Messaging | Twilio API for WhatsApp |
| Data processing | Pandas |

## Metrics

- **Privacy:** 100% on-device entity parsing; zero external data leakage of financial logs.
- **Inference cost:** $0.00 per inference (local CPU cycles, no paid token endpoint).
- **Speed:** sub-second routing latency; ~12–15 tokens/sec on coaching responses.
- **Audit integrity:** 100% of automated rebalances write an immutable change log entry.

## Demo

Demo video and screenshots: https://drive.google.com/drive/folders/1M9XXnlRoL3HQMefjlnUqt9DDoPPlAYt8?usp=sharing

## Future scope and limitations

**Limitations:** requires enough local RAM for the LLM to run audits promptly; currently single-currency and dependent on the user's bank sending parseable SMS alerts.

**Future scope:** direct bank account syncing (Plaid / Salt Edge) to remove the SMS-forwarding dependency, and multi-currency support.

## License

MIT License. See `LICENSE` for details.
