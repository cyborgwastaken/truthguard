# TruthGuard Backlog and Work Order

Source of truth for the GitHub Project board. Each row becomes one issue.

> **Current ownership** (supersedes the owner columns below; the role numbers there map to the roles in
> `DOCS/team/`). The source of truth is `OPS/github/create_backlog.py` and the board.
>
> | Role | Primary | Secondary |
> |---|---|---|
> | 1 Backend and Database | cyborgwastaken | yashdiwan12 |
> | 2 Retrieval and AI Pipeline | AshwaniArya2005 | cyborgwastaken, yashdiwan12 |
> | 3 Verification | yashdiwan12 | AshwaniArya2005 |
> | 4 Frontend | iamsarik | cyborgwastaken |
> | 5 Data, Evaluation and Demo | dhruvt293 | iamsarik |
>
> Role to ticket mapping: 1 = T03 T06 T14 T24 T27; 2 = T02 T07 T08 T13 T23; 3 = T05 T09 T12 T15 T18;
> 4 = T04 T11 T17 T20 T21 T22 T26; 5 = T01 T10 T16 T19 T25 T28.

## Roles (5 people)

| Role | Owns |
|---|---|
| **P1 Backend** | API, ingestion, database, persistence |
| **P2 Retrieval and Synthesis** | Retriever, synthesizer, orchestrator |
| **P3 Verification** | Critic, resolver, evidence links, trust report |
| **P4 Frontend** | React UI |
| **P5 Evaluation and Ops** | Corpus, benchmark, baseline RAG, Docker, docs, demo |

## Board columns

`Backlog` → `Ready` → `In progress` → `In review` → `Done`

- Wave 1 issues start in **Ready**; Wave 2 and later start in **Backlog** and move to Ready when their dependencies are Done.
- Done = merged PR, tests passing, acceptance criteria met.

## Wave 0: Scaffold (done)

| ID | Ticket | Status |
|---|---|---|
| T00 | Repo scaffold, shared schemas, `/health` | Done |

## Wave 1: Foundation (all five work in parallel)

| ID | Ticket | Owner | Depends on |
|---|---|---|---|
| T01 | Fictional corpus: 15–30 docs covering superseded, unresolved-conflict, insufficient-evidence, hard-negative cases, with expected labels | P5 | T00 |
| T02 | Ingestion: normalize text, chunk with stable IDs and offsets, content hash | P2 | T00 |
| T03 | Postgres in Docker Compose, SQLAlchemy models, migrations for Document/Chunk/Answer/Claim/EvidenceLink | P1 | T00 |
| T04 | Frontend scaffold: Vite + React + TS, API client, layout shell, health check | P4 | T00 |
| T05 | Resolver rules design doc: supersession, effective dates, authority, abstention (no code yet) | P3 | T00 |

## Wave 2: Core pipeline (starts when Wave 1 is Done)

| ID | Ticket | Owner | Depends on |
|---|---|---|---|
| T06 | `POST/GET /documents` wired to ingestion and DB | P1 | T02, T03 |
| T07 | Keyword/full-text retriever returning ranked passages with metadata | P2 | T02, T03 |
| T08 | Synthesizer: claim-level answer with citation IDs, Pydantic-validated, retry once | P2 | T07 |
| T09 | Resolver engine: deterministic supersession, date and authority rules, three statuses | P3 | T05 |
| T10 | Baseline RAG implementation (retrieve + answer, no critic) | P5 | T07 |
| T11 | Chat UI and document list/upload page | P4 | T04, T06 |

## Wave 3: Verification (starts when Wave 2 is Done)

| ID | Ticket | Owner | Depends on |
|---|---|---|---|
| T12 | Critic agent: contradictions, staleness, unsupported claims, each with evidence refs | P3 | T08 |
| T13 | Orchestrator: retrieve → synthesize → critic → resolve, with explicit failure states | P2 | T08, T09, T12 |
| T14 | `POST /questions` and `GET /answers/{id}` with persistence | P1 | T13 |
| T15 | Evidence graph assembler and `GET /answers/{id}/evidence-graph` | P3 | T12, T14 |
| T16 | Benchmark dataset v1 (labeled cases) and metric functions | P5 | T01, T10 |
| T17 | Answer view: citations, source passage viewer, conflict comparison | P4 | T11, T14 |

## Wave 4: Showcase (starts when Wave 3 is Done)

| ID | Ticket | Owner | Depends on |
|---|---|---|---|
| T18 | Trust report builder and `GET /answers/{id}/trust-report` with documented formulas | P3 | T15 |
| T19 | Benchmark runner (3 configs) and `POST /evaluations/runs` | P5 | T13, T16 |
| T20 | Evidence graph UI | P4 | T15, T17 |
| T21 | Trust report panel | P4 | T18 |
| T22 | Benchmark dashboard | P4 | T19 |
| T23 | Prompt-injection hardening: treat retrieved text as untrusted, add tests | P2 | T13 |
| T24 | Persist evaluation runs, per-case results, and run history | P1 | T19 |

## Wave 5: Demo readiness

| ID | Ticket | Owner | Depends on |
|---|---|---|---|
| T25 | Run benchmark, record real results, write evaluation methodology doc | P5 | T19 |
| T26 | Loading/error states, version/date metadata display | P4 | T20, T21 |
| T27 | Setup docs, one-command Docker start, architecture doc | P1 | T24 |
| T28 | Demo script, rehearsal, fallback recording | P5 | T25, T26 |

## Post-hackathon (Backlog only, unassigned)

| ID | Ticket |
|---|---|
| T29 | Counterfactual verification |
| T30 | Human review workflow with auth and audit log |
| T31 | Continuous monitoring and change-impact reports |
