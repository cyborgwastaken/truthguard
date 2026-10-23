# Project Progress

Current state of the TruthGuard build. The status section below is **generated from the GitHub board**; do not edit it by hand. Regenerate it after each merge:

```bash
python3 OPS/github/update_progress.py
```

The notes section at the bottom is written by hand: decisions, reasons and open questions.

## Where things stand (hand-written, 2026-10-23)

**Working mode since 2026-10-23:** the demo moved up to the next day, so all work is on the `dev` branch, in phases taken from the two roadmaps, with no tickets, pull requests or board updates. `main` is untouched (its last commit is the T12 merge). The generated board status further down therefore **no longer matches reality**: it still shows tickets as not started that are built on `dev`. Trust this section.

| Phase | What it is (roadmap) | State |
|---|---|---|
| 1. Verification pipeline | retrieve, draft, critic, resolve with explicit failure states; the critic and resolver see only the documents the answer cites; one verdict per conflict | built and tested |
| 2. API and answer view | `POST /questions`, `GET /answers/{id}`, stored answers with a replayable record; chat with citations that open the source passage, side-by-side conflict comparison, "statements not used"; replay mode | built and tested |
| 3. Benchmark and red-team lab | 18 labeled cases, 14 metrics with numerators and denominators, runner for three setups, CLI, `/evaluations` API, Benchmark tab | built and tested; **the benchmark has not been run, so there are no results yet** |
| 4. Evidence graph and trust report | graph of claims, sources, supersession and conflicts; trust report with separate dimensions and no single score | built and tested |
| 5. Demo readiness | `OPS/start.sh`, `stop.sh`, `reset_answers.sh`; rehearsal command `python -m app.demo`; prompt-injection tests; demo script; methodology | built and tested; **rehearsal and the screen recording are still to do** |

**Tests:** 381 agent, 85 backend, 22 ops; the frontend builds with no lint warnings. A fresh clone of `dev` started with the one command and passed everything (checked before the real-model fixes of 2026-10-23, which were tested in place).

**Checked against the real model (Groq `openai/gpt-oss-120b`, temperature 0, 2026-10-23):** all 18 labeled cases return the expected status, one run each, and replaying the recorded replies reproduces the same 18 with no network and no key. This shows the statuses only. It does not show that the answer text has the right facts, it is one run per case so stability is not measured, and the three-way comparison with the plain baseline has not been run. Before the critic prompt was tightened (below), C11 (managers versus interns) came back as a false conflict.

**What the old tickets became:** T13 orchestrator, T14 API, T15 evidence graph, T16 dataset and metrics, T17 answer view, T18 trust report, T19 runner (built, not run), T20 graph view, T21 trust panel, T22 dashboard, T27 setup guide and one-command start, and T28 demo script (written, not rehearsed) are all done on `dev`. T23 is reduced to the injection tests. T25 has its methodology written but no results. T26 is partly done (loading and error states exist). T24 (store runs in the database) is cut: runs are JSON files. T29 to T31 are not started.

**Still to do, in order:** rehearse the demo and fix what the real model gets wrong (`python -m app.demo --repeats 3`); run the benchmark and read the results before presenting (`python -m app.benchmark`); record a screen video; later, merge `dev` into `main` through a pull request and bring the board and the role docs up to date.

<!-- BEGIN GENERATED (OPS/github/update_progress.py) -->
## Status (generated 2026-10-22)

**12 of 32 tickets done.** Done 12 · In review 0 · In progress 0 · Ready 2 · Backlog 18

### Ready to start

- #13 T12: Critic agent (@yashdiwan12)
- #17 T16: Benchmark dataset v1 and metric functions (@dhruvt293)

### In flight

- nothing in flight

### Open pull requests

- none

### All tickets

| Ticket | Issue | Title | Owner | Status | Waiting on |
|---|---|---|---|---|---|
| **Wave 0: Scaffold** | | | | | |
| T00 | #1 | Repo scaffold, shared schemas, /health | @cyborgwastaken | Done | - |
| **Wave 1: Foundation** | | | | | |
| T01 | #2 | Fictional corpus with labeled cases | @dhruvt293 | Done | - |
| T02 | #3 | Ingestion: normalize, chunk, hash | @AshwaniArya2005 | Done | - |
| T03 | #4 | Postgres, models and migrations | @cyborgwastaken | Done | - |
| T04 | #5 | Frontend scaffold (Vite + React + TS) | @cyborgwastaken | Done | - |
| T05 | #6 | Resolver rules design doc | @yashdiwan12 | Done | - |
| **Wave 2: Core pipeline** | | | | | |
| T06 | #7 | POST/GET /documents | @cyborgwastaken | Done | - |
| T07 | #8 | Keyword/full-text retriever | @AshwaniArya2005 | Done | - |
| T08 | #9 | Synthesizer with claim-level citations | @AshwaniArya2005 | Done | - |
| T09 | #10 | Resolver engine | @yashdiwan12 | Done | - |
| T10 | #11 | Baseline RAG | @dhruvt293 | Done | - |
| T11 | #12 | Chat UI and document list/upload | @iamsarik | Done | - |
| **Wave 3: Verification** | | | | | |
| T12 | #13 | Critic agent | @yashdiwan12 | Ready | - |
| T13 | #14 | Orchestrator | @AshwaniArya2005 | Backlog | T12 |
| T14 | #15 | POST /questions and GET /answers/{id} | @cyborgwastaken | Backlog | T13 |
| T15 | #16 | Evidence graph assembler and endpoint | @yashdiwan12 | Backlog | T12, T14 |
| T16 | #17 | Benchmark dataset v1 and metric functions | @dhruvt293 | Ready | - |
| T17 | #18 | Answer view with citations and conflict comparison | @iamsarik | Backlog | T14 |
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

- **2026-10-23, the critic prompt is stricter (critic-v2) because the real model reported false conflicts.** On the first real run, C11 (managers versus interns) became `conflict_unresolved`: the synthesizer cited the general remote-work policy for one claim, which brought it into scope, and the critic reported "managers two days versus employees three days" (a specific-group rule against a general one) and confused days in the office with days remote. The prompt now says that a rule for one group against a rule for everyone is layered on purpose and is not a contradiction, that passages measuring different things are not comparable, and to stay silent when unsure. After the change all 18 cases matched, including the three real conflicts, which a stricter prompt could have started to miss. The prompt version is recorded with every answer.
- **2026-10-23, Groq rate limits are waited out, up to 45 seconds.** The free tier allows 8,000 tokens per minute and one question uses about 5,000 to 7,000 over three model calls, so a second question within a minute was refused with "try again in 17 s". `GroqLLM` now waits as long as Groq says (header, else the message text) and retries up to three times; a longer wait, such as a daily cap, fails at once with the message. In practice a question after another can take 30 to 45 seconds, and a full benchmark takes many minutes; it resumes from its cache if interrupted. A daily token cap may still stop a large run.
- **2026-10-23, an answer is the answer plus its whole verification record.** `POST /questions` returns and stores `answer` and `verification` (every retrieved passage with metadata and whether it was in scope, each conflict with its own verdict and winner, stale sources, the role of each claim, timings), so any answer can be shown again exactly as it was produced, and the evidence graph and trust report are computed from it. This needed one migration (`answers.as_of`, `answers.details`).
- **2026-10-23, a failed or unfinished check is never a clean one.** The critic's success is recorded explicitly (`critic_ok`): an empty list of findings means "nothing found" only when the critic finished. The first version recorded the stage before checking for failure, so a failed critic read as "no conflicts, OK" in the trust report; a test found it. Claims are marked current, superseded, a side of an unresolved conflict, or unsupported, and only current and conflict-side claims reach the answer text.
- **2026-10-23, the trust report has no single score.** The roadmap forbids an invented "92% trustworthy". Six dimensions (evidence coverage, citation support, conflicts, freshness, provenance, verification status) each give their numerator, denominator, a level (ok, attention, problem or unknown) and a sentence. High coverage can never hide an unresolved conflict: that is its own warning.
- **2026-10-23, offline fallback for the demo.** Recorded real model replies (45 entries, fictional documents only) are in `AGENT/datasets/recorded/replies.jsonl`. `TRUTHGUARD_LLM_MODE=replay` runs the app from them with no key; a replayed answer carries a "Replayed recording" tag, and a prompt with no recording fails visibly as `verification_failed`. `OPS/start.sh` chooses replay by itself when there is no key but there are recordings.
- **2026-10-23, work moved to the `dev` branch without tickets.** See the section at the top. Cuts: storing benchmark runs in the database (T24), the "ask as of" date picker, streamed answers, and a full injection red-team suite (kept as tests).
- **2026-10-22, T11 used a mock for `POST /questions` until the real endpoint existed.** Done on 2026-10-23: the mock and its note are removed and the chat calls the real endpoint.
- **2026-10-22, the baseline RAG (T10) is deliberately plain.** It uses search only (`expand_related=False`), so it does not get the supersession expansion TruthGuard adds. A failed model call is `verification_failed`, never `insufficient_evidence`, so the benchmark can count failures separately from correct abstentions. It shares the synthesizer's prompt with the full pipeline, so the comparison isolates what the critic and the resolver add; the evaluation methodology must say so.
- **2026-10-22, resolver (T09) follows `DOCS/resolver-rules.md`, including closure under supersession.** Before a conflict is judged, every retrieved document linked to a listed source by an applicable supersession joins it, so the superseding document takes part even if the critic did not list it (D11: a conflict whose every side is superseded resolves for the superseding document). A contradiction citing an unretrieved source, or naming fewer than two sources, is `conflict_unresolved`. Checked against an independent reference implementation on 90,000 random cases.
- **2026-10-20, the language model is Groq, and Python 3.12 is the minimum.** `GroqLLM` (the `groq` SDK needs Python 3.10+; the project lead approved 3.12). The key is the environment variable `GROQ_API_KEY`, never a file; the model name comes from `TRUTHGUARD_LLM_MODEL` (Groq retires models, so keep it in configuration). Only the fictional fixtures go through the API. Everyone recreates their venv with `python3.12` (see `DOCS/setup.md`).
- **2026-10-20, retrieval (T07) never abstains.** Search is OR-style ranked by `ts_rank`, and `retrieve()` adds the documents that supersede or are superseded by a hit, following chains for up to 5 rounds. For the "no evidence" cases (C08 to C10) it still returns 8 to 11 low-scoring irrelevant passages, so "insufficient evidence" must be decided downstream (T13/T08), for example from the synthesizer returning no claims.
- **2026-10-20, T04 covered by the project lead.** iamsarik is unavailable for now, so cyborgwastaken took T04 (issue #5, noted on the issue). iamsarik is back and delivered T11.
- **2026-10-20, frontend needs Node 20.19 or newer.** Vite 8 requires it; plain Node 20.x fails.
- **2026-10-20, `main` is protected; squash merges only; no `dev` branch.** Every change goes through a PR approved by cyborgwastaken (CODEOWNERS). Squash gives one commit per ticket. A `dev` branch was rejected because every ticket would merge twice and the review value would not increase. Known-good versions are tagged instead (`demo-1`). Reasoning in `DOCS/maintainer-guide.md`.
- **2026-10-20, admin enforcement is off on purpose.** The lead cannot approve their own PRs, so they merge those with the admin override. Side effect: the lead can also push straight to `main`; the rule is to not do it. One empty test commit (`067640f`, "protection test") landed on `main` that way while testing; it changes nothing.
- **2026-10-20, old pip breaks the install.** pip 21.x (the macOS Python 3.9 default) cannot install `../AGENT` in editable mode. `DOCS/setup.md` tells people to run `pip install --upgrade pip` first. A `setup.py` shim was tried and did not work, so it was removed.
- **2026-10-20, Postgres runs on host port 5433.** Port 5432 is often taken by a local Postgres. Override with `TRUTHGUARD_DB_PORT`.
- **2026-10-20, `answer_citations` table added in T03.** Not in the ticket, but `FinalAnswer.citations` needs storage for T14. `supersedes_document_id` is deliberately not a foreign key because the superseded document may arrive later or never.
- **2026-10-19, ownership by role.** Five roles with a primary and secondary developer each (table in `DOCS/backlog.md` and `DOCS/team/README.md`). A secondary supports and reviews; only the primary opens PRs unless a ticket is handed over on its issue.
- **2026-10-19, no co-author or AI attribution lines in commit messages.** Project lead rule, applies to everyone.
