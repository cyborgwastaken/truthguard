# dhruvt293: Dashboard, Documentation and Demo

Read the [team guide](README.md) first for the ticket loop (branch, commit, PR, board).

## Your role in one paragraph

You own how the project is finished and presented: the benchmark dashboard, the real measured results, the polish on the website, the setup instructions, and the demo. Your tickets come late (Waves 4 and 5), but a good demo is what people remember, so you start preparing early. You also act as the team's first "fresh user": if something is confusing to set up, that is a bug to write down.

## Your tickets

| Ticket | Issue | Wave | Start when |
|---|---|---|---|
| T22 Benchmark dashboard | #23 | 4 | T19 (benchmark runner) is Done |
| T25 Record real results and methodology doc | #26 | 5 | T19 is Done |
| T26 Loading/error states and metadata display | #27 | 5 | T20 and T21 are Done |
| T27 Setup docs and one-command start | #28 | 5 | T24 is Done |
| T28 Demo script, rehearsal, fallback recording | #29 | 5 | T25 and T26 are Done |

None of your tickets are in Wave 1, so start with the preparation below.

## Preparation while you wait (do these now)

These are not tickets, but they make your later work much easier.

1. Do the **one-time setup** in the [team guide](README.md) and make sure the existing tests pass. Write down every place you got stuck. That list becomes the base of T27.
2. Read both roadmaps in `DOCS/`.
3. Read the PRs as they come in (T01, T04, T05). You are allowed to comment with questions.
4. Draft an outline of the demo in `DOCS/demo-outline.md` (the three scenarios: superseded policy, unresolved conflict, insufficient evidence; see "Demo script" at the end of the initial roadmap). You will turn it into the real script in T28. This outline needs its own PR; ask cyborgwastaken to add a ticket for it, or include it in your T28 PR later.

---

## T22: Benchmark dashboard

**Goal:** a page on the website that compares the three systems (baseline RAG, RAG + critic, full TruthGuard) and lets you click into any failed case.

**Where:** `FRONTEND/src/features/evaluations/`. Coordinate with yashdiwan12, who set up the frontend (T04) and its types and API layout.

**Steps:**
1. Wait for T19. Read the results file format that AshwaniArya2005 produces and the endpoint (`GET /evaluations/runs/{run_id}`) cyborgwastaken adds.
2. Build a summary table: rows = metrics (retrieval recall, contradiction precision/recall, citation support rate, correct abstention rate, resolution accuracy, latency), columns = the three systems.
3. Show the dataset version and the run configuration (model, prompt version, time) so results can be reproduced.
4. Build a case list with filters (category, pass/fail). Clicking a case shows the question, retrieved passages, the system's answer, and the expected result.
5. Only show numbers that exist in the data. No rounding up, no hand-typed values.
6. Commit, push, PR (`Closes #23`) with a screenshot.

**Done when:** every number on the page can be traced to per-case rows.

---

## T25: Record real results and methodology doc

**Goal:** an honest write-up of how we tested and what we measured.

**Where:** `DOCS/evaluation-methodology.md` and `DOCS/results.md`.

**Steps:**
1. Run the benchmark (command documented by AshwaniArya2005 in T19) at least once on a clean checkout.
2. In the methodology doc explain: what the dataset contains and its categories, what each metric means (copy the formulas from the metric docstrings), what the three configurations are, and the limitations (small synthetic dataset, model outputs can vary between runs).
3. In `results.md` paste the real numbers from the dashboard or results file, with the date, dataset version and configuration.
4. **Do not claim improvement unless the numbers show it.** If TruthGuard does not win on a category, say so.
5. Commit, push, PR (`Closes #26`).

**Done when:** every figure in the docs matches a recorded run.

---

## T26: Loading/error states and metadata display

**Goal:** make the website feel finished and reliable.

**Where:** `FRONTEND/`. Work with yashdiwan12 to avoid editing the same files at the same time; announce on the issue which components you are touching.

**Steps:**
1. Go through every page and every API call. For each, check the **loading** state (spinner or skeleton), the **error** state (a clear message and a retry button), and the **empty** state (e.g. no documents yet).
2. Show version, effective date and authority wherever a document appears; show "unknown" for missing values.
3. Test the unhappy paths: stop the backend and use the app; submit an empty question.
4. Check it on a narrow (phone-size) browser window.
5. Commit, push, PR (`Closes #27`).

**Done when:** you cannot find a screen that shows a blank page or an unexplained failure.

---

## T27: Setup docs and one-command start

**Goal:** a new person can clone the repo and run everything by following the docs.

**Where:** root `README.md`, `DOCS/architecture.md`, and with cyborgwastaken, `OPS/` (Docker Compose).

**Steps:**
1. Start from the list of problems you noted during your own setup.
2. Write exact copy-paste commands for: install, database start, load the sample documents, run the backend, run the frontend, run all tests.
3. Test the instructions on a **clean clone in a new folder** (or a different computer). Fix any step that fails.
4. Write `DOCS/architecture.md`: the folder map, the four-stage pipeline, and where each ticket's code lives (use the diagram in the roadmap as a base).
5. Commit, push, PR (`Closes #28`).

**Done when:** someone who has never seen the project can get it running without asking for help.

---

## T28: Demo script, rehearsal, fallback recording

**Goal:** a demo that works every time.

**Steps:**
1. Turn your outline into `DOCS/demo-script.md`: for each of the five demo steps (see the initial roadmap, section 13) write the exact question to type, what should appear on screen, and what to say.
2. Run through the script on a clean start, at least three times. Note anything that varies between runs.
3. Prepare a fallback: record a screen video of a perfect run, and keep screenshots of each step in case the live demo fails.
4. Decide with the team who talks and who clicks.
5. Commit, push, PR (`Closes #29`).

**Done when:** the demo runs from a clean start and a recorded backup exists.
