# AGENTS.md

Instructions for any coding agent (Claude Code, Codex, Cursor, etc.) working in this repo.

## Read first, in this order

1. [docs/HANDOFF.md](docs/HANDOFF.md): current state, decisions made, and what to do next.
2. [docs/superpowers/specs/2026-10-10-hermod-design.md](docs/superpowers/specs/2026-10-10-hermod-design.md): the design.
3. [docs/hackathon-brief.md](docs/hackathon-brief.md): what we're being judged on and the deadline.

## What this is

Hermod is a WhatsApp contact that checks in with a patient at each dose after they get a
prescription. It logs what actually happened and flags missed or extra doses for the doctor.
It's a hackathon entry, and submissions close **Mon 12 Oct 2026, 9am AEDT**.

## Hard constraints

- **Everything free.** No paid APIs or hosting. Gemini free tier, Meta WhatsApp test number,
  SQLite, local machine plus a free tunnel.
- **Python for the core.** The user wants to extend it in Python. `frontend/` (React + Vite,
  started by teammate Ethan) is the only non-Python code. n8n is optional and only used for alert fan-out.
- **No dosing advice from the agent, ever.** The safety path for emergencies and overdoses is
  deterministic and in `hermod/harness/guardrails.py`. Don't route it through the LLM.
- **Synthetic data only.** Label demo patients `is_synthetic=True`. Never commit real phone
  numbers, keys, or `.env`.
- **Module boundaries:** the agent talks to WhatsApp only through the `Channel` protocol
  (`hermod/channels/base.py`), and to the model only through `harness.tracer.traced_completion`
  (so every LLM call is logged). The adherence rules in `hermod/adherence/` decide what counts
  as a problem, and the LLM only records what the patient said.

## Commands

```bash
python3.13 -m venv .venv && source .venv/bin/activate   # Python 3.11 to 3.13; 3.14 is not supported yet
pip install -e ".[dev]"
cp .env.example .env
uvicorn hermod.main:app --reload       # http://localhost:8000/health
pytest -q
ruff check .
cd frontend && npm install && npm run dev
docker compose --profile n8n up -d     # optional n8n on :5678
```

## Working rules

- Keep `pytest` and `ruff check .` green before every commit.
- Small, focused commits. Push to `main` (it's a hackathon, so there's no PR process unless the team asks for one).
- Teammates push to the same repo, so run `git pull --rebase` before you push.
- When you finish a chunk of work, update the **Status** and **Next steps** sections of `docs/HANDOFF.md`.
