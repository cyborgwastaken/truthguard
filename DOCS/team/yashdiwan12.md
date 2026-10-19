# yashdiwan12: The Website (Frontend)

Read the [team guide](README.md) first for the ticket loop (branch, commit, PR, board).

## Your role in one paragraph

You build everything a judge or user actually sees. TruthGuard's strength is that it shows its evidence, so your screens matter: the answer, its sources, the conflict, and why it decided what it did. The backend does not exist yet when you start, so you build against agreed data shapes and fake data, then connect to the real API when it is ready.

## Your tickets

| Ticket | Issue | Wave | Start when |
|---|---|---|---|
| T04 Frontend scaffold | #5 | 1 | Now (Ready) |
| T11 Chat UI and document list/upload | #12 | 2 | T04 and T06 are Done |
| T17 Answer view with citations and conflict comparison | #18 | 3 | T11 and T14 are Done |
| T20 Evidence graph UI | #21 | 4 | T15 and T17 are Done |
| T21 Trust report panel | #22 | 4 | T18 is Done |

## Tech and layout

React + TypeScript, built with Vite. All your files live in `FRONTEND/`. Suggested layout:

```text
FRONTEND/src/
  api/          # functions that call the backend
  components/   # small reusable pieces
  features/     # chat/, documents/, answer/, evidence-graph/, trust-report/
  types/        # TypeScript types that mirror the backend models
```

The backend runs at `http://localhost:8000` during development. Put that URL in one place (`import.meta.env.VITE_API_URL`) so it is easy to change.

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

**Data you will call (agreed with cyborgwastaken, shapes defined in `AGENT/truthguard_agent/schemas/models.py`):**
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
1. Wait for iamsarik to post the graph data shape on issue #16, then write matching types.
2. Start simple: a nested list (claim -> its supporting / contradicting / context passages). A graph library is optional; a clear list is fine and faster.
3. Style relations differently: supports, contradicts, context. Make unresolved conflicts stand out.
4. Clicking a passage opens it in the same side panel as T17.
5. Commit, push, PR (`Closes #21`).

**Done when:** every displayed claim shows its evidence, or "no evidence found".

---

## T21: Trust report panel

**Goal:** display iamsarik's trust report.

**Rules:**
1. Show each dimension **separately** with its name, value, and a short explanation of how it is computed (an info tooltip is good).
2. **Never** invent a single overall percentage.
3. Show "unknown" where the backend says unknown.
4. Make conflict status prominent. High coverage does not cancel a conflict.
5. Commit, push, PR (`Closes #22`).

**Done when:** all dimensions render for real answers, including those with unknown values.

## While you wait

Until T04 is merged you are unblocked. After that, Wave 2 needs the backend `/documents` endpoint (T06). Build your screens with mock data in the meantime, and review teammates' PRs.
