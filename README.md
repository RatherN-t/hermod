# Hermod

A Telegram companion for patients after they get a prescription. It checks in at each dose
the way a nurse would, logs what actually happened, and flags missed or extra doses for the
doctor before the next visit.

> Hackathon project for Builders Hack: Unlocked (Oct 2026). All patient data is synthetic.

## Status

The patient-facing agent works end to end on Telegram: message → guardrails → Gemini with
tools → dose log → adherence rules → reply, plus scheduled check-ins at each dose time. A
JSON API ([docs/API.md](docs/API.md), live at `/docs`) serves the doctor dashboard and the
prescription form; the React frontend is being wired to it. Prescription photo parsing is
still a stub. **Agents: start with
[AGENTS.md](AGENTS.md) and [docs/HANDOFF.md](docs/HANDOFF.md).** See
[the design doc](docs/superpowers/specs/2026-10-10-hermod-design.md).

## Stack (all free)

- **Telegram Bot API**: patient chat, long polling (no public URL or tunnel needed)
- **Gemini Flash Lite** via LiteLLM (free tier, tool calling)
- **FastAPI**: JSON API for the doctor dashboard (`/api`, docs at `/docs`)
- **SQLite or Supabase Postgres / SQLModel**: dose log, messages, agent traces, flags
- **APScheduler**: timed check-ins
- **n8n** (optional, Docker): fan doctor alerts out to email/Slack

## Layout

```
hermod/
  api/         JSON API for the dashboard (routes, response schemas)
  channels/    Channel protocol, Telegram adapter, console adapter (dev/tests)
  agent/       agent loop, prompts, tools
  llm/         LiteLLM wrapper
  harness/     tracer (logs every LLM call), guardrails, alerts
  adherence/   deterministic rules -> flags
  scheduler/   timed check-ins
  db/          models, session (SQLite/Postgres), schema upkeep, copy tool
  demo.py      seed a synthetic patient, print their link, chat in the terminal
```

## Run

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add GEMINI_API_KEY and TELEGRAM_BOT_TOKEN
pytest
```

### 1. Create the bot

In Telegram, message **@BotFather**, send `/newbot`, and pick a name and a username ending in
`bot`. Put the token in `.env` as `TELEGRAM_BOT_TOKEN=`.

### 2. Add a patient

```bash
python -m hermod.demo seed --phone 61400000000 --name "Sam Taylor"
```

This creates a synthetic patient on a 7-day amoxicillin course (08:00, 14:00, 20:00) and
prints their personal link, `https://t.me/<your_bot>?start=<code>`. Print it again with
`python -m hermod.demo link --phone 61400000000`. `--phone` is just the patient's id here.

### 3. Start Hermod

```bash
uvicorn hermod.main:app --port 8000
```

The patient opens their link and taps **Start**. Hermod links the chat to their record,
welcomes them, and checks in at every dose time while the server runs. If the patient had
already started the bot before using the link, Telegram drops the code, so they can send the
code (the part after `start=`) as a message instead.

### Dashboard API

With the server running, open `http://localhost:8000/docs` for every endpoint, or read
[docs/API.md](docs/API.md). The React dev server (`localhost:5173`) is allowed by CORS.

### Use Supabase instead of the local SQLite file

1. Create a free project at https://supabase.com, choosing a region near you and saving the
   database password.
2. In the project, click **Connect** and copy the **Session pooler** URI (port 5432; the
   direct connection is IPv6-only). Replace `[YOUR-PASSWORD]` with your database password.
3. Copy existing local data across (keeps ids, so Telegram links keep working):
   `python -m hermod.db.copy --to "<that URI>"`
4. Set `DATABASE_URL=<that URI>` in `.env` and restart the server. Tables are created on
   startup, new columns are added automatically, and row-level security is switched on so
   Supabase's public Data API can't read patient data.

### Try the agent in the terminal

```bash
CHANNEL=console python -m hermod.demo chat --phone 61400000000
```

Type as the patient. `/checkin` sends the due check-in, `/flags` shows flags and adherence.

## Safety

- Messages about overdoses or emergencies skip the LLM and get a fixed escalation message
  (000 / Poisons Information 13 11 26) plus an URGENT flag.
- Replies that drift into dosing advice are replaced with a fixed "ask your doctor" message.
- Every LLM call is stored in `AgentTrace` (prompt, output, tool calls, latency, errors).
