# Hermod

A Telegram companion for patients after they get a prescription. It checks in at each dose
the way a nurse would, logs what actually happened, and flags missed or extra doses for the
doctor before the next visit.

> Hackathon project for Builders Hack: Unlocked (Oct 2026). All patient data is synthetic.

## Status

The patient-facing agent works end to end on Telegram: message → guardrails → Gemini with
tools → dose log → adherence rules → reply, plus scheduled check-ins at each dose time. The
doctor dashboard and prescription photo parsing are still stubs. **Agents: start with
[AGENTS.md](AGENTS.md) and [docs/HANDOFF.md](docs/HANDOFF.md).** See
[the design doc](docs/superpowers/specs/2026-10-10-hermod-design.md).

## Stack (all free)

- **Telegram Bot API**: patient chat, long polling (no public URL or tunnel needed)
- **Gemini Flash Lite** via LiteLLM (free tier, tool calling)
- **FastAPI**: app server + doctor dashboard
- **SQLite / SQLModel**: dose log, messages, agent traces, flags
- **APScheduler**: timed check-ins
- **n8n** (optional, Docker): fan doctor alerts out to email/Slack

## Layout

```
hermod/
  channels/    Channel protocol, Telegram adapter, console adapter (dev/tests)
  agent/       agent loop, prompts, tools
  llm/         LiteLLM wrapper
  harness/     tracer (logs every LLM call), guardrails, alerts
  adherence/   deterministic rules -> flags
  scheduler/   timed check-ins
  db/          models + session
  dashboard/   doctor pages
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
