# Role 1: Backend and Database

Read the [team guide](README.md) first for the ticket loop (branch, commit, PR, board).

**Primary developer:** @cyborgwastaken  
**Secondary developer(s):** @yashdiwan12

## What this role is

You own the web API and the database. The AGENT package contains the logic; you store its data, expose it over HTTP, and make it reliable. The frontend developers depend on your endpoints, so announce the data shapes early and keep them stable.

## Tickets in this role

| Ticket | Issue | Wave | Start when |
|---|---|---|---|
| T03 Postgres, models and migrations | #4 | 1 | Now |
| T06 POST/GET /documents | #7 | 2 | T02 and T03 are Done |
| T14 POST /questions and GET /answers/{id} | #15 | 3 | T13 is Done |
| T24 Persist evaluation runs | #25 | 4 | T19 is Done |
| T27 Setup docs and one-command start | #28 | 5 | T24 is Done |

The primary developer does the work and opens the PRs. The secondary developer(s) read the PRs, help when the primary is stuck, and take a ticket over if asked on the issue. Do not start someone else's ticket without saying so on the issue first.

---

## T03: Postgres, models and migrations

**Goal:** a database that starts with one command, with tables for everything the system stores.

**Where:** `OPS/docker-compose.yml`, `BACKEND/app/db/` (models, session), `BACKEND/alembic/` (migrations).

**Steps:**
1. Branch `t03-database`.
2. Add `OPS/docker-compose.yml` with a Postgres 16 service (use the image `pgvector/pgvector:pg16` so vector search is possible later), a named volume, and the credentials from `BACKEND/app/config.py` (`truthguard` / `truthguard` / db `truthguard`).
3. Add `sqlalchemy>=2`, `alembic` and `psycopg[binary]` to `BACKEND/requirements.txt`.
4. Create SQLAlchemy models in `BACKEND/app/db/models.py` that mirror the Pydantic records in `AGENT/truthguard_agent/schemas/models.py`: `documents`, `chunks`, `answers`, `claims`, `evidence_links`. Keep `document_id` and `chunk_id` as the primary keys (stable IDs). Store missing metadata as NULL.
5. Add an Alembic migration that creates the tables. Test with `alembic upgrade head` on a fresh database, then `alembic downgrade base`.
6. Add a test that creates a Document row with missing metadata and reads it back with the NULLs intact.
7. Document `docker compose -f OPS/docker-compose.yml up -d` in `BACKEND/README.md`.
8. Commit, push, PR (`Closes #4`).

**Done when:** one command starts Postgres, the migration applies and rolls back cleanly, and the test passes.

---

## T06: POST/GET /documents

**Goal:** upload and list documents through the API, chunking them on the way in.

**Where:** `BACKEND/app/api/documents.py` and `BACKEND/tests/test_documents.py`. Register the router in `BACKEND/app/main.py`.

**Steps:**
1. Wait until T02 (chunking) and T03 (database) are Done, then `git pull`.
2. `POST /documents` accepts a `DocumentIn`, stores the document, calls the chunker from T02, and stores the chunks.
3. Re-uploading the same `document_id` with identical content changes nothing and returns the existing record. The same `document_id` with different content returns `409` for now (versioning comes later).
4. `GET /documents` lists documents with their metadata (unknown values stay `null`). `GET /documents/{document_id}` returns one document with its chunks.
5. Return clear errors: `422` for invalid input, `404` for unknown IDs.
6. Test with FastAPI's `TestClient`: create, duplicate, conflict, list, get, not found.
7. Commit, push, PR (`Closes #7`).

**Done when:** the Role 4 frontend can upload and list documents against the real API.

---

## T14: POST /questions and GET /answers/{id}

**Goal:** the endpoint the chat page calls, storing every answer so it can be inspected later.

**Where:** `BACKEND/app/api/questions.py`, `BACKEND/app/api/answers.py`, tests in `BACKEND/tests/`.

**Steps:**
1. Wait for T13 (orchestrator), then `git pull`.
2. `POST /questions` takes a `QuestionIn`, calls the orchestrator, saves the answer, claims and evidence links, and returns the `FinalAnswer`.
3. `GET /answers/{answer_id}` returns a saved answer with its claims and evidence links.
4. **A failed verification is not a server error.** If the orchestrator reports `verification_failed`, return that status in a normal response so the UI can show it. Reserve `500` for real bugs.
5. Never return a stack trace to the client.
6. Test with a fake orchestrator for every status: resolved, conflict_unresolved, insufficient_evidence, verification_failed.
7. Commit, push, PR (`Closes #15`).

**Done when:** a question sent to the API returns a saved, retrievable answer in every status.

---

## T24: Persist evaluation runs

**Goal:** store benchmark runs so the dashboard can compare them later.

**Where:** `BACKEND/app/db/models.py` (new tables), `BACKEND/app/api/evaluations.py`, a new Alembic migration.

**Steps:**
1. Wait for T19 (runner) and read the shape of its result object.
2. Add tables `evaluation_runs` (run id, configuration name, dataset version, model, prompt version, timestamp, summary metrics as JSON) and `evaluation_case_results` (run id, case id, retrieved chunk ids, answer, status, correct yes/no, latency).
3. Endpoints: `POST /evaluations/runs` (start a run and save it), `GET /evaluations/runs` (list), `GET /evaluations/runs/{run_id}` (summary plus per-case rows).
4. Every summary number must be reproducible from the per-case rows. Add a test that recomputes one metric from stored rows.
5. Commit, push, PR (`Closes #25`).

**Done when:** a run can be saved and read back, and the dashboard (T22) has what it needs.

---

## T27: Setup docs and one-command start

**Goal:** a new person can clone the repo and run everything by following the docs.

**Where:** root `README.md`, `DOCS/architecture.md`, and the existing `OPS/` Docker Compose.

**Steps:**
1. Start from the list of problems you noted during your own setup.
2. Write exact copy-paste commands for: install, database start, load the sample documents, run the backend, run the frontend, run all tests.
3. Test the instructions on a **clean clone in a new folder** (or a different computer). Fix any step that fails.
4. Write `DOCS/architecture.md`: the folder map, the four-stage pipeline, and where each ticket's code lives (use the diagram in the roadmap as a base).
5. Commit, push, PR (`Closes #28`).

**Done when:** someone who has never seen the project can get it running without asking for help.
