# Handoff

Last updated: Sat 10 Oct 2026, night (build day 2 of 3). Submissions close **Mon 12 Oct, 9am AEDT**.

## Status in one paragraph

The patient-facing agent works end to end **on Telegram** and has been tested live on a real
phone. A patient opens their personal start link, Hermod links the chat to their record and
welcomes them, checks in at each dose time, logs what they report with tools, answers "did I
already take it?" from the log, flags side effects and questions for the doctor, and sends
overdose or emergency messages to a fixed escalation without the LLM. Every LLM call is traced.
The backend now also serves a **JSON API** for the doctor dashboard and the prescription
form (patients, reminders, dose timeline, adherence, flags, conversation, agent traces); see
[docs/API.md](API.md) or `/docs` on the running server. It runs on SQLite locally or on
**Supabase Postgres** (tested against Postgres 15). The remaining work is the **frontend**:
Ethan's `frontend/` has the medication-reminder form on demo data, to be wired to the API.

## The idea

A patient leaves the clinic with a prescription. By the follow-up visit, neither they nor the
doctor knows how closely it was followed. Hermod sits in the patient's Telegram as a contact and
checks in at each dose, the way a nurse would. It logs taken, late, missed and extra doses, and
flags problems for the doctor. Architecture inspiration: https://instinct.com/ (an agent that
lives in a messaging app).

- **The new ability (the hackathon's central question):** the patient can now follow their course
  correctly, and the doctor can now see what happened between visits.
- **Suggested demo person:** someone on a 7-day antibiotic course, since the story has a clear
  start and end. Use chronic medication non-adherence for the "how big is the problem" slide
  (WHO 2003: about 50% of people with chronic conditions don't take medication as prescribed).

## Decisions already made (don't reopen them without asking the user)

| Decision | Choice | Why |
| --- | --- | --- |
| Messaging | **Telegram Bot API**, long polling | Free, no approval, templates or 24h window, and no public URL needed. WhatsApp was tried first (Meta Cloud API and Twilio adapters were built), but Meta blocked developer signup from a new device, Twilio trial accounts can only send fixed templates, and a borrowed Meta test number was banned. See the design doc. |
| Patient linking | Personal link `t.me/<bot>?start=<link_code>` | Telegram doesn't share phone numbers with bots. If Telegram drops the code (chat already started), the patient can send the code as a message. |
| LLM | **Gemini 3.5 Flash Lite via LiteLLM** (`LLM_MODEL=gemini/gemini-3.5-flash-lite`) | Free, tool calling, about 1–2s per call. `gemini-2.5-flash` is retired for new keys; `gemini-3.8-flash` took 60s+ per call on the free tier. |
| Core language | **Python / FastAPI** | User preference. |
| n8n | **Optional, alerts only** (`docker compose --profile n8n`) | Keep the logic in Python so there's one codebase to debug. |
| Storage | SQLite + SQLModel | Free, no setup. Datetimes are timezone-aware UTC. |
| Scheduling | APScheduler, in-process | Free, no extra infrastructure. |
| Safety | No dosing advice. Overdose or emergency text skips the LLM and gets a fixed escalation message (000 / Poisons Information Centre 13 11 26) plus an URGENT flag. Replies containing dosing advice are replaced. Flag summaries state only what the patient said. | Health product; judges will ask about this. |
| Repo | Public: https://github.com/RatherN-t/hermod | |

## Open decisions

1. **Public website** (a required hackathon deliverable): a separate page, or part of `frontend/`.
2. **Demo person:** antibiotics (recommended) or chronic medication.
3. **Prescription entry:** web form only, or also a photo parsed by Gemini vision (stretch goal).

## Code map

| Path | State | Contains |
| --- | --- | --- |
| `hermod/main.py` | working | App, lifespan (init DB, scheduler, Telegram poller), logging, `/health` |
| `hermod/config.py` | working | Settings from `.env` (`GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `CHANNEL`, ...) |
| `hermod/db/models.py` | working | Patient (`phone`, `telegram_chat_id`, `link_code`), Prescription, Medication, DoseEvent, Message, AgentTrace, Flag |
| `hermod/channels/telegram.py` | working | `send_text`, long-polling `poll_forever`, `parse_update`; never logs the bot token |
| `hermod/channels/console.py` | working | Prints instead of sending (`CHANNEL=console`, tests, CLI) |
| `hermod/llm/client.py` | working | `complete()` via LiteLLM; `extract_prescription_from_image()` is still a stub |
| `hermod/harness/tracer.py` | working | `traced_completion()` writes an `AgentTrace` row per call, including errors |
| `hermod/harness/guardrails.py` | working | `detect_emergency()`, `check_outbound()` |
| `hermod/harness/alerts.py` | working | `notify_doctor()` POSTs to `N8N_ALERT_WEBHOOK_URL` if set |
| `hermod/agent/agent.py` | working | `handle_inbound()` (linking, guardrails, tool loop, reply), `run_checkin()` |
| `hermod/agent/tools.py` | working | `log_dose`, `flag_issue` |
| `hermod/adherence/rules.py` | working | `evaluate_patient()` (missed streak, extra dose, daily max, unresponsive 24h), `adherence_summary()` |
| `hermod/scheduler/jobs.py` | working | Minute tick: create DoseEvents, send due check-ins, mark no-reply doses `UNKNOWN` after 6h |
| `hermod/demo.py` | working | `seed` / `link` / `chat` CLI |
| `hermod/api/routes.py` | working | `/api/...` endpoints (list in `docs/API.md`), optional `X-API-Key` |
| `hermod/api/schemas.py`, `views.py` | working | camelCase response/request models; row → response builders |
| `hermod/db/session.py` | working | SQLite/Postgres engine, `add_missing_columns()`, Supabase RLS lock-down |
| `hermod/db/copy.py` | working | `python -m hermod.db.copy --to <url>`: copy all data, keeping ids |
| `frontend/` | form, demo data | React 19 + Vite 8 + TypeScript medication-reminder form; not connected to the API |
| `tests/` | 62 passing | API, agent (LLM mocked), Telegram, guardrails, rules, scheduler, DB upkeep. `TEST_DATABASE_URL=postgresql://...` runs them on Postgres |

## Next steps (suggested build order)

1. **Wire the frontend to the API** (Ethan): the reminder form → `POST /api/patients/{id}/reminders`,
   the patient's Telegram link/QR from `link.telegramLink`, and the doctor view from
   `/api/dashboard`, `/api/patients/{id}`, `/adherence`, `/doses`, `/flags`, `/messages`,
   `/api/traces/{id}`. Field mapping from the existing TypeScript types is in `docs/API.md`.
2. **Shared database:** done. Live data is in Supabase (see setup below); the local
   `hermod.db` is a stale copy from before the move.
3. **Hand-over test:** someone unfamiliar does a 2-day course on their own phone. Seed them, send
   the link, and keep the server running.
4. **Hackathon deliverables:** public website, 4-page deck, demo of 5 minutes or less (see the brief).
5. Stretch: prescription photo parsed by Gemini vision.

## Setup the user must do (not code; check with the user what's done)

- [x] Gemini API key in `.env` as `GEMINI_API_KEY`.
- [x] Telegram bot from @BotFather, token in `.env` as `TELEGRAM_BOT_TOKEN`.
- [x] Supabase project `miumtcqtdncqqhgpqbrd` (Sydney, Postgres 17) holds the live data. Its
      Session pooler URI is `DATABASE_URL` in the user's `.env` (ask the user for it privately;
      it contains the DB password). `.mcp.json` adds the Supabase MCP server; each person runs
      `claude /mcp` in a terminal to sign in.
- [ ] Everyone on the team completes the Builders Survey (a submission requirement).

## Gotchas

- Python 3.14 is not supported (`requires-python <3.14`). Use 3.13.
- Check-ins only go out while `uvicorn` is running. Keep the machine awake during the hand-over test.
- New model columns are added on startup (`add_missing_columns`), but renames and drops are not:
  those need a hand migration on every existing database, including Supabase.
- Use Supabase's **Session pooler** URI (port 5432). The direct connection is IPv6-only on the
  free tier, and the transaction pooler (6543) doesn't suit a long-running server.
- Reminder `pause` deletes upcoming doses and `resume` recreates them, so paused time isn't
  counted as missed.
- `httpx` logs request URLs at INFO, and Telegram URLs contain the bot token, so `main.py` keeps
  `httpx`/`httpcore` at WARNING. Don't lower that.
- A `hermod-1/` folder may exist in some local checkouts. It's a teammate's second clone, so don't commit it.
