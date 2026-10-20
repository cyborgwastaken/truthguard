# Project Progress

Current state of the TruthGuard build. The status section below is **generated from the GitHub board**; do not edit it by hand. Regenerate it after each merge:

```bash
python3 OPS/github/update_progress.py
```

The notes section at the bottom is written by hand: decisions, reasons and open questions.

<!-- BEGIN GENERATED (OPS/github/update_progress.py) -->
## Status (generated 2026-10-20)

**3 of 32 tickets done.** Done 3 · In review 1 · In progress 1 · Ready 1 · Backlog 26

### Ready to start

- #6 T05: Resolver rules design doc (@yashdiwan12)

### In flight

- #3 T02: Ingestion: normalize, chunk, hash (@AshwaniArya2005), in progress
- #5 T04: Frontend scaffold (Vite + React + TS) (@cyborgwastaken), in review

### Open pull requests

- #37 T04: Frontend scaffold (Vite + React + TS) (@cyborgwastaken): review required
- #36 T02 ingestion (@AshwaniArya2005): review required

### All tickets

| Ticket | Issue | Title | Owner | Status | Waiting on |
|---|---|---|---|---|---|
| **Wave 0: Scaffold** | | | | | |
| T00 | #1 | Repo scaffold, shared schemas, /health | @cyborgwastaken | Done | - |
| **Wave 1: Foundation** | | | | | |
| T01 | #2 | Fictional corpus with labeled cases | @dhruvt293 | Done | - |
| T02 | #3 | Ingestion: normalize, chunk, hash | @AshwaniArya2005 | In progress | - |
| T03 | #4 | Postgres, models and migrations | @cyborgwastaken | Done | - |
| T04 | #5 | Frontend scaffold (Vite + React + TS) | @cyborgwastaken | In review | - |
| T05 | #6 | Resolver rules design doc | @yashdiwan12 | Ready | - |
| **Wave 2: Core pipeline** | | | | | |
| T06 | #7 | POST/GET /documents | @cyborgwastaken | Backlog | T02 |
| T07 | #8 | Keyword/full-text retriever | @AshwaniArya2005 | Backlog | T02 |
| T08 | #9 | Synthesizer with claim-level citations | @AshwaniArya2005 | Backlog | T07 |
| T09 | #10 | Resolver engine | @yashdiwan12 | Backlog | T05 |
| T10 | #11 | Baseline RAG | @dhruvt293 | Backlog | T07 |
| T11 | #12 | Chat UI and document list/upload | @iamsarik | Backlog | T04, T06 |
| **Wave 3: Verification** | | | | | |
| T12 | #13 | Critic agent | @yashdiwan12 | Backlog | T08 |
| T13 | #14 | Orchestrator | @AshwaniArya2005 | Backlog | T08, T09, T12 |
| T14 | #15 | POST /questions and GET /answers/{id} | @cyborgwastaken | Backlog | T13 |
| T15 | #16 | Evidence graph assembler and endpoint | @yashdiwan12 | Backlog | T12, T14 |
| T16 | #17 | Benchmark dataset v1 and metric functions | @dhruvt293 | Backlog | T10 |
| T17 | #18 | Answer view with citations and conflict comparison | @iamsarik | Backlog | T11, T14 |
| **Wave 4: Showcase** | | | | | |
| T18 | #19 | Trust report builder and endpoint | @yashdiwan12 | Backlog | T15 |
| T19 | #20 | Benchmark runner (3 configs) | @dhruvt293 | Backlog | T13, T16 |
| T20 | #21 | Evidence graph UI | @iamsarik | Backlog | T15, T17 |
| T21 | #22 | Trust report panel | @iamsarik | Backlog | T18 |
| T22 | #23 | Benchmark dashboard | @iamsarik | Backlog | T19 |
| T23 | #24 | Prompt-injection hardening | @AshwaniArya2005 | Backlog | T13 |
| T24 | #25 | Persist evaluation runs | @cyborgwastaken | Backlog | T19 |
| **Wave 5: Demo readiness** | | | | | |
| T25 | #26 | Record real results and evaluation methodology doc | @dhruvt293 | Backlog | T19 |
| T26 | #27 | Loading/error states and metadata display | @iamsarik | Backlog | T20, T21 |
| T27 | #28 | Setup docs and one-command start | @cyborgwastaken | Backlog | T24 |
| T28 | #29 | Demo script, rehearsal, fallback recording | @dhruvt293 | Backlog | T25, T26 |
| **Post-hackathon** | | | | | |
| T29 | #30 | Counterfactual verification | @unassigned | Backlog | - |
| T30 | #31 | Human review workflow with auth and audit log | @unassigned | Backlog | - |
| T31 | #32 | Continuous monitoring and change-impact reports | @unassigned | Backlog | - |
<!-- END GENERATED -->

## Decisions and notes

Newest first. One entry per decision, with the reason. Add an entry whenever something is decided that a newcomer (or an AI agent) could not work out from the code.

- **2026-10-20, T02 and T06/T07.** PR #36 (T02 ingestion) is the next blocker: T06 and T07 both wait on it. Keep an eye on it; the generated table shows what is waiting.
- **2026-10-20, T04 covered by the project lead.** iamsarik is unavailable for now, so cyborgwastaken took T04 (issue #5, noted on the issue). When iamsarik returns, T11 and later frontend tickets go back to them.
- **2026-10-20, frontend needs Node 20.19 or newer.** Vite 8 requires it; plain Node 20.x fails.
- **2026-10-20, `main` is protected; squash merges only; no `dev` branch.** Every change goes through a PR approved by cyborgwastaken (CODEOWNERS). Squash gives one commit per ticket. A `dev` branch was rejected because every ticket would merge twice and the review value would not increase. Known-good versions are tagged instead (`demo-1`). Reasoning in `DOCS/maintainer-guide.md`.
- **2026-10-20, admin enforcement is off on purpose.** The lead cannot approve their own PRs, so they merge those with the admin override. Side effect: the lead can also push straight to `main`; the rule is to not do it. One empty test commit (`067640f`, "protection test") landed on `main` that way while testing; it changes nothing.
- **2026-10-20, old pip breaks the install.** pip 21.x (the macOS Python 3.9 default) cannot install `../AGENT` in editable mode. `DOCS/setup.md` tells people to run `pip install --upgrade pip` first. A `setup.py` shim was tried and did not work, so it was removed.
- **2026-10-20, Postgres runs on host port 5433.** Port 5432 is often taken by a local Postgres. Override with `TRUTHGUARD_DB_PORT`.
- **2026-10-20, `answer_citations` table added in T03.** Not in the ticket, but `FinalAnswer.citations` needs storage for T14. `supersedes_document_id` is deliberately not a foreign key because the superseded document may arrive later or never.
- **2026-10-19, ownership by role.** Five roles with a primary and secondary developer each (table in `DOCS/backlog.md` and `DOCS/team/README.md`). A secondary supports and reviews; only the primary opens PRs unless a ticket is handed over on its issue.
- **2026-10-19, no co-author or AI attribution lines in commit messages.** Project lead rule, applies to everyone.
