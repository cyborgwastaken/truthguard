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
| [DOCS/demo-script.md](DOCS/demo-script.md) | The demo, step by step, and what to do when something goes wrong |
| [DOCS/evaluation-methodology.md](DOCS/evaluation-methodology.md) | How the benchmark works and what its numbers do not show |
| [DOCS/instructions.md](DOCS/instructions.md) | Entry point and rules for AI coding agents |
| [DOCS/team/README.md](DOCS/team/README.md) | How we work: board, branches, pull requests, who does what |
| [DOCS/team/](DOCS/team/) | One page per person, and one doc per role with step-by-step ticket instructions |
| [DOCS/maintainer-guide.md](DOCS/maintainer-guide.md) | For the project lead: reviewing and merging PRs, branch protection, board upkeep |
| [DOCS/progress.md](DOCS/progress.md) | What is done, in flight and blocked right now; decisions and reasons |
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

## Run it

With Docker Desktop running, and Node 20.19+ and Python 3.12+ installed:

```bash
OPS/start.sh     # database, backend, sample documents, frontend: then open http://localhost:5173
OPS/stop.sh
```

Put `GROQ_API_KEY=...` in `BACKEND/.env` for real answers. The full guide is [DOCS/setup.md](DOCS/setup.md); the demo is
[DOCS/demo-script.md](DOCS/demo-script.md); how it is measured is [DOCS/evaluation-methodology.md](DOCS/evaluation-methodology.md).

Tests: `cd AGENT && python -m pytest`, `cd BACKEND && python -m pytest` (needs the database), `python -m pytest OPS/tests`.
