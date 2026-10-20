# How We Work: Read This First

This guide is for everyone on the team. It explains the project, the board, and the exact steps to take one ticket from start to finish. Your personal doc (in this folder) then lists your tickets one by one.

## 1. What we are building

TruthGuard answers questions from a set of documents and shows its evidence. If two documents disagree, it says so. If a document is outdated, it says so. If it cannot find the answer, it says "I don't know" instead of guessing.

The system has four parts that run in order:

```text
Question -> Retriever -> Synthesizer -> Critic -> Resolver -> Answer + evidence
            (find       (draft an      (look for  (decide who
             passages)   answer with    conflicts) wins, if anyone)
                         citations)
```

Read these two documents once (30 minutes) so the ticket names make sense:
- [Initial roadmap](../truthguard_intital_roadmap.md)
- [Expansion roadmap](../truthguard_expansion_roadmap.md)

## 2. The repo map

| Folder | What lives there | Who mostly works here |
|---|---|---|
| `AGENT/` | The "brain": data models (`schemas/`), retriever, synthesizer, critic, resolver, test datasets (`datasets/`) | Everyone except frontend |
| `BACKEND/` | The web API (FastAPI) that the frontend calls | cyborgwastaken |
| `FRONTEND/` | The website (React) | yashdiwan12, dhruvt293 |
| `OPS/` | Docker, database setup, GitHub scripts | cyborgwastaken, dhruvt293 |
| `DOCS/` | Documentation | Everyone |

Do not put files at the top level of the repo. If you are not sure where something goes, ask.

## 3. The board

Open the project board: GitHub -> `cyborgwastaken` -> Projects -> **Virtusa TruthGuard**.

Every ticket is a card. A card moves left to right:

| Column | Meaning | Who moves it |
|---|---|---|
| **Backlog** | Not ready yet; it waits for other tickets | automatic order, see "Depends on" |
| **Ready** | You can start now | **automatic**: when everything it depends on is merged (a comment on the issue tags you) |
| **In progress** | You are working on it | **automatic**: when you first push a branch named `tNN-...` (a draft PR also counts) |
| **In review** | Your PR is open and waiting for review | **automatic**: when you open the PR (it must say `Closes #N`); closing the PR without merging puts it back to In progress |
| **Done** | Reviewed, merged, finished | cyborgwastaken, after merging |

Each ticket (issue) tells you its **Depends on** list and a **Done when** line. If a ticket is still in Backlog, do not start it. The things it needs are not built yet.

Tickets are grouped into **waves**. Wave 1 first, then Wave 2, and so on. Within a wave, everyone works at the same time.

## 4. One-time setup (do this once)

1. Accept the GitHub invitation (check your email, or go to https://github.com/cyborgwastaken/truthguard/invitations).
2. Install: **Git**, **Python 3.12 or newer**, **Node.js 20.19 or newer** (frontend people), and **VS Code**.
3. Tell Git who you are:
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "your-github-email@example.com"
   ```
4. Clone the repo and set up Python:
   ```bash
   git clone https://github.com/cyborgwastaken/truthguard.git
   cd truthguard
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   cd BACKEND
   pip install -r requirements.txt  # run this from inside BACKEND, not the repo root
   cd ../AGENT && python -m pytest  # should say 6 passed
   ```
   If the tests pass, your setup works.

## 5. The ticket loop (do this for every ticket)

Pretend you are working on ticket **T01** (issue #2). Replace names as needed.

**Step 1: Check it is Ready.** Read the issue: description, Depends on, Done when. If anything is unclear, comment on the issue and ask before you start.

**Step 2: Nothing to do on the board.** The card moves to **In progress** by itself the first time you push your branch (step 7). That is why the branch name must start with the ticket number, like `t01-corpus`.

**Step 3: Get the latest code and make a branch.**
```bash
git checkout main
git pull
git checkout -b t01-corpus
```
Branch name = ticket id + a few words, lowercase, dashes. One branch per ticket. **Never work directly on `main`.**

**Step 4: Do the work.** Your personal doc says what to build and where the files go. Work in small pieces.

**Step 5: Test it.** If you wrote Python, write tests and run them:
```bash
cd AGENT && python -m pytest
```
Do not open a PR with failing tests.

**Step 6: Commit often, with clear messages.**
```bash
git status                       # see what changed
git add path/to/your/files       # add only your files
git commit -m "T01: add superseded-policy fixture documents"
```
Start every message with the ticket id. Commit after each meaningful piece, not once at the end.

**Step 7: Push your branch.**
```bash
git push -u origin t01-corpus
```
(The first time, `-u` links your branch to GitHub. Later, `git push` is enough.)

**Step 8: Open a Pull Request (PR).** GitHub shows a "Compare & pull request" button after your push. Click it, then:
- **Title:** `T01: Fictional corpus with labeled cases`
- **Description:** use this template
  ```text
  Closes #2

  ## What I did
  - ...

  ## How to check it
  - ...

  ## Questions / things I'm unsure about
  - ...
  ```
  `Closes #2` links the PR to the issue (use your ticket's issue number, shown in the issue URL).
- **Reviewer:** add `cyborgwastaken`. The PR form is pre-filled with a template; fill it in and tick the checklist.

**Step 9: Nothing to do on the board.** The card moves to **In review** by itself when you open the PR, as long as the description contains `Closes #<issue number>` (the template has it). A **draft** PR keeps it In progress until you click *Ready for review*. If a card did not move, tell cyborgwastaken.

**Step 10: Handle review comments.** Reviewers will ask for changes. This is normal and not a criticism. Fix the code on the same branch, commit, and `git push`. The PR updates itself. Reply to each comment ("done" or your reasoning), then ask for a re-review.

**Step 11: Merge.** Once approved, cyborgwastaken merges the PR. The card moves to Done by itself, and the tickets that were waiting for yours move to Ready (their owners get a comment). Then update your computer:
```bash
git checkout main
git pull
```
Start the next ticket from Step 1.

## 6. Rules that keep us out of trouble

1. **Never push to `main`.** It is protected: GitHub rejects direct pushes from you, and a PR needs approval from cyborgwastaken before it can merge. PRs are merged with "squash", so `main` gets one commit per ticket, and your branch is deleted automatically afterwards.
2. **One ticket = one branch = one PR.** Small PRs get reviewed faster.
3. **Pull before you branch** (`git pull` on `main`).
4. **Do not commit secrets.** API keys, passwords, `.env` files never go in git.
5. **Do not commit generated stuff:** `.venv/`, `node_modules/`, `__pycache__/`. The `.gitignore` already covers them.
6. **Do not invent facts in the data.** If a document has no date, leave the date empty rather than making one up. The system relies on this.
7. **Do not change someone else's files** without telling them in the issue.
8. **Stuck for more than 30 minutes? Ask.** Comment on your issue or message the team with what you tried and the error text. Asking early is expected.

## 7. Common problems

| Problem | Fix |
|---|---|
| `git push` is rejected | Someone else changed your branch or `main` moved. Run `git pull`, fix any conflict, push again. Ask if unsure. |
| Merge conflict | Git marks `<<<<<<<` sections in the file. Keep the right lines, delete the markers, `git add` the file, `git commit`. Ask for help the first time. |
| `ModuleNotFoundError: truthguard_agent` | Your venv is not active, or `pip install -r requirements.txt` was run from the wrong folder. Redo setup step 4. |
| Committed to `main` by mistake | Do not push. Tell cyborgwastaken; it is fixable if nothing was pushed. |
| Tests pass for you but fail on review | Pull the latest `main` into your branch: `git merge main`. |

## 8. Review: what to expect

cyborgwastaken reviews every PR. The checks are:
- Does it meet the ticket's **Done when** line?
- Do the tests pass, and are there tests for the new logic?
- Does it use the shared data models in `AGENT/truthguard_agent/schemas/`?
- Is anything invented, hard-coded, or secret?

Reviewing is also a good way to learn. Read other people's PRs even if you are not the reviewer.

## 9. Your docs

Roles (what each role means and its tickets):
- [Role 1: Backend and Database](role-1-backend-database.md)
- [Role 2: Retrieval and AI Pipeline](role-2-retrieval-ai.md)
- [Role 3: Verification](role-3-verification.md)
- [Role 4: Frontend](role-4-frontend.md)
- [Role 5: Data, Evaluation and Demo](role-5-data-eval-demo.md)

Who does what (primary and secondary):

| Role | Primary | Secondary |
|---|---|---|
| 1 Backend and Database | cyborgwastaken | yashdiwan12 |
| 2 Retrieval and AI Pipeline | AshwaniArya2005 | cyborgwastaken, yashdiwan12 |
| 3 Verification | yashdiwan12 | AshwaniArya2005 |
| 4 Frontend | iamsarik | cyborgwastaken |
| 5 Data, Evaluation and Demo | dhruvt293 | iamsarik |

Personal pages: [cyborgwastaken](cyborgwastaken.md), [AshwaniArya2005](ashwaniarya2005.md), [yashdiwan12](yashdiwan12.md), [iamsarik](iamsarik.md), [dhruvt293](dhruvt293.md).
