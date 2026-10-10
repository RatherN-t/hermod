# Hermod

A WhatsApp companion for patients after they get a prescription. It checks in at each dose
the way a nurse would, logs what actually happened, and flags missed or extra doses for the
doctor before the next visit.

> Hackathon project for Builders Hack: Unlocked (Oct 2026). All patient data is synthetic.

## Status

Baseline architecture only. Modules are stubbed with interfaces. See
[the design doc](docs/superpowers/specs/2026-10-10-hermod-design.md).

## Stack (all free)

- **FastAPI**: webhook + doctor dashboard
- **WhatsApp Cloud API** (Meta test number)
- **Gemini Flash** via LiteLLM (free tier, tool calling + vision)
- **SQLite / SQLModel**: dose log, messages, agent traces, flags
- **APScheduler**: timed check-ins
- **n8n** (optional, Docker): fan doctor alerts out to email/Slack

## Layout

```
hermod/
  channels/    WhatsApp boundary (Channel protocol, Meta adapter, webhook routes)
  agent/       agent loop, prompts, tools
  llm/         LiteLLM wrapper
  harness/     tracer (logs every LLM call), guardrails, alerts
  adherence/   deterministic rules -> flags
  scheduler/   timed check-ins
  db/          models + session
  dashboard/   doctor pages
```

## Run

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in keys
uvicorn hermod.main:app --reload
pytest
```

Optional n8n: `docker compose --profile n8n up -d` → http://localhost:5678
