# Hermod: design (v1, patient agent built)

Hackathon: Builders Hack: Unlocked (build 9–11 Oct 2026, submissions due 12 Oct 9am AEDT).

## Problem

A patient leaves the clinic with a new prescription. Between visits nobody tracks whether it
was followed: doses get missed, doubled up, or stopped early. At the follow-up visit the
patient can't remember accurately and the doctor is guessing. Around 50% of patients with
chronic conditions don't take their medication as prescribed (WHO, 2003). Collecting more
first-hand evidence is a separate task.

## The new ability

- **Patient:** follows their course correctly, with a Telegram contact that checks in at
  each dose, answers "did I already take it?", and never makes them feel judged.
- **Doctor:** sees an accurate adherence log and red flags (missed, extra, side effects)
  before the next visit, something they currently can't get.

## Scope for the weekend

1. Doctor adds a prescription (web form; stretch goal: photo parsed by Gemini vision).
2. Patient opens their personal `t.me/<bot>?start=<code>` link (or QR code) and taps Start;
   Hermod links the chat to their record and onboards them.
3. At each dose time Hermod checks in. The patient replies in free text and the agent logs it
   with tools.
4. Rules raise flags. Overdose language bypasses the LLM and goes to a fixed escalation
   message plus an URGENT flag.
5. Doctor dashboard: timeline, % adherence, open flags, full agent trace for each message.

Done: 2–4, and the API behind 1 and 5. Next: the frontend for 1 and 5.

Out of scope: real patient data, EHR integration, multi-clinic auth, languages other than
English.

## Architecture

All Python (FastAPI). Each module has one job and talks to the others through a small
interface.

| Module | Responsibility |
| --- | --- |
| `channels/` | `Channel` protocol (`send_text`), Telegram adapter (long polling), console adapter for dev and tests. |
| `agent/` | Agent loop, system prompt, tool specs (`log_dose`, `flag_issue`), chat linking. |
| `llm/` | LiteLLM wrapper. The model is set by env (`gemini/gemini-3.5-flash-lite`). |
| `harness/` | `tracer`: every LLM call logged to `AgentTrace`. `guardrails`: deterministic safety checks. `alerts`: flag fan-out to n8n. |
| `adherence/` | Deterministic rules that turn the dose log into flags and summary stats. The LLM records, the rules judge. |
| `scheduler/` | APScheduler tick creates DoseEvents, sends due check-ins, marks unanswered doses unknown after 6h. |
| `db/` | SQLModel on SQLite or Supabase Postgres: Patient, Prescription, Medication, DoseEvent, Message, AgentTrace, Flag. Adds new columns on startup; copy tool between databases. |
| `api/` | JSON API for the React dashboard: patients, reminders, doses, adherence, flags, conversation, traces. |

Data flow (inbound): Telegram `getUpdates` → `parse_update` → find patient by chat id (or link
code) → store Message → guardrail pre-check → `traced_completion` with tools →
`execute_tool` writes DoseEvent/Flag → guardrail post-check → `send_text` → store Message →
`adherence.evaluate_patient` → alerts.

Data flow (proactive): scheduler tick → due DoseEvent → `send_text` check-in → patient reply
handled as inbound.

## Key decisions

- **Telegram, not WhatsApp.** WhatsApp was the plan, and adapters for Meta's Cloud API and
  Twilio were built and tested, but none could reach a phone this weekend: Meta blocked
  developer signup from a new device, Twilio trial accounts can only send fixed templates,
  and the borrowed Meta test number came back `BANNED`. Telegram's Bot API is free, needs no
  approval or templates, has no 24-hour messaging window, and long polling removes the need
  for a public URL. The `Channel` protocol keeps a WhatsApp adapter a one-class change later.
- **Linking without phone numbers.** Telegram doesn't share phone numbers with bots, so each
  patient gets a random `link_code` in their start link.
- **LLM:** Gemini 3.5 Flash Lite via LiteLLM, about 1–2s per call with tool calling. Gemini
  2.5 Flash is retired for new keys, and 3.8 Flash took over 60s per call on the free tier.
- **The LLM records, the rules judge.** Missed-dose streaks, extra doses, the daily maximum
  and unresponsiveness are deterministic rules over the dose log. Flag summaries must
  describe only what the patient said, because the doctor reads them as fact.
- **Safety:** no dosing advice, fixed escalation text, all demo data synthetic and labelled.
- **Dashboard = React + JSON API.** Ethan's `frontend/` is the doctor UI; the backend only
  serves JSON (`/api`, camelCase, documented in `docs/API.md`).
- **Database:** SQLite locally, Supabase (free Postgres) when shared. Supabase exposes the
  `public` schema over its Data API, so Hermod enables row-level security on its tables and
  connects as the owner. A reminder is one medication on its own prescription, and a pause
  removes upcoming doses so a paused course doesn't count as missed.
- **n8n:** optional, used only for alert fan-out. The core logic stays in Python.
- **Hosting for the demo:** run locally. Telegram long polling works from a laptop.

## Testing

- Unit: adherence rules, guardrails, Telegram update parsing, chat linking, bot token kept
  out of logs.
- Scripted conversation replay against the agent with the LLM mocked.
- Live run against real Gemini and a real Telegram chat (welcome, dose logging, "did I take
  it?", side effect, dosing question, overdose escalation).
- Hand-over test: someone unfamiliar does a 2-day course on their own phone (required by the
  brief).

## Open questions

- Which persona for the demo: an acute antibiotic course (clear end, easy story) or a chronic
  medication (bigger problem)? Recommendation: antibiotics for the demo, chronic for the
  market-size slide.
