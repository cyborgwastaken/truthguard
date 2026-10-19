# Role 4: Frontend

Read the [team guide](README.md) first for the ticket loop (branch, commit, PR, board).

**Primary developer:** @iamsarik  
**Secondary developer(s):** @cyborgwastaken

## What this role is

You build everything a judge or user actually sees. TruthGuard's strength is that it shows its evidence, so your screens matter: the answer, its sources, the conflict, and why it decided what it did. The backend does not exist yet when you start, so you build against agreed data shapes and fake data, then connect to the real API when it is ready. You also finish the polish: the benchmark dashboard, loading and error states.

## Tickets in this role

| Ticket | Issue | Wave | Start when |
|---|---|---|---|
| T04 Frontend scaffold | #5 | 1 | Now |
| T11 Chat UI and document list/upload | #12 | 2 | T04 and T06 are Done |
| T17 Answer view with citations and conflict comparison | #18 | 3 | T11 and T14 are Done |
| T20 Evidence graph UI | #21 | 4 | T15 and T17 are Done |
| T21 Trust report panel | #22 | 4 | T18 is Done |
| T22 Benchmark dashboard | #23 | 4 | T19 is Done |
| T26 Loading/error states and metadata display | #27 | 5 | T20 and T21 are Done |

The primary developer does the work and opens the PRs. The secondary developer(s) read the PRs, help when the primary is stuck, and take a ticket over if asked on the issue. Do not start someone else's ticket without saying so on the issue first.

## Tech and layout

React + TypeScript, built with Vite. All your files live in `FRONTEND/`.

```text
FRONTEND/src/
  api/          # functions that call the backend
  components/   # small reusable pieces
  features/     # chat/, documents/, answer/, evidence-graph/, trust-report/, evaluations/
  types/        # TypeScript types that mirror the backend models
```

The backend runs at `http://localhost:8000` during development. Put that URL in one place (`import.meta.env.VITE_API_URL`).

---

## T04: Frontend scaffold

**Goal:** an app that starts, has a basic layout, and can talk to the backend's `/health` endpoint.

**Steps:**
1. Branch `t04-frontend-scaffold`.
2. From the repo root:
   ```bash
   cd FRONTEND
   npm create vite@latest . -- --template react-ts
   npm install
   npm run dev
   ```
   Open the URL it prints (usually http://localhost:5173). You should see the starter page.
3. Remove the starter demo content. Create the folders from the layout above.
4. Make a simple layout shell: a top bar with the name "TruthGuard" and an area for pages (Chat, Documents).
5. Create `src/api/client.ts` with a `getHealth()` function that calls `GET /health` and returns the JSON. Show "Backend: connected" or "Backend: offline" in the top bar.
6. To test it, start the backend in another terminal: `cd BACKEND && uvicorn app.main:app --reload`.
7. Add `FRONTEND/README.md` with the run commands.
8. Commit, push, PR (`Closes #5`). Do **not** commit `node_modules/` (it is already ignored).

**Done when:** `npm run dev` works, and the top bar reflects whether the backend is up.

---

## T11: Chat UI and document list/upload

**Goal:** a user can upload a document, see the document list, ask a question, and see a plain answer.

**Data you will call (agreed with the Role 1 developer, shapes defined in `AGENT/truthguard_agent/schemas/models.py`):**
- `POST /documents`: create a document (fields: `document_id`, `title`, `content`, `version`, `effective_date`, ...)
- `GET /documents`: list documents
- `POST /questions` with `{ "question": "..." }`: returns a final answer

**Steps:**
1. Write TypeScript types in `src/types/` that mirror `DocumentIn`, `Document` and `FinalAnswer`.
2. While the backend endpoints are not ready, use a **mock**: a function returning hard-coded data that you swap for the real call later. Keep that swap in `src/api/` only.
3. Documents page: a table of documents (title, version, effective date, authority) and an upload form. Missing fields must show "unknown", not a blank or a made-up value.
4. Chat page: a text box and a message list. Show a loading state while waiting and an error message if the call fails.
5. Show the answer text and its status (`resolved`, `conflict_unresolved`, `insufficient_evidence`, `verification_failed`) as a clearly visible badge.
6. Commit, push, PR (`Closes #12`). In the PR, add a screenshot.

**Done when:** you can upload a document and ask a question end to end with the real API.

---

## T17: Answer view with citations and conflict comparison

**Goal:** make the evidence visible, which is TruthGuard's whole point.

**Steps:**
1. Under each answer show its **citations** as clickable chips (document title + version).
2. Clicking a citation opens the full source passage in a side panel, with the document's version, effective date and authority.
3. If the answer status is `conflict_unresolved` or conflicts were detected, show a **side-by-side comparison**: left passage vs right passage, each labelled with document, version and date, plus the reason text from the backend (`resolution_reason`).
4. For `insufficient_evidence`, show a clear "The documents don't contain enough information" message. Do not show an empty answer.
5. Use distinct colours/icons for resolved, unresolved and insufficient, and make sure they are readable (not colour-only: add a text label).
6. Commit, push, PR (`Closes #18`) with screenshots of all three states.

**Done when:** all three demo situations (superseded, unresolved, insufficient) look right and are understandable at a glance.

---

## T20: Evidence graph UI

**Goal:** show how claims connect to passages.

**Steps:**
1. Wait for the Role 3 developer to post the graph data shape on issue #16, then write matching types.
2. Start simple: a nested list (claim -> its supporting / contradicting / context passages). A graph library is optional; a clear list is fine and faster.
3. Style relations differently: supports, contradicts, context. Make unresolved conflicts stand out.
4. Clicking a passage opens it in the same side panel as T17.
5. Commit, push, PR (`Closes #21`).

**Done when:** every displayed claim shows its evidence, or "no evidence found".

---

## T21: Trust report panel

**Goal:** display the trust report built in T18.

**Rules:**
1. Show each dimension **separately** with its name, value, and a short explanation of how it is computed (an info tooltip is good).
2. **Never** invent a single overall percentage.
3. Show "unknown" where the backend says unknown.
4. Make conflict status prominent. High coverage does not cancel a conflict.
5. Commit, push, PR (`Closes #22`).

**Done when:** all dimensions render for real answers, including those with unknown values.

---

## T22: Benchmark dashboard

**Goal:** a page on the website that compares the three systems (baseline RAG, RAG + critic, full TruthGuard) and lets you click into any failed case.

**Where:** `FRONTEND/src/features/evaluations/`. Reuse the types and API layout set up in T04.

**Steps:**
1. Wait for T19. Read the results file format the runner (T19) produces and the endpoint (`GET /evaluations/runs/{run_id}`) the backend (T24) adds.
2. Build a summary table: rows = metrics (retrieval recall, contradiction precision/recall, citation support rate, correct abstention rate, resolution accuracy, latency), columns = the three systems.
3. Show the dataset version and the run configuration (model, prompt version, time) so results can be reproduced.
4. Build a case list with filters (category, pass/fail). Clicking a case shows the question, retrieved passages, the system's answer, and the expected result.
5. Only show numbers that exist in the data. No rounding up, no hand-typed values.
6. Commit, push, PR (`Closes #23`) with a screenshot.

**Done when:** every number on the page can be traced to per-case rows.

---

## T26: Loading/error states and metadata display

**Goal:** make the website feel finished and reliable.

**Where:** `FRONTEND/`. Announce on the issue which components you are touching, so you and your secondary developer do not edit the same files at the same time.

**Steps:**
1. Go through every page and every API call. For each, check the **loading** state (spinner or skeleton), the **error** state (a clear message and a retry button), and the **empty** state (e.g. no documents yet).
2. Show version, effective date and authority wherever a document appears; show "unknown" for missing values.
3. Test the unhappy paths: stop the backend and use the app; submit an empty question.
4. Check it on a narrow (phone-size) browser window.
5. Commit, push, PR (`Closes #27`).

**Done when:** you cannot find a screen that shows a blank page or an unexplained failure.
