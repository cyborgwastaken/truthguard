# TruthGuard

Multi-agent document verification: sourced answers, contradiction and staleness detection, honest abstention.

> **AI coding agents: stop and read [DOCS/instructions.md](DOCS/instructions.md) before doing anything else.**
> It tells you to ask the human who they are and which ticket they are working on, which docs to read first, and the rules for this repo.
>
> **New team member (human)?** Start with [DOCS/team/README.md](DOCS/team/README.md).

## Documentation index

| Doc | What it is |
|---|---|
| [DOCS/setup.md](DOCS/setup.md) | Install and run everything on your computer |
| [DOCS/instructions.md](DOCS/instructions.md) | Entry point and rules for AI coding agents |
| [DOCS/team/README.md](DOCS/team/README.md) | How we work: board, branches, pull requests, who does what |
| [DOCS/team/](DOCS/team/) | One page per person, and one doc per role with step-by-step ticket instructions |
| [DOCS/backlog.md](DOCS/backlog.md) | All tickets, waves, dependencies |
| [DOCS/truthguard_intital_roadmap.md](DOCS/truthguard_intital_roadmap.md) | MVP plan: architecture, data contracts, demo scenarios |
| [DOCS/truthguard_expansion_roadmap.md](DOCS/truthguard_expansion_roadmap.md) | Evidence graph, trust reports, benchmark lab, later features |

Project board: GitHub -> cyborgwastaken -> Projects -> Virtusa TruthGuard.

| Folder | Purpose |
|---|---|
| `FRONTEND/` | React UI (chat, evidence graph, trust report, benchmark dashboard) |
| `BACKEND/` | FastAPI service: ingestion, question and evaluation APIs, persistence |
| `AGENT/` | Domain schemas, retriever, synthesizer, critic, resolver, orchestrator, datasets |
| `OPS/` | Docker Compose, database setup, deployment |
| `DOCS/` | Roadmaps, architecture, evaluation methodology |

## Dev setup

Full step-by-step guide: [DOCS/setup.md](DOCS/setup.md). The short version:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip
(cd BACKEND && pip install -r requirements.txt)          # also installs ../AGENT in editable mode
docker compose -f OPS/docker-compose.yml up -d           # Postgres on port 5433
(cd BACKEND && alembic upgrade head && python -m pytest)
(cd BACKEND && uvicorn app.main:app --reload)
```
