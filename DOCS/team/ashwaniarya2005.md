# AshwaniArya2005: Test Data and Benchmark

Read the [team guide](README.md) first for the ticket loop (branch, commit, PR, board).

## Your role in one paragraph

You own the test data and the scoreboard. TruthGuard is only impressive if we can prove it beats a plain "search and answer" system. You build (1) fake documents with deliberate contradictions, (2) the plain baseline system, and (3) the benchmark that scores both on the same questions. Everything you produce must be honest: we report the numbers we actually measure, even if they are unflattering.

## Your tickets

| Ticket | Issue | Wave | Start when |
|---|---|---|---|
| T01 Fictional corpus with labeled cases | #2 | 1 | Now (Ready) |
| T10 Baseline RAG | #11 | 2 | T07 (retriever) is Done |
| T16 Benchmark dataset v1 and metric functions | #17 | 3 | T01 and T10 are Done |
| T19 Benchmark runner (3 configs) | #20 | 4 | T13 and T16 are Done |

---

## T01: Fictional corpus with labeled cases

**Goal:** 15 to 30 short, fake documents (for example a company's remote-work policy, travel rules, expense rules) that contain deliberate problems, plus a list of questions with the correct expected outcome for each.

**Why it matters:** every other ticket is tested against your data. Quality here decides whether the demo works.

**Where files go:** `AGENT/datasets/fixtures/` (documents) and `AGENT/datasets/benchmark/` (questions; you finish these in T16).

**Document format:** one JSON file per document. The fields match the `DocumentIn` model in `AGENT/truthguard_agent/schemas/models.py`; open that file and look.

```json
{
  "document_id": "remote_policy_v1",
  "title": "Remote Work Policy",
  "version": "1",
  "created_at": "2026-01-10",
  "effective_date": "2026-01-15",
  "authority_level": "official",
  "supersedes_document_id": null,
  "content": "Employees may work remotely up to five days per week..."
}
```

Rules for the fields:
- `document_id`: unique, lowercase, underscores, e.g. `remote_policy_v1`. Never reuse or rename one later.
- Dates are `YYYY-MM-DD`. Allowed `authority_level` values: `official`, `draft`, `informal`, `unknown`.
- If a fact is genuinely unknown, use `null`. Include a few documents with missing dates on purpose; the system must cope.
- All content is invented. No real company names or real people's data.

**Steps:**
1. Create the branch `t01-corpus`.
2. Plan the topics. Pick 4 or 5 topics (remote work, travel budget, expense limits, leave, equipment).
3. Write documents so that the set contains **all** of these cases (aim for 3 or more examples of each):
   - **Superseded:** v1 says "5 days remote"; an official amendment (`supersedes_document_id: "remote_policy_v1"`, later effective date) says "3 days". Correct answer: 3 days, resolved.
   - **Unresolved conflict:** two *equally official* documents disagree and neither supersedes the other. Correct outcome: conflict_unresolved. Both positions must be shown.
   - **Insufficient evidence:** questions about something no document mentions. Correct outcome: insufficient_evidence.
   - **Hard negative:** two passages that sound similar but do **not** actually contradict (e.g. one is about managers, one about interns). The system must not flag these.
   - **Plain answerable:** a topic with a single clear document. Correct outcome: resolved.
   - **Trap:** a newer-looking document that is only a *draft* and does not supersede anything. Newest does not always win.
4. Write the labels in `AGENT/datasets/fixtures/README.md`: a table listing each case, its documents, the question, and the expected outcome (`resolved`, `conflict_unresolved`, `insufficient_evidence`) with a one-sentence reason.
5. Write a small test `AGENT/tests/test_fixtures.py` that loads every JSON file and checks it validates as `DocumentIn`, and that every `supersedes_document_id` points to a document that exists.
   ```python
   import json, pathlib
   from truthguard_agent.schemas import DocumentIn

   FIXTURES = pathlib.Path(__file__).parent.parent / "datasets" / "fixtures"

   def test_all_fixtures_validate():
       for path in FIXTURES.glob("*.json"):
           DocumentIn(**json.loads(path.read_text()))
   ```
6. Run `cd AGENT && python -m pytest`, commit, push, open a PR (`Closes #2`).

**Done when:** 15 to 30 valid documents, all six case types present, labels table written, test passes.

---

## T10: Baseline RAG

**Goal:** a deliberately simple system: find the most relevant passages, ask the language model to answer from them. **No** conflict checking, no resolver. This is the "before" picture we compare against.

**Where:** `AGENT/truthguard_agent/baseline.py` and `AGENT/tests/test_baseline.py`.

**Steps:**
1. Wait until T07 (retriever) is Done, then `git pull` and read `retriever.py` to see how to call it.
2. Write one function `answer_baseline(question: str) -> FinalAnswer` (use the `FinalAnswer` model from schemas). It retrieves passages, asks the model to answer using only them, and returns an answer with citations.
3. It should always return status `resolved` when it produced an answer, and `insufficient_evidence` only if nothing was retrieved. That is exactly the weakness we are measuring.
4. Test it with a fake/stub model so tests do not call the paid API. Ask cyborgwastaken how the model client is wrapped.
5. Commit, push, PR (`Closes #11`).

**Done when:** you can run it on any fixture question and get a `FinalAnswer`.

---

## T16: Benchmark dataset v1 and metric functions

**Goal:** turn your T01 labels into a machine-readable test set, and write the functions that compute scores.

**Where:** `AGENT/datasets/benchmark/cases.json`, `AGENT/truthguard_agent/evaluation/metrics.py`, tests in `AGENT/tests/test_metrics.py`.

**Steps:**
1. Create `cases.json`: a list where each case has `case_id`, `question`, `category` (superseded / unresolved / insufficient / hard_negative / plain), `expected_status`, `expected_source_ids` (documents that must be cited), and `contradicting_source_ids` (empty for hard negatives).
2. Give the dataset a `dataset_version` field (`"v1"`). Whenever you change a case, bump it.
3. Write metric functions, each a small pure function with a docstring that states the **formula and denominator**:
   - `retrieval_recall`: of the expected documents, what share did we retrieve?
   - `contradiction_precision` / `contradiction_recall`: flagged conflicts that were real; real conflicts that were flagged.
   - `citation_support_rate`: citations that actually support their claim.
   - `correct_abstention_rate`: of insufficient-evidence cases, how many did the system refuse?
   - `resolution_accuracy`: final status equals expected status.
4. Test each function with tiny hand-made examples where you can compute the answer by hand.
5. Commit, push, PR (`Closes #17`).

**Done when:** every metric has a documented formula and a passing test with a hand-computed expected value.

---

## T19: Benchmark runner (3 configs)

**Goal:** run every case through three systems and record the results.

**The three systems:** (1) baseline RAG, (2) RAG plus critic, (3) full TruthGuard with the resolver.

**Where:** `AGENT/truthguard_agent/evaluation/runner.py`.

**Steps:**
1. Write `run_benchmark(config_name, cases) -> RunResult` that calls the chosen system on each case, stores the output, and computes the metrics from T16.
2. Save per-case results (question, retrieved passages, answer, status, whether it was correct). Every number in the summary must be traceable to a per-case row.
3. Record the run configuration: dataset version, model name, prompt version, retrieval settings, timestamp.
4. Record latency per case.
5. Commit, push, PR (`Closes #20`).

**Done when:** one command runs all three systems on all cases and writes a results file with per-case rows and summary metrics.

## Honesty rule

Do not tune the system or edit the test cases just to make the scores look better. If TruthGuard does not beat the baseline on some category, that is a finding and goes in the report.

## While you wait for Wave 2

Once T01 is merged, you can help by reviewing teammates' PRs and by reading `AGENT/truthguard_agent/schemas/models.py` so the later tickets feel familiar.
