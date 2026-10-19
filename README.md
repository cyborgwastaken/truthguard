# TruthGuard

Multi-agent document verification: sourced answers, contradiction and staleness detection, honest abstention.

| Folder | Purpose |
|---|---|
| `FRONTEND/` | React UI (chat, evidence graph, trust report, benchmark dashboard) |
| `BACKEND/` | FastAPI service: ingestion, question and evaluation APIs, persistence |
| `AGENT/` | Domain schemas, retriever, synthesizer, critic, resolver, orchestrator, datasets |
| `OPS/` | Docker Compose, database setup, deployment |
| `DOCS/` | Roadmaps, architecture, evaluation methodology |

## Dev setup

```bash
python3 -m venv .venv && . .venv/bin/activate
cd BACKEND && pip install -r requirements.txt   # also installs ../AGENT in editable mode
(cd ../AGENT && python -m pytest)
python -m pytest
uvicorn app.main:app --reload
```
