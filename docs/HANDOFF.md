# Handoff

Last updated: Sat 10 Oct 2026 (build day 2 of 3). Submissions close **Mon 12 Oct, 9am AEDT**.

## Status in one paragraph

The design is written and the baseline architecture is pushed. Every Python module exists with
its interface and docstring, but the bodies are `raise NotImplementedError`. Only two things
work end to end: `GET /health` and the Meta webhook verification handshake (`GET /webhook/whatsapp`).
The data model in `hermod/db/models.py` is complete. Teammate Ethan has added `frontend/`, which
is still the default Vite + React starter page with no Hermod UI. **The user has not yet approved
the design for implementation.** They asked for the plan and scaffold first. Confirm with the user
before writing feature code, unless they've already said "go".

## The idea

A patient leaves the clinic with a prescription. By the follow-up visit, neither they nor the
doctor knows how closely it was followed. Hermod sits in the patient's WhatsApp as a contact and
checks in at each dose, the way a nurse would. It logs taken, late, missed and extra doses, and
flags problems for the doctor. Architecture inspiration: https://instinct.com/ (an agent that
lives in WhatsApp).

- **The new ability (the hackathon's central question):** the patient can now follow their course
  correctly, and the doctor can now see what happened between visits.
- **Suggested demo person:** someone on a 7-day antibiotic course, since the story has a clear
  start and end. Use chronic medication non-adherence for the "how big is the problem" slide
  (WHO 2003: about 50% of people with chronic conditions don't take medication as prescribed).

## Decisions already made (don't reopen them without asking the user)

| Decision | Choice | Why |
| --- | --- | --- |
| WhatsApp | **Meta WhatsApp Cloud API**, free test number | Official, so it's credible for health. Free. Limit: 5 verified recipient phones. |
| 24h rule | Free-form replies only within 24h of the patient's last message. Proactive check-ins outside that window need a **pre-approved template**. | Meta policy. `Patient.last_inbound_at` drives the choice between `send_text` and `send_template`. |
| LLM | **Gemini Flash free tier via LiteLLM** (`LLM_MODEL=gemini/gemini-2.5-flash`) | Free, supports tool calling, and vision (stretch goal: read a prescription photo). Swapping models means changing one env var. |
| Core language | **Python / FastAPI** | User preference. |
| n8n | **Optional, alerts only** (`docker compose --profile n8n`) | User asked about n8n. We agreed to keep the logic in Python so there's one codebase to debug. |
| Storage | SQLite + SQLModel | Free, no setup. |
| Scheduling | APScheduler, in-process | Free, no extra infrastructure. |
| Safety | No dosing advice. Overdose or emergency text skips the LLM and gets a fixed escalation message (000 / Poisons Information Centre 13 11 26) plus an URGENT flag. | Health product; judges will ask about this. |
| Repo | Public: https://github.com/RatherN-t/hermod | |

## Open decisions

1. **What `frontend/` is for.** It could be the public website (a required hackathon
   deliverable), the doctor dashboard, or both. The design doc planned Jinja pages in
   `hermod/dashboard/` for the doctor. If the React app becomes the dashboard, `hermod/dashboard/`
   should become a JSON API (`/api/...`) instead. Ask the user or Ethan.
2. **Demo person:** antibiotics (recommended) or chronic medication.
3. **Prescription entry:** web form only, or also a photo parsed by Gemini vision (stretch goal).

## Code map

| Path | State | Contains / will contain |
| --- | --- | --- |
| `hermod/main.py` | working | App, lifespan (init DB, start scheduler), `/health` |
| `hermod/config.py` | working | Settings loaded from `.env` |
| `hermod/db/models.py` | working | Patient, Prescription, Medication, DoseEvent(status), Message, AgentTrace, Flag |
| `hermod/db/session.py` | working | Engine, `init_db`, `get_session` |
| `hermod/channels/base.py` | working | `Channel` protocol, `IncomingMessage` |
| `hermod/channels/routes.py` | partial | GET verify works; POST receive is a stub |
| `hermod/channels/meta_whatsapp.py` | stub | `send_text`, `send_template`, `parse_webhook`, `verify_signature` |
| `hermod/llm/client.py` | stub | `complete()` via LiteLLM; `extract_prescription_from_image()` |
| `hermod/harness/tracer.py` | stub | `traced_completion()`: calls the LLM and writes an `AgentTrace` row |
| `hermod/harness/guardrails.py` | stub (message text done) | `detect_emergency()`, `check_outbound()` |
| `hermod/harness/alerts.py` | stub | `notify_doctor()`: POST to `N8N_ALERT_WEBHOOK_URL` |
| `hermod/agent/prompts.py` | done | System prompt template |
| `hermod/agent/tools.py` | specs done | `log_dose`, `flag_issue` specs; `execute_tool()` stub |
| `hermod/agent/agent.py` | stub | `handle_inbound()`, `run_checkin()` |
| `hermod/adherence/rules.py` | stub | `evaluate_patient()`, `adherence_summary()` |
| `hermod/scheduler/jobs.py` | partial | Scheduler starts, but no jobs are registered |
| `hermod/dashboard/routes.py` | empty router | Doctor views (see open decision 1) |
| `frontend/` | Vite starter page | React 19 + Vite 8 + TypeScript |
| `n8n/` | README only | Exported n8n workflows go here |
| `tests/test_smoke.py` | 2 passing | Health check; webhook rejects a bad token |

## Next steps (suggested build order)

Each step should be demoable on its own, so stopping early still leaves something to show.

1. **WhatsApp echo:** implement `MetaWhatsAppChannel` (`parse_webhook`, `send_text`,
   `verify_signature`) and wire POST `/webhook/whatsapp` to store a `Message` and echo the
   text back. Test with fixture payloads from Meta's docs. Then try it live through a tunnel.
2. **LLM and harness:** `llm.complete()` via LiteLLM, and `traced_completion()` writing an
   `AgentTrace`. Swap the echo for an LLM reply.
3. **Agent with tools:** `handle_inbound()` builds the prompt from the patient's current
   prescription, runs the tool loop (`log_dose` and `flag_issue` write `DoseEvent`s and `Flag`s),
   then sends the reply. Add guardrails before and after the LLM call.
4. **Seed script:** synthetic doctor, patient and 7-day amoxicillin prescription, so the DoseEvents exist.
5. **Scheduler:** a tick every minute finds due `DoseEvent`s and calls `run_checkin()`
   (template if outside 24h, otherwise free-form). Mark no-reply doses `UNKNOWN` after N hours.
6. **Adherence rules:** 2 or more consecutive missed doses; more than `max_daily_doses`;
   stopped before `end_date`. Write `Flag`s and call `notify_doctor()`.
7. **Doctor view:** patient list, dose timeline, % adherence, open flags, and the agent trace
   for each message. Where it lives depends on open decision 1.
8. **Prescription entry form** (and, as a stretch, a photo parsed by Gemini vision).
9. **Hackathon deliverables:** public website, 4-page deck, demo of 5 minutes or less (see the brief),
   plus a hand-over test with someone unfamiliar with the product.

## Setup the user must do (not code; check with the user what's done)

- [ ] Gemini API key from https://aistudio.google.com/apikey, saved as `GEMINI_API_KEY` in `.env`.
- [ ] Meta developer app with the WhatsApp product enabled. Copy the token and phone number ID into `.env`,
      and add the testers' phones as verified recipients.
- [ ] Submit a **utility template** for dose check-ins as early as possible. Approval takes time.
      Until it's approved, the default `hello_world` template is the only option outside the 24h window.
- [ ] Free tunnel (`cloudflared tunnel --url http://localhost:8000` or ngrok). Register
      `https://<tunnel>/webhook/whatsapp` with `WHATSAPP_VERIFY_TOKEN` in Meta and subscribe to `messages`.
- [ ] Everyone on the team completes the Builders Survey (a submission requirement).

## Gotchas

- Python 3.14 is not supported (`requires-python <3.14`). Use 3.13.
- WhatsApp sends phone numbers in E.164 format without the `+`. Store them the same way in `Patient.wa_phone`.
- Meta retries webhooks that don't respond quickly, so return 200 at once and process in the background.
  Deduplicate on `wa_message_id`.
- A `hermod-1/` folder may exist in some local checkouts. It's a teammate's second clone, so don't commit it.
