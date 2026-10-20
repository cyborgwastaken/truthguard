# Resolver Rules

Design for the resolution engine (ticket T05). T09 turns this page into code, so every rule says exactly which inputs it reads and which outcome it gives. All document IDs and dates in the examples are invented.

## 1. What the resolver is

The resolver is a plain Python function with no language model. It decides whether the retrieved evidence justifies a single answer, and says why.

- The **critic** observes: it reports which sources contradict each other and which look stale.
- The **resolver** decides: it applies the rules below to those findings and the document metadata.

Proposed signature (to be agreed on issue #10 before T09 starts):

```python
def resolve(passages: List[RetrievedPassage], critic: CriticResult, as_of: date) -> ResolutionOutcome
```

`ResolutionOutcome` holds `status` (`AnswerStatus`), `winning_source_ids`, `stale_source_ids` and `reason` (one readable sentence).

### Statuses the resolver can return

| Status | Meaning |
|---|---|
| `resolved` | The evidence and metadata establish one position (or there is no conflict). |
| `conflict_unresolved` | A real conflict exists and the metadata does not establish which side wins. Both positions are shown. |
| `insufficient_evidence` | There is nothing to answer from. |

`verification_failed` is **not** a resolver status. The orchestrator returns it when a model call times out or returns malformed output, before the resolver runs. The resolver never turns a failure into a success.

### Inputs the rules read

| Field | Where it comes from | Used by |
|---|---|---|
| `document_id` | `RetrievedPassage.document` | all rules |
| `supersedes_document_id` | `Document` | R1, R2 |
| `effective_date` | `Document` | R2 |
| `authority_level` | `Document` | R3 |
| `contradictions[].source_ids` | `CriticResult` | which documents are in conflict |
| `needs_resolution` | `CriticResult` | only to detect an inconsistent critic result (Step 0) |
| `as_of` | caller (required) | R2 |

`created_at`, `version` and `title` are never used to rank documents.

## 2. Ground rules

1. **Unknown stays unknown.** A `None` date or `unknown` authority is never replaced by a guess, by a default date, or by another field. A rule that needs a value it does not have does not fire.
2. **Newest does not automatically win.** See R4.
3. **No `resolved` without a reason.** Every outcome carries a `reason` that names the documents and the rule used.
4. **The resolver only works with what it is given.** It does not look up documents that were not retrieved.

## 3. The question date (`as_of`)

R2 compares effective dates to a "question date".

- `as_of` is **required**. The resolver never reads the clock, so the same inputs always give the same outcome. This keeps tests and benchmark runs repeatable.
- The orchestrator (T13) chooses the date, defaulting to today, passes it to the resolver and stores it with the answer.
- The reason states the date when it matters (for example "as of 2026-10-20").

A date equal to `as_of` counts as arrived (`effective_date <= as_of`).

## 4. Rules, in priority order

When rules disagree, the one with the lower number wins. Rules R1 to R5 are applied per conflict (see section 5).

### R1: Explicit supersession

- **Rule:** document B supersedes document A when B has `supersedes_document_id == A`, and B is in force under R2. Then B wins over A, and A is stale.
- **Inputs:** `supersedes_document_id`, `effective_date`, `as_of`, `authority_level` of B.
- **Outcome:** `resolved`, winner B, stale A. Reason names B, A, the rule and B's effective date.
- **Who can supersede:** an `official` document can supersede any document. An `unknown`-authority document can supersede only a document that is not `official`. A `draft` or `informal` document never supersedes anything. In every case where the supersession is ignored, the reason says why, even if the document names a `supersedes_document_id` (decision D2).
- **Chains:** a document A is stale only if a document that **names A directly** is in force and allowed to supersede under D2. Staleness is not inherited. Take C supersedes B and B supersedes A:
  - B in force: A is stale, whether or not C is in force. A stale B still supersedes A, because B names A.
  - B not in force (effective date unknown or in the future): A is **not** stale, even if C is in force, because C never names A.
- **Where supersession is looked up:** among all retrieved passages, not only among the sources of one conflict.
- **A supersession target that is not in the corpus** (the pointed-to ID was never ingested, or was not retrieved) is ignored. It cannot make anything stale because there is nothing to compare. Mention it in the reason only if it affects the outcome.
- **Example:**
  - `remote_policy_v1`: official, effective 2026-01-15, "up to five days remote".
  - `remote_policy_amendment_v2`: official, effective 2026-10-01, `supersedes_document_id = remote_policy_v1`, "up to three days remote".
  - Question date 2026-10-20. The critic reports a contradiction.
  - Result: `resolved`; winner `remote_policy_amendment_v2`; stale `remote_policy_v1`.
  - Reason: "remote_policy_amendment_v2 explicitly supersedes remote_policy_v1 (effective 2026-10-01); rule: explicit supersession."

### R2: Effective date

- **Rule:** a supersession is in force only when the superseding document's `effective_date` is on or before `as_of`.
  - `effective_date > as_of`: **not yet in force.** R1 does not fire. The superseded document still stands. The reason says the amendment takes effect on that date.
  - `effective_date` is `None`: **cannot confirm.** R1 does not fire, and the reason says the effective date is unknown (decision D1).
- **Inputs:** `effective_date` of the superseding document, `as_of`.
- **Outcome:** the supersession is ignored. The conflict continues to R3 and R5 as if no supersession existed, but the reason mentions the ignored supersession.
- **Example:**
  - Same documents as R1, but the amendment is effective 2026-12-01 and the question date is 2026-10-20.
  - Result: R1 does not fire. Both are `official`, so R3 gives no ranking and R5 applies: `conflict_unresolved`.
  - Reason: "remote_policy_amendment_v2 supersedes remote_policy_v1 but takes effect on 2026-12-01, after 2026-10-20; no precedence established."
  - A caller who wants the current rule can see the future change in the reason.

### R3: Authority

- **Rule:** if both sides of a conflict have a known authority level and the levels differ, the higher one wins. Ranking: `official` above `draft` and `informal`. `draft` and `informal` rank equal to each other (decision D3).
- **Applies only when** there is no in-force supersession (R1 takes priority) and both levels are known.
- **More than two sides:** a side is outranked only if another remaining side has a known, higher level. `unknown` neither outranks nor is outranked. Example: official X, draft Y, unknown U: Y is outranked by X; X and U remain, so the conflict is unresolved.
- **`unknown` gives no ranking.** If either side is `unknown`, R3 does not fire. An `unknown` document is not treated as lower authority.
- **Outcome:** `resolved`, winner the higher-authority document. Stale list stays empty, because authority does not make a document outdated. Reason names both documents, both levels and the rule.
- **Example:**
  - `travel_budget_policy`: official, "hotel limit 150".
  - `travel_budget_draft_2026`: draft, "hotel limit 200", newer.
  - No supersession.
  - Result: `resolved`; winner `travel_budget_policy`.
  - Reason: "travel_budget_policy is official and travel_budget_draft_2026 is a draft; rule: authority."

### R4: Newest does NOT automatically win

- **Rule:** a later `effective_date`, `created_at` or `version` never settles a conflict on its own. It matters only through R1 and R2, where the newer document **explicitly** names the older one.
- **Outcome:** none. This rule forbids a shortcut. If the only difference between two conflicting documents is that one is newer, the result is `conflict_unresolved` (R5).
- **Why:** the newer document might be a draft, a different scope, or an unrelated policy.
- **Example:**
  - `expense_policy_a`: official, effective 2026-02-01, "meal limit 40".
  - `expense_policy_b`: official, effective 2026-08-01, "meal limit 55", no `supersedes_document_id`.
  - Result: `conflict_unresolved`. The resolver must not answer "55".

### R5: Equal authority, no supersession

- **Rule:** if a conflict remains after R1 to R3, the result is `conflict_unresolved`. This covers: both `official` and no supersession; both `unknown`; one `unknown`; both `draft` or `informal`.
- **Outcome:** `conflict_unresolved`. `winning_source_ids` is empty. Reason names the conflicting documents and says precedence cannot be established from the available metadata. The UI shows both positions.
- **Example:**
  - `leave_policy_hr`: official, "20 days".
  - `leave_policy_finance`: official, "18 days".
  - Neither supersedes the other.
  - Result: `conflict_unresolved`.
  - Reason: "leave_policy_hr and leave_policy_finance are both official and neither supersedes the other; rule: equal authority, no supersession."

### R6: No relevant evidence

- **Rule:** if there is nothing to answer from, the result is `insufficient_evidence`. This is checked **first**, before R1 to R5.
- **Inputs:** `passages`.
- **Outcome:** `insufficient_evidence` when `passages` is empty. Reason: "No relevant passages were retrieved."
- **Example:** the question is "What is the parental leave policy?", but no document mentions parental leave. Retrieval returns nothing. Result: `insufficient_evidence`.
- The resolver cannot judge relevance of retrieved passages. If the critic flags every claim as unsupported, the orchestrator (T13) returns `insufficient_evidence` before calling the resolver (decision D5).

### R7: Missing metadata

- **Rule:** the resolver never fills in missing metadata. A `None` date, `None` `supersedes_document_id` or `unknown` authority means "that rule has no input".
- **Effect on other rules:** missing data makes R1 to R3 not fire, which usually leads to R5 (`conflict_unresolved`). It never produces `resolved` by guessing.
- **Outcome:** none by itself. The reason should say which value was unknown when that is why a rule did not fire.
- **Example:** `lease_note_a` (official, no dates) and `lease_note_b` (official, no dates) disagree. Result: `conflict_unresolved`; reason: "effective dates unknown for both documents".

## 5. How the rules fit together

**Step 0: before any conflict is judged.**
- If `passages` is empty, R6 applies and the result is `insufficient_evidence`.
- **The `contradictions` list decides whether a conflict exists**, not `needs_resolution`.
  - `contradictions` is empty and `needs_resolution` is false: the result is `resolved` with reason "No contradiction was detected among the retrieved sources."
  - `contradictions` is empty but `needs_resolution` is true: the critic result is inconsistent, because a flagged conflict must come with evidence. The result is `conflict_unresolved`, `winning_source_ids` is empty, and the reason says the critic reported a conflict without any contradiction to resolve, so no source can be preferred (decision D9). The critic (T12) must not produce this combination.
  - `contradictions` is not empty but `needs_resolution` is false: the contradictions are judged anyway.
- **Stale sources are computed once, over all retrieved passages:** every retrieved document that is superseded by an in-force retrieved document under R1 goes in `stale_source_ids`, whether or not it appears in a contradiction. Staleness decides a conflict only, it does not remove a document from the evidence (decision D8).
- **`unsupported_claims` is ignored.** The resolver judges conflicts between sources, not whether claims are backed. Status never changes because of it (decision D10).

**Step 1: per conflict.** For each contradiction in `critic.contradictions`, look only at the documents in its `source_ids`:

1. R1 and R2: find any in-force supersession among them. A document that is superseded by an in-force retrieved document (R1) is defeated.
2. Among the sides that remain, R3: drop any side outranked by another remaining side with a known, higher authority level.
3. If still no single remaining side, R5.

A conflict is **resolved** only if exactly one position remains undefeated. If two or more remain, it is unresolved.

**Step 2: combine.** The overall status is `resolved` only if every conflict is resolved. If any conflict is unresolved, the overall status is `conflict_unresolved`, and the reason covers the unresolved ones. `winning_source_ids` lists winners of resolved conflicts. `stale_source_ids` is the list computed in Step 0, not a per-conflict list.

## 6. Outcome table

| # | Passages | Conflict between sources? | In-force supersession? | Authority levels | Status | Rule |
|---|---|---|---|---|---|---|
| 1 | none | n/a | n/a | n/a | `insufficient_evidence` | R6 |
| 2 | some | no | n/a | n/a | `resolved` | Step 0 |
| 3 | some | yes | yes (effective date reached) | any | `resolved`, newer is winner | R1 |
| 4 | some | yes | named but `effective_date > as_of` | equal or unknown | `conflict_unresolved` | R2, R5 |
| 5 | some | yes | named but `effective_date` unknown | equal or unknown | `conflict_unresolved` | R2, R7, R5 |
| 6 | some | yes | named by a `draft` or `informal` document | any | follows R3 or R5 as if no supersession | R1, R3, R5 |
| 7 | some | yes | none | both known, different | `resolved`, higher is winner | R3 |
| 8 | some | yes | none | equal and known | `conflict_unresolved` | R5 |
| 9 | some | yes | none | one or both `unknown` | `conflict_unresolved` | R3, R5, R7 |
| 10 | some | yes, differs only by date | none | equal | `conflict_unresolved` | R4, R5 |
| 11 | some | several, some resolved and some not | mixed | mixed | `conflict_unresolved` | Step 2 |
| 12 | some | yes | named by an `unknown`-authority document against an `official` one | official vs unknown | `conflict_unresolved` | R1 (D2), R3, R5 |
| 13 | some | `contradictions` empty, `needs_resolution` true | n/a | n/a | `conflict_unresolved` | Step 0 (D9) |
| 14 | some | no | yes (B in force, names A) | any | `resolved`, A in `stale_source_ids` | Step 0 (D8) |

In rows 4 and 5, if authority levels are known and differ, R3 applies as in row 7.

## 7. Decisions and questions for the lead

The guiding principle: when metadata is unclear, an honest `conflict_unresolved` is better than a confident wrong `resolved`. The decisions below follow from it. D1 to D7 were confirmed by @cyborgwastaken in the T05 review. D8 to D10 came from that review.

| ID | Topic | Decision |
|---|---|---|
| D1 | Superseding document has no effective date | The supersession does not apply. Reason says the effective date is unknown. |
| D2 | Who can supersede | `official` can supersede any document. `unknown` can supersede only a non-`official` document. `draft` and `informal` never supersede. An `official` document is therefore never overruled by a lower or unknown authority. |
| D3 | `draft` versus `informal` | Ranked equal, both below `official`. The docs define no order between them. |
| D4 | Question date | `as_of` is a required argument. The resolver never reads the clock. The orchestrator defaults it to today and records it with the answer. |
| D5 | Irrelevant retrieved passages | The resolver returns `insufficient_evidence` only for empty passages. The orchestrator (T13) maps "every claim unsupported" to `insufficient_evidence` before calling the resolver. |
| D6 | Authority versus supersession | An in-force supersession beats authority (R1 before R3). D2 prevents a lower-authority document from abusing this. |
| D7 | Superseding document not retrieved | The resolver only uses retrieved passages. The retriever (T07) must pull in documents that supersede or are superseded by retrieved ones. |
| D8 | Meaning of "stale" | Staleness only decides a conflict. `stale_source_ids` is informational, for the answer view and the trust report's freshness dimension. It never removes a document from the evidence. |
| D9 | `needs_resolution` true with no contradictions | The resolver returns `conflict_unresolved` with an explanatory reason. The critic must not produce this combination. |
| D10 | `unsupported_claims` | Ignored by the resolver. The orchestrator (T13) handles the case where every claim is unsupported (D5). The trust report (T18) shows partial citation support. |

Question for the lead (from the review of this page):

1. If every side of a conflict is defeated by supersession (for example two superseded documents that disagree, and the in-force document is silent), I propose the conflict is moot: it counts as resolved in favor of the superseding document(s), and the reason says so. The safer alternative is `conflict_unresolved`. Which one?
