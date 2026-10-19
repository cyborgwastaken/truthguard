# iamsarik: Critic, Resolver, Evidence Graph, Trust Report

Read the [team guide](README.md) first for the ticket loop (branch, commit, PR, board).

## Your role in one paragraph

You own the "verification" part, which is the heart of TruthGuard. The synthesizer drafts an answer. Your code then checks it: do documents contradict each other, is anything outdated, is every claim backed by evidence, and who wins when documents disagree. Your rule of thumb: **be able to point to evidence for every finding, and never guess.**

## Your tickets

| Ticket | Issue | Wave | Start when |
|---|---|---|---|
| T05 Resolver rules design doc | #6 | 1 | Now (Ready) |
| T09 Resolver engine | #10 | 2 | T05 is Done |
| T12 Critic agent | #13 | 3 | T08 (synthesizer) is Done |
| T15 Evidence graph assembler and endpoint | #16 | 3 | T12 and T14 are Done |
| T18 Trust report builder and endpoint | #19 | 4 | T15 is Done |

Useful background: [Initial roadmap sections 5.4 and 5.5](../truthguard_intital_roadmap.md) and [Expansion roadmap features A and B](../truthguard_expansion_roadmap.md). The data models are in `AGENT/truthguard_agent/schemas/models.py`; read `CriticResult`, `Contradiction`, `StalenessFinding`, `EvidenceLink`, `FinalAnswer`.

---

## T05: Resolver rules design doc

**Goal:** a written, precise rulebook for deciding which document wins. No code yet. T09 will turn it into code, so ambiguity here becomes bugs later.

**Where:** `DOCS/resolver-rules.md`.

**Steps:**
1. Branch `t05-resolver-rules`.
2. For each rule, write: the rule, the inputs it looks at, the outcome, and one worked example.
3. Cover at least these rules, in priority order:
   - **Explicit supersession:** document B has `supersedes_document_id = A` **and** B's effective date has arrived. Then B wins over A and A is stale.
   - **Effective date:** a supersession whose effective date is in the future relative to the question date does not apply yet.
   - **Authority:** if the corpus defines authority levels, an `official` document outranks a `draft` or `informal` one. If authority is `unknown`, it gives no ranking.
   - **Newest does NOT automatically win.** A later date alone never settles a conflict. Say so explicitly.
   - **Equal authority, no supersession:** status is `conflict_unresolved`; show both positions.
   - **No relevant evidence:** `insufficient_evidence`.
   - **Missing metadata:** unknown stays unknown; the resolver must not fill it in.
4. Add a table of outcomes: inputs -> `resolved` / `conflict_unresolved` / `insufficient_evidence`.
5. Add a section "Questions I'm unsure about" and tag cyborgwastaken in the PR to settle them.
6. Commit, push, PR (`Closes #6`).

**Done when:** every rule has an example and the outcome table is complete.

---

## T09: Resolver engine

**Goal:** a plain Python function, **no language model involved**, that applies your T05 rules.

**Where:** `AGENT/truthguard_agent/resolver.py`, tests in `AGENT/tests/test_resolver.py`.

**Steps:**
1. Agree the function signature in a comment on issue #10 before coding. Suggested:
   ```python
   def resolve(passages: List[RetrievedPassage], critic: CriticResult, as_of: Optional[date] = None) -> ResolutionOutcome:
       ...
   ```
   with `ResolutionOutcome` containing `status` (`AnswerStatus`), `winning_source_ids`, `stale_source_ids` and `reason` (a sentence a human can read).
2. Implement one rule per small helper function so each can be tested alone.
3. Write at least one test per rule, plus tests for the edge cases: missing dates, a supersession pointing to a document that does not exist, a draft that is newer than an official policy.
4. The `reason` text must name the documents and the rule used, e.g. "remote_policy_amendment_v2 explicitly supersedes remote_policy_v1 (effective 2026-10-01)".
5. Commit, push, PR (`Closes #10`).

**Done when:** all rules from T05 have passing unit tests, and the function never returns `resolved` without a stated reason.

---

## T12: Critic agent

**Goal:** given a question, a draft answer and the retrieved passages, report problems with evidence.

**Where:** `AGENT/truthguard_agent/critic.py`, tests in `AGENT/tests/test_critic.py`.

**Steps:**
1. Pull `main` after T08 is merged and read `synthesizer.py` to see its output (claims with citation IDs).
2. Return a `CriticResult` (already defined in schemas) with three lists:
   - `contradictions`: two sources disagree about the same claim.
   - `staleness`: a source is explicitly superseded.
   - `unsupported_claims`: a claim whose cited passages do not back it up.
3. Split the job into two kinds of check:
   - **Deterministic checks (plain Python):** dates, `supersedes_document_id`. Do these in code, not with the model.
   - **Semantic checks (language model):** "do these two passages actually contradict?", "does this passage support this claim?". Ask for structured JSON and validate it with Pydantic. If the model returns bad JSON, retry once, then fail safely (report that verification failed; never pretend it passed).
4. **Every finding must cite evidence** (`EvidenceRef` with `source_id` and `chunk_id`). A finding without evidence is rejected.
5. Test with the fixture documents from T01 (superseded, unresolved, hard negative). The hard-negative test is important: the critic must **not** flag passages that merely sound similar. Use a fake model in tests so they run offline.
6. Commit, push, PR (`Closes #13`).

**Done when:** known conflicts in the fixtures are flagged with evidence and hard negatives are not.

---

## T15: Evidence graph assembler and endpoint

**Goal:** turn an answer's claims and evidence into a structure the website can draw: claims, the passages that support or contradict them, and the conflicts.

**Where:** `AGENT/truthguard_agent/evidence_graph.py` and an endpoint in `BACKEND/app/api/answers.py`. Coordinate the endpoint with cyborgwastaken, who owns the backend.

**Steps:**
1. Define the output shape first (nodes and edges, or a nested list) and post it on issue #16 so yashdiwan12 can start the UI against it.
2. Build the graph from stored claims and `EvidenceLink` records. Each link has a relation: `supports`, `contradicts` or `context`.
3. **Never label a citation as "supports" just because it was retrieved.** Only use relations the critic actually judged.
4. Mark unresolved conflicts so the UI can highlight them.
5. Expose `GET /answers/{answer_id}/evidence-graph`.
6. Test with a fixture where you know exactly which links should exist.
7. Commit, push, PR (`Closes #16`).

**Done when:** a known fixture produces exactly the expected nodes and links.

---

## T18: Trust report builder and endpoint

**Goal:** a report with separate, explained numbers describing how well-checked an answer is.

**Where:** `AGENT/truthguard_agent/trust_report.py`, `GET /answers/{answer_id}/trust-report`.

**Dimensions (see Expansion roadmap, Feature B):** evidence coverage, citation support, contradiction status, freshness, provenance completeness, verification status.

**Steps:**
1. For each dimension write the **formula and denominator** in the function docstring (e.g. "evidence coverage = claims with at least one evidence link / total factual claims").
2. If the needed data is missing, report `unknown`. Never treat missing metadata as "fresh" or "authoritative".
3. **Do not combine everything into one score** like "92% trustworthy". It would be invented. Keep the dimensions separate.
4. A high evidence coverage must never hide an unresolved contradiction; the report must show the conflict status prominently.
5. Test each dimension with a small fixed example where you can compute the value by hand.
6. Commit, push, PR (`Closes #19`).

**Done when:** every number has a documented formula and a passing test.

## While you wait

Until T05 is merged, you are the first person in Wave 1 with only a design doc, so take your time and make it good. Once it is in review, read the T01 fixtures (Ashwani's PR) so your rules match the real cases.
