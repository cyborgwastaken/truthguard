# Demo Script

About 8 minutes. Everything here uses the fictional "Acme Corp" documents; nothing real goes to the language model.

## Before you go on (10 minutes, the day before and again an hour before)

1. **Start everything:** `OPS/start.sh`. It checks Docker, Node and Python, sets up the environment, starts the
   database, the backend and the frontend, and loads the 26 sample documents. Open http://localhost:5173.
   It prints which model mode it chose.
2. **Give it the model key:** put `GROQ_API_KEY=...` in `BACKEND/.env` (a git-ignored file), then `OPS/stop.sh`
   and `OPS/start.sh` again. The top bar shows "Backend: connected"; `curl localhost:8000/health` shows
   `"key_present": true`.
3. **Rehearse against the real model and record it:** `cd BACKEND && python -m app.demo --repeats 3`.
   It runs the demo questions three times each, compares each answer with its expected status, and records the
   model's replies. Pick, for each kind of question below, one that printed `OK` every time. If a question prints
   `BAD`, use its alternative.
4. **Run the benchmark** (takes a while; it can be interrupted and resumed): `cd BACKEND && python -m app.benchmark`.
   When it finishes the Benchmark tab shows the results. Read them before you present; say what they are, good or bad.
5. **Clear the rehearsal answers:** `OPS/reset_answers.sh` (keeps the documents).
6. **The fallback:** with replies recorded, `TRUTHGUARD_LLM_MODE=replay OPS/start.sh` runs the whole demo with
   no network and no key. Replayed answers carry a visible "Replayed recording" tag; say so if you use it.
   Also record a screen video of one perfect run.

## Pacing (read this)

The free Groq tier allows about 8,000 tokens a minute and one question uses 5,000 to 7,000, so **a question asked
right after another may wait 15 to 45 seconds** for the rate limit instead of failing. Ask the next question only after
you have finished talking about the last one, and expect 5 to 40 seconds per answer. The loading text says it is working.
If a wait would be longer than 45 seconds (a daily cap) the answer shows "Verification failed" with the reason; then use
the recorded replay for the rest.

## The script

**1. What it is (30 s).** "Companies keep policies in many documents. They get amended, drafted, and
contradicted. A normal question-answering system finds some text and summarises it, so it can state an outdated rule
with full confidence. TruthGuard checks the answer against the sources, shows the evidence, and says so when it
cannot tell."

**2. The documents (30 s).** Click **Documents**. 26 fictional documents. Point at the columns: version, effective date,
authority (official, draft, informal) and "unknown" where the metadata is missing. "It never fills a gap in
silently."

**3. A superseded policy (2 min).** **Chat**, then the example **Superseded policy**:
*How many days per week can employees work remotely?*

You should see (takes a few seconds with the real model):
- Status **Resolved**, the answer **three days**, and *Why:* an explicit supersession, with the date.
- A comparison of the two documents side by side: the old policy tagged **Superseded**, the amendment tagged
  **Takes precedence**.
- Click the source chip: the passage opens with its authority, effective date, version and what it supersedes.
- Open **Evidence graph**: two claims, two sources, supports/contradicts lines, the supersession bracket.
- Open **Trust report**: separate dimensions (coverage, citation support, conflicts, freshness, provenance), each
  with its numerator and denominator, and deliberately no single score.

Say: "The old policy says five days. A plain search-and-answer system can state that. Here the amendment explicitly
replaces it and is in force, so the system answers three and says why."

**4. Two equally official sources disagree (1.5 min).** Example **Equally official sources disagree**:
*How long do employees have to submit expense receipts?*

You should see: status **Conflict - unresolved**, both positions (14 days from Finance, 30 days from HR) shown with the
same weight, and *Why:* equal authority, neither supersedes the other.

Say: "It does not guess. Two official documents disagree and nothing in the metadata settles it, so the right answer
is to show both and say so."

**5. Not in the documents (1 min).** Example **Not in the documents**:
*What is Acme Corp's policy on employee stock options?*

You should see: status **Insufficient evidence** and "Not answered". Say: "Search always returns something, so
the system has to decide there is nothing to answer from. It abstains instead of inventing."

**6. No false alarm (1 min).** Example **Different groups, no conflict**:
*How many remote days per week can managers take versus interns?*

You should see: **Resolved**, both groups answered, no conflict. Say: "Two numbers are not a contradiction when they
are about different people."

**7. The measurement (1.5 min).** Click **Benchmark**. "The same 18 labeled questions answered three ways: plain
search-and-answer, with the critic added, and the full system." Walk through the rows that matter:
**Key facts present**, **States the outdated value**, **False conflicts**, **Flags real conflicts**, **Failed checks**.
Read the real numbers aloud, including the bad ones. Open a case that failed to show the answers.

Say before the numbers: "It is 18 invented documents and questions, measured on one model. It shows how the three
setups differ; it does not say how the system would score on other documents."

**8. Close (30 s).** "The point is not that it is always right. It is that it shows its evidence, says when sources
conflict or are out of date, abstains when it cannot tell, and counts its own failures instead of hiding them."

## If something goes wrong

| What happens | What to do |
|---|---|
| An answer takes more than 30 s or shows "Request failed" | Say "the model service is slow", wait; or switch to replay (above). The app never shows a half answer. |
| An answer differs from the rehearsal | That is the model varying between runs. Say so, and use the benchmark page for the measured picture. Do not hide it. |
| "No language-model key is configured" | `GROQ_API_KEY` is missing in `BACKEND/.env`; fix it and restart with `OPS/stop.sh`, `OPS/start.sh`. Or use replay. |
| Groq returns 429 (rate limit) | Wait a minute. Ask fewer questions live; use the recorded replay for the rest. |
| The page says "Backend: offline" | `OPS/start.sh` again; check `.run/backend.log`. |
| Old answers clutter the chat | They do not: the chat only shows this session. To clear the stored ones, `OPS/reset_answers.sh`. |
| Docker is not running | Start Docker Desktop, wait until it is ready, `OPS/start.sh`. |

## Things to say if asked

- **"Is it always right?"** No. The benchmark counts wrong answers and failed checks separately, and the trust
  report shows what was and was not checked. It is built to expose uncertainty, not to promise correctness.
- **"What stops a document from instructing the model?"** Documents are wrapped as data and escaped; the model must
  cite real passages, and a citation to anything that was not retrieved fails the whole answer; the critic only sees
  documents the answer relies on. There are tests for this.
- **"Why not just pick the newest document?"** Newer is not always current: a draft can be newer and unapproved. The
  rules need an explicit "supersedes" link, an effective date that has arrived, and enough authority.
- **"What does the model decide and what does the code decide?"** The model drafts the answer and judges whether
  passages disagree or back a claim. Dates, supersession, authority and the final status are plain rules, so the
  decision can be read and tested.
