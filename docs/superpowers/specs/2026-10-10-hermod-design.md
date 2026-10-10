# Hermod: design (v0, awaiting approval)

Hackathon: Builders Hack: Unlocked (build 9–11 Oct 2026, submissions due 12 Oct 9am AEDT).

## Problem

A patient leaves the clinic with a new prescription. Between visits nobody tracks whether it
was followed: doses get missed, doubled up, or stopped early. At the follow-up visit the
patient can't remember accurately and the doctor is guessing. Around 50% of patients with
chronic conditions don't take their medication as prescribed (WHO, 2003). Collecting more
first-hand evidence is a separate task.

## The new ability

- **Patient:** follows their course correctly, with a WhatsApp contact that checks in at
  each dose, answers "did I already take it?", and never makes them feel judged.
- **Doctor:** sees an accurate adherence log and red flags (missed, extra, side effects)
  before the next visit, something they currently can't get.

## Scope for the weekend

1. Doctor adds a prescription (web form; stretch goal: photo parsed by Gemini vision).
2. Patient taps a wa.me link or QR code, sends "Hi", and Hermod onboards them (this opens the 24h window).
3. At each dose time Hermod checks in. The patient replies in free text and the agent logs it with tools.
4. Rules raise flags. Overdose language bypasses the LLM and goes to a fixed escalation message plus an URGENT flag.
5. Doctor dashboard: timeline, % adherence, open flags, full agent trace for each message.

Out of scope: real patient data, EHR integration, multi-clinic auth, languages other than English.

## Architecture

All Python (FastAPI). Each module has one job and talks to the others through a small interface.

| Module | Responsibility |
| --- | --- |
| `channels/` | WhatsApp boundary. `Channel` protocol plus a Meta Cloud API adapter. Webhook verify/receive. |
| `agent/` | Agent loop, system prompt, tool specs (`log_dose`, `flag_issue`). |
| `llm/` | LiteLLM wrapper. The model is set by env (`gemini/gemini-2.5-flash`). Vision extraction. |
| `harness/` | `tracer`: every LLM call logged to `AgentTrace`. `guardrails`: deterministic safety checks. `alerts`: flag fan-out to n8n. |
| `adherence/` | Deterministic rules that turn the dose log into flags and summary stats. The LLM records, the rules judge. |
| `scheduler/` | APScheduler tick creates DoseEvents and sends due check-ins. |
| `db/` | SQLModel + SQLite: Patient, Prescription, Medication, DoseEvent, Message, AgentTrace, Flag. |
| `dashboard/` | Jinja pages for the doctor. |

Data flow (inbound): Meta webhook → signature check → `parse_webhook` → store Message →
guardrail pre-check → `traced_completion` with tools → `execute_tool` writes DoseEvent/Flag →
guardrail post-check → `send_text` → store Message → `adherence.evaluate_patient` → alerts.

Data flow (proactive): scheduler tick → due DoseEvent → if within 24h window `send_text`, else
`send_template` (pre-approved utility template) → patient reply handled as inbound.

## Key decisions

- **WhatsApp:** Meta Cloud API with a free test number (up to 5 verified recipients). Messages outside
  the 24h window require a pre-approved template. We'll submit a utility "dose check-in"
  template on day 1. The `Channel` protocol keeps WAHA/Twilio available as a fallback.
- **LLM:** Gemini Flash free tier via LiteLLM. Supports tool calling and vision.
- **n8n:** optional, used only for alert fan-out. The core logic stays in Python.
- **Safety:** no dosing advice, fixed escalation text, all demo data synthetic and labelled.
- **Hosting for the demo:** run locally behind a free tunnel (cloudflared or ngrok) so Meta can reach the webhook.

## Testing

- Unit: adherence rules, guardrails, webhook parsing (fixtures from real Meta payloads).
- Scripted conversation replay against the agent with the LLM mocked.
- Hand-over test: someone unfamiliar does a 2-day course on their own phone (required by the brief).

## Open questions

- Which persona for the demo: an acute antibiotic course (clear end, easy story) or a chronic
  medication (bigger problem)? Recommendation: antibiotics for the demo, chronic for the market-size slide.
