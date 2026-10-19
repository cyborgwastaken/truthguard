# TruthGuard — Hackathon Implementation Plan

## 1. Project Overview

**TruthGuard** is a multi-agent document question-answering system designed to detect contradictions, identify stale or superseded documents, flag unsupported claims, and explain how answers were resolved.

### Problem

Document collections often contain conflicting policy versions, outdated FAQs, and amendments. Conventional retrieval-augmented generation (RAG) can retrieve and summarize these sources without reliably exposing the conflict.

### Goal

Build a demonstrable MVP that answers questions from a curated document corpus while showing evidence, conflicts, document provenance, and uncertainty.

### Hackathon Constraints

- **Timeline:** Under one week; plan assumes five working days.
- **Team:** Mixed software development and AI/ML skills.
- **Scope:** A focused, reliable workflow rather than a general-purpose autonomous agent platform.
- **Data:** Use fictional or public documents; avoid confidential material.

## 2. MVP Success Criteria

By the end of the hackathon, a judge should be able to:

1. Upload or ingest a small set of documents with version and date metadata.
2. Ask a natural-language question about the corpus.
3. See an answer with source citations.
4. See conflicting passages and why a document may be stale or superseded.
5. Receive an explicit uncertainty response when the evidence cannot resolve a conflict.
6. Compare TruthGuard's behavior with a basic RAG baseline on a small, labeled test set.

### Required Demo Scenarios

- **Superseded policy:** An explicit, effective amendment changes an earlier rule; the system explains why the amendment takes precedence.
- **Unresolved conflict:** Two equally authoritative sources disagree and the system presents both instead of guessing.
- **Insufficient evidence:** The corpus does not support an answer, so the system abstains rather than inventing one.

## 3. Proposed Architecture

```text
React / Next.js Frontend
  ├── Chat interface
  ├── Citation and evidence viewer
  ├── Conflict comparison
  └── Document version timeline
             |
             v
FastAPI Backend
  ├── Document ingestion API
  ├── Question API
  └── Request validation
             |
             v
Orchestrator (Python)
  ├── Retriever
  ├── Synthesizer
  ├── Critic / Adversary
  └── Resolution Engine
             |
             +----------------------+
             |                      |
             v                      v
Document Store              Retrieval Index
  ├── Original text          ├── BM25 / full-text
  ├── Chunks                 └── Embeddings / vectors
  └── Version metadata
```

The three agents are the core workflow. The orchestrator controls execution order and shared state; the resolution engine applies explicit rules to findings. These are implementation components, not extra agents.

### End-to-End Question Flow

1. Validate the user's question.
2. Retrieve relevant passages using keyword and semantic search.
3. Return passage text with source IDs and metadata.
4. Draft a candidate answer with claim-level citations.
5. Ask the critic to check:
   - Direct contradictions between retrieved sources.
   - Staleness and explicit supersession.
   - Claims unsupported by the retrieved evidence.
6. Resolve only when provenance and metadata support a decision.
7. If the conflict remains ambiguous, present both positions and state that it cannot be resolved from available information.
8. Return an answer, citations, detected conflicts, resolution rationale, and status to the UI.

## 4. Suggested Technology Stack

Choose tools the team already knows where possible.

- **Frontend:** React or Next.js, with Tailwind CSS if useful.
- **Backend:** Python, FastAPI, Pydantic.
- **Storage:** PostgreSQL for document metadata and content.
- **Retrieval:** PostgreSQL full-text search (BM25-style keyword retrieval can be added) plus an embedding model and pgvector, if time permits.
- **LLM:** One capable LLM for synthesis and critique initially; use structured outputs for predictable contracts.
- **Testing:** Pytest plus a small hand-labeled evaluation set.
- **Deployment:** Use the simplest deployment option already familiar to the team. Do not make deployment a blocker for the core demo.

A custom autonomous-agent framework is not necessary for the initial fixed workflow. A simple Python orchestrator is sufficient.

## 5. Components and Responsibilities

### 5.1 Document Ingestion

Responsibilities:
- Accept text or supported document files.
- Normalize text and split it into retrievable chunks.
- Store source ID, title, version, effective date, creation date, authority level, and explicit supersession metadata when available.
- Preserve the original text and stable chunk IDs for citations.

Do not assume all documents contain complete metadata. Missing or ambiguous metadata must remain unknown rather than being fabricated.

### 5.2 Retriever Agent

Input: User question.

Output:
- Ranked passages.
- Stable source and chunk IDs.
- Relevant metadata.
- Retrieval scores where available.

MVP approach:
- Start with keyword/full-text search.
- Add semantic retrieval if it improves the test cases.
- Retrieve enough passages to expose likely contradictions; do not only return the single top match.

### 5.3 Synthesizer Agent

Input: Question and retrieved passages.

Output:
- Candidate answer.
- Atomic claims.
- Citation IDs supporting each claim.
- Unknowns or caveats.

Requirements:
- Use only retrieved evidence for factual claims.
- Attach citations to the claims they support.
- Do not hide disagreement between sources.

### 5.4 Critic / Adversary Agent

Input: Question, candidate answer, retrieved passages, and metadata.

Output:
- Contradictions with supporting source IDs.
- Potentially stale or superseded sources and reasons.
- Unsupported claims.
- Whether the conflict needs resolution.

Use deterministic checks for dates and explicit metadata where possible. Use the LLM for semantic comparison and claim-support judgments. The critic must provide evidence references for every flagged issue.

### 5.5 Resolution Engine

Responsibilities:
- Apply explicit supersession and effective-date rules.
- Consider source authority only when the corpus defines it.
- Preserve provenance in the final answer.
- Surface both positions if the evidence establishes a conflict but not precedence.
- Abstain when evidence is insufficient.

Do not automatically choose the newest document unless the available metadata or policy establishes that it supersedes the older one.

## 6. Data Contracts

### Document Metadata

```json
{
  "document_id": "remote_policy_amendment_v2",
  "title": "Remote Work Policy Amendment",
  "version": "2",
  "created_at": "2026-10-01",
  "effective_date": "2026-10-01",
  "authority_level": "official",
  "supersedes_document_id": "remote_policy_v1",
  "content": "Example policy text..."
}
```

All values are illustrative. Store missing fields as unknown/null rather than inventing them.

### Critic Result

```json
{
  "contradictions": [
    {
      "claim": "Employees may work remotely five days a week",
      "source_ids": [
        "remote_policy_v1",
        "remote_policy_amendment_v2"
      ],
      "severity": "high",
      "evidence": [
        {
          "source_id": "remote_policy_v1",
          "chunk_id": "chunk_001"
        },
        {
          "source_id": "remote_policy_amendment_v2",
          "chunk_id": "chunk_014"
        }
      ]
    }
  ],
  "staleness": [
    {
      "source_id": "remote_policy_v1",
      "reason": "Explicitly superseded by an effective amendment"
    }
  ],
  "unsupported_claims": [],
  "needs_resolution": true
}
```

This is a target schema example, not a verified model output.

### Final Answer

```json
{
  "answer": "The current limit is three remote-work days per week.",
  "status": "resolved",
  "citations": [
    {
      "source_id": "remote_policy_amendment_v2",
      "chunk_id": "chunk_014"
    }
  ],
  "conflicts_detected": 1,
  "resolution_reason": "The effective amendment explicitly supersedes version 1."
}
```

Possible statuses:
- `resolved`
- `conflict_unresolved`
- `insufficient_evidence`

Only use `resolved` when the evidence supports that decision.

## 7. API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/documents` | Ingest a document |
| GET | `/documents` | List documents and versions |
| POST | `/questions` | Run the verification pipeline |
| GET | `/questions/{id}` | Retrieve a saved result, if persistence is implemented |
| GET | `/health` | Basic service health check |

Keep the API contract small. Add authentication, background jobs, and advanced access control only if required by the hackathon.

## 8. Five-Day Execution Plan

### Day 1 — Foundation and Corpus

- Agree on metadata and response schemas.
- Create 15–30 fictional policy documents with deliberate conflicts.
- Implement ingestion and document storage.
- Implement baseline keyword retrieval.

**Exit criterion:** A question returns relevant passages with stable source IDs.

### Day 2 — Question Answering

- Implement the synthesizer.
- Require claim-level citations.
- Build the FastAPI question endpoint.
- Build a basic chat UI with evidence display.

**Exit criterion:** End-to-end Q&A works for non-conflicting documents.

### Day 3 — Critic and Conflict Detection

- Implement structured critic output.
- Detect contradictions across retrieved passages.
- Check explicit supersession and effective dates.
- Flag unsupported claims.

**Exit criterion:** The critic flags known conflicts and cites the passages involved.

### Day 4 — Resolution and Evaluation

- Implement the resolution engine.
- Support unresolved-conflict and insufficient-evidence outcomes.
- Test the required demo scenarios.
- Compare against baseline RAG and fix high-impact failures.

**Exit criterion:** All three demo scenarios produce appropriate outcomes.

### Day 5 — UI Polish and Demo

- Add side-by-side evidence comparison.
- Show version/date metadata and conflict status.
- Add loading and error states.
- Run the evaluation set and record results.
- Rehearse a short demo; prepare a fallback recording.

**Exit criterion:** A repeatable demo works from a clean start.

If only three days are available, reduce the corpus and UI polish. Preserve source-grounded conflict detection, transparent resolution, and abstention.

## 9. Team Work Split

For a four-person team:

1. **Backend:** APIs, ingestion, metadata, persistence.
2. **AI/ML:** retrieval, synthesis, critic prompts, structured outputs.
3. **Frontend:** chat, citations, conflict comparison, timeline.
4. **Integration and evaluation:** labeled corpus, tests, orchestration integration, demo and documentation.

For smaller teams, combine frontend with integration or backend with orchestration. Agree on schemas and API contracts before parallel implementation.

## 10. Evaluation Plan

Create a small labeled test set with:
- Questions with a clear answer.
- Direct contradictions.
- Explicitly superseded documents.
- Ambiguous precedence.
- Missing evidence.
- Similar wording that is not a genuine contradiction.

Track:
- Retrieval recall for relevant evidence.
- Contradiction-detection precision and recall.
- Citation support rate.
- Unsupported-claim rate.
- Correct resolution and abstention rate.
- End-to-end latency and failure rate.

Compare TruthGuard with a simple RAG baseline on the same questions. Report actual results; do not claim improvements without measurements.

## 11. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Critic hallucinations | Require exact evidence references for each finding |
| Incorrect newest-document wins | Use explicit supersession, effective dates and defined authority |
| Too much framework work | Use a simple Python orchestrator |
| LLM output format failures | Validate with Pydantic; retry once or fail safely |
| Weak demo corpus | Curate examples with known expected outcomes |
| No proof of improvement | Benchmark against baseline RAG |
| Prompt injection in documents | Treat retrieved text as untrusted data; do not let it override system instructions or grant tools |
| Time lost on UI | Finish a minimal end-to-end workflow before visual polish |

## 12. Out of Scope for the Hackathon MVP

Unless the core system is already stable, defer:
- Autonomous agent loops with unlimited retries.
- Fine-tuning custom language models.
- Complex role-based access control.
- Real-time collaborative editing.
- Support for every file format.
- Large-scale distributed infrastructure.
- Claims of guaranteed factual correctness.

## 13. Demo Script

1. Ask a straightforward question and show a sourced answer.
2. Ask about a policy with an explicit amendment and show the conflict plus resolution rationale.
3. Ask about two equally authoritative documents that disagree and show the unresolved-conflict state.
4. Ask about information absent from the corpus and show abstention.
5. Briefly compare the result with baseline RAG and present measured evaluation results.

## 14. Definition of Done

- [ ] Documents can be ingested with stable IDs and metadata.
- [ ] Questions retrieve multiple relevant passages.
- [ ] Answers include source-grounded citations.
- [ ] The critic returns structured contradiction, staleness, and unsupported-claim findings.
- [ ] Resolution respects explicit provenance and supersession rules.
- [ ] Unresolved conflicts and missing evidence are surfaced honestly.
- [ ] The three required demo scenarios work.
- [ ] A baseline comparison and evaluation results are available.
- [ ] Setup instructions and a reliable demo path are documented.

---

**Guiding principle:** TruthGuard is not successful merely because it uses multiple agents. It succeeds when it can expose conflicting evidence, explain what supports its conclusion, and admit when the evidence is insufficient.
