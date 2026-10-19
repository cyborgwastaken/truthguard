# TruthGuard Expansion Roadmap

**Purpose:** Evolve TruthGuard from a hackathon MVP into an inspectable, measurable, and maintainable document-verification system.

**Core promise:** TruthGuard does not merely answer questions. It exposes the evidence behind an answer, identifies conflicts and uncertainty, and records how verification decisions were reached.

## 1. Scope and prioritization

This roadmap preserves the existing architecture:

- React frontend
- FastAPI backend
- Orchestrator
- Retriever
- Synthesizer
- Critic / adversary
- Resolution engine
- Document store and retrieval index

The features below are proposed extensions. They are not all required for the original MVP.

### Recommended order

| Priority | Feature | Target phase | Why this order |
|---|---|---|---|
| P0 | Stable claim/evidence IDs and evaluation schemas | Hackathon foundation | Every selected feature depends on traceable evidence and repeatable outputs |
| P1 | Evidence Graph | Hackathon thin slice; expand later | Makes verification inspectable and gives the UI a compelling demonstration |
| P1 | Trust Reports | Hackathon thin slice; calibrate later | Communicates what the system checked without pretending to guarantee correctness |
| P1 | Benchmark & Red-Team Lab | Small hackathon benchmark; expand later | Measures whether the critic and resolution engine actually improve on baseline RAG |
| P2 | Counterfactual Verification | Post-hackathon | Depends on stable retrieval, evidence IDs, deterministic test cases, and result comparison |
| P2 | Human Review Workflow | Post-hackathon, unless judging requires it | Requires persistent cases, reviewer identity/permissions, and an audit trail |
| P2 | Continuous Monitoring | Post-hackathon | Depends on reliable document versioning, change detection, dependency tracking, and re-evaluation |

**Hackathon rule:** Implement a thin, end-to-end slice of the first three features. Do not attempt all six at full depth in under a week.

## 2. Target architecture

```text
React UI
  ├── Chat + answer citations
  ├── Evidence Graph viewer
  ├── Trust Report panel
  ├── Benchmark / Red-Team dashboard
  ├── Counterfactual comparison (later)
  ├── Review queue (later)
  └── Change-impact dashboard (later)
             |
             v
FastAPI
  ├── POST /questions
  ├── POST /documents
  ├── GET  /documents
  ├── GET  /answers/{answer_id}
  ├── GET  /answers/{answer_id}/trust-report
  ├── GET  /answers/{answer_id}/evidence-graph
  ├── POST /evaluations/runs
  ├── GET  /evaluations/runs/{run_id}
  ├── POST /counterfactuals (later)
  ├── POST /reviews (later)
  └── POST /monitoring/rescan (later)
             |
             v
Orchestrator
  ├── Retriever
  ├── Synthesizer
  ├── Critic / Adversary
  ├── Resolution Engine
  └── Result / provenance assembler
             |
      +------+--------------------+
      |                           |
      v                           v
Document + metadata store    Retrieval index
      |
      v
Evidence / claim records
      |
      +--> Evidence Graph
      +--> Trust Report builder
      +--> Benchmark runner
      +--> Counterfactual runner (later)
      +--> Review + audit records (later)
      +--> Change dependency tracker (later)
```

### Architecture principles

1. **One shared evidence model:** All features must use the same stable document, chunk, claim, and answer identifiers.
2. **Keep orchestration explicit:** The Python orchestrator controls the existing agents and passes typed results between them.
3. **Separate observations from decisions:** The critic reports findings; the resolution engine decides whether the evidence and metadata justify a resolution.
4. **Do not invent confidence:** Distinguish measurable evidence checks from a calibrated probability of correctness.
5. **Preserve provenance:** Every finding should point to source passages and document versions.
6. **Make failures visible:** Retrieval failure, parse errors, timeouts, and inconclusive results should be represented explicitly.

## 3. Shared foundation: data model and contracts

Implement this foundation before building the new features.

### Core records

- **Document:** `document_id`, title, version, content hash, source, created date, effective date, authority metadata, explicit supersession relationship.
- **Chunk:** `chunk_id`, `document_id`, text, page/section/offset information, embedding reference if used.
- **Answer:** `answer_id`, question, answer text, status, model/prompt versions, timestamp.
- **Claim:** `claim_id`, `answer_id`, claim text, claim type, verification status.
- **Evidence link:** `claim_id`, `chunk_id`, relation (`supports`, `contradicts`, `context`), rationale, verifier version.
- **Conflict:** `conflict_id`, involved claim/source IDs, status, resolution rationale.
- **Evaluation run:** `run_id`, system configuration, dataset version, metrics, per-case results.
- **Audit event:** `event_id`, actor/system component, action, target ID, timestamp, before/after references where appropriate.

Use stable IDs. A content hash can help detect exact duplicate or changed files, but it should not replace a persistent document ID.

### Suggested claim status values

- `supported`
- `contradicted`
- `partially_supported`
- `unsupported`
- `unverified`

### Suggested answer status values

- `resolved`
- `conflict_unresolved`
- `insufficient_evidence`
- `verification_failed`

### Minimum evidence contract

Each factual claim should include one or more evidence links or explicitly state that evidence is missing. A citation existing is not proof that the citation supports the claim; support must be evaluated separately.

## 4. Feature roadmap

## Feature A — Evidence Graph

**Goal:** Show claims, evidence passages, contradictions, and resolution decisions as a traceable graph.

### MVP / hackathon slice

- Extract atomic claims from the synthesized answer.
- Link each claim to retrieved chunks.
- Classify links as `supports`, `contradicts`, or `context`.
- Display claims and linked passages in a side panel or simple graph.
- Highlight unresolved conflicts and show document version/date metadata.
- Allow clicking a node to open the source passage.

### Post-hackathon expansion

- Persist graph records across questions.
- Add entity and cross-document relationships.
- Track which prior answers depend on a particular claim or source.
- Add graph filtering by document, date, status, and relation.
- Add graph diffing when a source changes.

### Architecture changes

- Add claim and evidence-link tables/collections.
- Add an evidence-graph assembly service called after synthesis and critique.
- Add `GET /answers/{answer_id}/evidence-graph`.
- Add a React graph or relationship viewer. For the first version, a nested evidence list is acceptable if a graph library slows delivery.

### Dependencies

- Stable document and chunk IDs.
- Synthesizer output with claim-level structure.
- Critic output with source references.
- Persisted answer records if graph history is required.

### Acceptance criteria

- Every displayed claim can be traced to its supporting or contradicting passage(s), or is marked unsupported/unverified.
- Clicking a passage opens its source location where available.
- Contradictory links and unresolved conflicts are visually distinguishable.
- The UI never labels a citation as supporting evidence solely because it was retrieved.
- Automated tests validate graph links against known fixture data.

## Feature B — Trust Reports

**Goal:** Explain the quality and limitations of an answer using observable checks.

### MVP / hackathon slice

Generate a report with separate dimensions:

- Evidence coverage: claims with at least one candidate evidence link / total factual claims.
- Citation support: claims whose cited passages were judged to support them / claims evaluated.
- Contradiction status: count and status of detected conflicts.
- Freshness: whether relevant effective-date and supersession metadata is available and consistent with the question.
- Provenance completeness: proportion of evidence records with traceable source IDs and locations.
- Verification status: resolved, unresolved, insufficient evidence, or verification failed.

Show metric definitions and denominators in the UI.

### Post-hackathon expansion

- Calibrate correctness probabilities on a labeled dataset if a defensible calibration method is available.
- Track report changes across model/prompt versions.
- Add domain-specific thresholds and alerts.
- Evaluate whether report metrics correlate with actual correctness.

### Architecture changes

- Add a `trust_report` builder that consumes claims, evidence links, critic findings, and resolution output.
- Persist the report alongside the answer.
- Add `GET /answers/{answer_id}/trust-report`.
- Display dimensions separately rather than collapsing them into a single arbitrary score.

### Dependencies

- Claim extraction and stable claim IDs.
- Evidence links and critic findings.
- Clear definitions for each metric.
- Labeled examples for any claim about calibrated correctness.

### Acceptance criteria

- Every displayed metric has a documented formula and denominator.
- Missing metadata is reported as unknown, not silently treated as fresh or authoritative.
- The report distinguishes evidence coverage from correctness probability.
- A high evidence-coverage value cannot override an unresolved contradiction.
- Tests verify metric calculations on fixed examples.

**Important:** Do not display a number such as “92% trustworthy” unless it is calibrated and validated against representative labeled data. Use transparent dimensions first.

## Feature C — Benchmark & Red-Team Lab

**Goal:** Measure whether TruthGuard improves verification compared with a basic RAG baseline and expose failure modes.

### MVP / hackathon slice

Create a small versioned dataset containing:
- Straightforward answerable questions.
- Direct contradictions.
- Explicitly superseded policies.
- Ambiguous precedence.
- Missing-evidence questions.
- Similar passages that are not true contradictions.

Run the same cases against:
1. Baseline RAG.
2. RAG plus critic.
3. Full TruthGuard with resolution rules.

Report:
- Retrieval recall for relevant evidence.
- Contradiction-detection precision and recall.
- Citation support rate.
- Unsupported-claim rate.
- Correct abstention rate.
- Resolution accuracy on labeled cases.
- Latency and estimated model/API cost where measurable.

### Post-hackathon expansion

- Generate adversarial cases from templates and controlled mutations.
- Add difficulty tiers and regression suites.
- Track results across model, prompt, retriever, and corpus versions.
- Add failure clustering and a review workflow for mislabeled cases.
- Use human-reviewed labels as the benchmark grows.

### Architecture changes

- Add a benchmark runner separate from the interactive question endpoint.
- Store dataset version, configuration, per-case output, and aggregate metrics.
- Add endpoints such as `POST /evaluations/runs` and `GET /evaluations/runs/{run_id}`.
- Add a React dashboard for comparing configurations and drilling into failed cases.

### Dependencies

- Deterministic fixtures and expected labels.
- Stable output schemas.
- A baseline implementation.
- Consistent evaluation rules and versioned prompts/configurations.

### Acceptance criteria

- Every reported metric can be traced to per-case results.
- Baseline and TruthGuard run on the same test questions and corpus.
- The benchmark includes both real contradictions and hard negatives.
- Failed cases can be inspected with retrieved passages and model outputs.
- No improvement claim is made unless measured on the labeled set.
- The benchmark is repeatable with recorded configuration; LLM outputs may still vary unless controlled.

## Feature D — Counterfactual Verification

**Goal:** Test how the answer changes when a source or passage is removed, replaced, or modified.

### Post-hackathon implementation

1. Save the original question, corpus snapshot, retrieval configuration, and answer.
2. Select a source for intervention.
3. Create a controlled corpus view with that source removed or altered.
4. Re-run retrieval, synthesis, critique, and resolution.
5. Compare answers, claim sets, citations, conflicts, and statuses.
6. Report whether the intervention changed the outcome and which evidence drove the change.

### Types of intervention

- Remove one source.
- Remove one passage.
- Replace a source with an older or newer version.
- Change a policy value in a synthetic test document.
- Remove supersession metadata to test sensitivity to provenance.

### Architecture changes

- Add a counterfactual runner that invokes the existing orchestrator with a controlled corpus snapshot.
- Add `POST /counterfactuals` and a result endpoint.
- Persist intervention definitions and paired results.
- Add a React comparison view.

### Dependencies

- Stable source/chunk IDs.
- Reproducible corpus snapshots.
- Versioned prompts and retrieval settings.
- Benchmark cases for expected changes.
- Cost and runtime limits.

### Acceptance criteria

- The intervention is explicit and reproducible.
- Original and counterfactual results are shown side by side.
- The report identifies changes in answer, citations, conflict status, and resolution.
- The system does not claim causal certainty beyond the controlled intervention.
- Tests confirm that removing a known decisive source changes the expected synthetic test outcome.

## Feature E — Human Review Workflow

**Goal:** Allow an authorized reviewer to adjudicate conflicts the system cannot safely resolve.

### Post-hackathon implementation

- Create review cases for unresolved or high-impact conflicts.
- Show source passages, metadata, critic findings, and proposed answer.
- Allow reviewer decisions: resolve in favor of a source, preserve both positions, request more evidence, or leave unresolved.
- Require a rationale for a resolution.
- Record reviewer identity, timestamp, decision, and references to the source versions.
- Preserve the original AI result and create a separate human decision record.

### Architecture changes

- Add review-case, review-decision, and audit-event records.
- Add endpoints for creating, listing, and deciding review cases.
- Add authentication and role/permission checks before exposing sensitive documents.
- Add a React review queue and case detail view.
- Ensure reviewer decisions do not silently modify original source documents.

### Dependencies

- Persisted answer and conflict records.
- Stable evidence references.
- Authentication and authorization.
- Audit log design.
- A defined review policy for the chosen domain.

### Acceptance criteria

- Every decision has an actor, timestamp, rationale, and evidence references.
- The original AI answer and critic findings remain available after review.
- Unauthorized users cannot view or decide restricted cases.
- A reviewer can explicitly leave a case unresolved.
- Audit events are append-only at the application level and protected against ordinary edits.

## Feature F — Continuous Monitoring

**Goal:** Detect changes in a document corpus and re-verify answers that may be affected.

### Post-hackathon implementation

1. Ingest a new or modified document.
2. Compare content hashes and metadata with the previous version.
3. Identify changed chunks and explicit supersession relationships.
4. Find prior claims and answers linked to affected sources.
5. Re-run verification for those dependent answers.
6. Generate a change-impact report and optionally create review cases.
7. Notify users through a chosen channel once the workflow is reliable.

### Architecture changes

- Add a document-change detector.
- Store document versions and content hashes.
- Maintain source-to-claim and source-to-answer dependency links.
- Add a background job queue if scanning becomes too slow for request/response handling.
- Add monitoring status and change-impact views in React.
- Add a controlled rescan endpoint; scheduled or webhook-based triggers can come later.

### Dependencies

- Reliable document versioning and stable IDs.
- Evidence graph and answer history.
- Source dependency tracking.
- Background processing and retry behavior.
- Defined monitoring scope and permissions.

### Acceptance criteria

- Exact duplicate files do not create unnecessary reprocessing.
- A changed source creates a new version or a recorded change, not silent history loss.
- Dependent answers are marked for re-verification when relevant evidence changes.
- The system records which versions were checked and the outcome.
- Failed scans are visible and retryable.
- Notifications are sent only after a change has been recorded successfully.

## 5. Milestones

### Milestone 0 — Shared foundation

**Target:** First implementation step.

Deliver:
- Stable IDs and typed schemas.
- Persisted document metadata and chunk references.
- Claim-level answer structure.
- A small labeled corpus and baseline RAG.

**Exit criteria:** The same test question can be run, inspected, and compared using stable source references.

### Milestone 1 — Hackathon showcase

**Target:** Under one week.

Deliver:
- Evidence Graph thin slice.
- Trust Report with transparent dimensions.
- Small Benchmark & Red-Team Lab.
- Existing retrieval → synthesis → critique → resolution workflow.
- Three reliable demo cases: superseded source, unresolved conflict, insufficient evidence.

**Exit criteria:** A judge can inspect the evidence, see the conflict, and compare measured results against baseline RAG.

### Milestone 2 — Verification workbench

**Target:** First post-hackathon iteration.

Deliver:
- Persisted evidence graph and answer history.
- Counterfactual verification.
- Human review queue and audit trail.
- Expanded regression benchmark.

**Exit criteria:** A user can inspect a past decision, test source sensitivity, and record a human resolution without overwriting the original AI result.

### Milestone 3 — Continuously maintained knowledge

**Target:** Later product iteration.

Deliver:
- Document version/change detection.
- Dependency-based re-verification.
- Change-impact reports.
- Notifications and review-case creation.
- Permission-aware integrations.

**Exit criteria:** A corpus change can be traced to affected evidence and answers, with re-verification outcomes recorded.

## 6. Suggested repository structure

```text
truthguard/
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       └── features/
│           ├── evidence-graph/
│           ├── trust-reports/
│           ├── evaluations/
│           ├── counterfactuals/
│           ├── reviews/
│           └── monitoring/
├── backend/
│   └── app/
│       ├── api/
│       ├── agents/
│       │   ├── retriever.py
│       │   ├── synthesizer.py
│       │   └── critic.py
│       ├── services/
│       │   ├── orchestrator.py
│       │   ├── resolver.py
│       │   ├── evidence_graph.py
│       │   ├── trust_report.py
│       │   ├── evaluation_runner.py
│       │   ├── counterfactual_runner.py
│       │   └── change_monitor.py
│       ├── schemas/
│       ├── db/
│       └── jobs/
├── datasets/
│   ├── fixtures/
│   └── benchmark/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evaluation/
└── docs/
    ├── architecture.md
    └── evaluation-methodology.md
```

Do not create empty modules for every future feature immediately. Add folders when implementation begins; the structure above is a target layout.

## 7. Cross-cutting engineering requirements

- **Provenance:** Every finding must point to the source version and passage used.
- **Security:** Treat retrieved text as untrusted input; prevent prompt injection from changing system behavior or expanding tool permissions.
- **Privacy:** Enforce access control before retrieval and before returning citations.
- **Observability:** Record latency, model calls, errors, retries, and cost where available.
- **Reproducibility:** Save corpus snapshot, prompts, model identifiers, retrieval settings, and evaluation dataset version.
- **Failure handling:** Timeouts and malformed model outputs must not be interpreted as successful verification.
- **Human accountability:** High-impact or ambiguous decisions should remain reviewable; never represent the system as guaranteeing truth.

## 8. Final prioritization

For the hackathon, build **Evidence Graph + Trust Reports + a small Benchmark & Red-Team Lab** on top of the existing architecture.

After the demo is stable, implement **Counterfactual Verification** and **Human Review Workflow**. Add **Continuous Monitoring** once source versioning, evidence dependencies, and answer history are reliable.

The key measure of progress is not how many agents or features TruthGuard contains. It is whether it can expose evidence, detect meaningful conflicts, explain its decisions, and acknowledge when the available information is insufficient.
