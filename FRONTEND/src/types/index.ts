/** TypeScript types that mirror the backend models.
 *  Keep in sync with AGENT/truthguard_agent/schemas/models.py and
 *  BACKEND/app/schemas/documents.py. Missing metadata stays null – never invent it.
 */

export type BackendStatus = 'checking' | 'connected' | 'offline'

export interface HealthResponse {
  status: string
}

// ---- Enums (match enums.py exactly) ----

export type AuthorityLevel = 'official' | 'draft' | 'informal' | 'unknown'

export type AnswerStatus =
  | 'resolved'
  | 'conflict_unresolved'
  | 'insufficient_evidence'
  | 'verification_failed'

// ---- Document types ----

/** Upload payload — mirrors DocumentCreate in BACKEND/app/schemas/documents.py */
export interface DocumentCreate {
  document_id: string
  title: string
  content: string
  version: string | null
  effective_date: string | null   // ISO date string (YYYY-MM-DD) or null
  authority_level: AuthorityLevel
  supersedes_document_id: string | null
  source: string | null
}

/** Response from GET /documents and POST /documents — mirrors DocumentSummary */
export interface DocumentSummary {
  document_id: string
  title: string
  version: string | null
  created_at: string | null
  effective_date: string | null
  authority_level: AuthorityLevel
  supersedes_document_id: string | null
  source: string | null
  content_hash: string
  ingested_at: string
  chunk_count: number
}

// ---- Answer / Question types ----
// Mirror AGENT/truthguard_agent/schemas/models.py and AGENT/truthguard_agent/orchestrator.py.

export interface EvidenceRef {
  source_id: string
  chunk_id: string
}

export type ClaimStatus = 'supported' | 'contradicted' | 'partially_supported' | 'unsupported' | 'unverified'
export type EvidenceRelation = 'supports' | 'contradicts' | 'context'
/** What a claim is in the answer. */
export type ClaimRole = 'current' | 'superseded' | 'conflict_side' | 'unsupported'

export interface Claim {
  claim_id: string
  answer_id: string
  text: string
  claim_type: string
  status: ClaimStatus
}

export interface EvidenceLink {
  claim_id: string
  chunk_id: string
  source_id: string
  relation: EvidenceRelation
  rationale: string
  verifier_version: string
}

export interface FinalAnswer {
  answer_id: string
  question: string
  answer: string
  status: AnswerStatus
  citations: EvidenceRef[]
  conflicts_detected: number
  resolution_reason: string | null
  claims: Claim[]
  evidence_links: EvidenceLink[]
  created_at: string
  model_version: string | null
  prompt_version: string | null
}

/** One retrieved passage with the metadata a reader needs to judge it. */
export interface PassageView {
  chunk_id: string
  document_id: string
  title: string
  text: string
  version: string | null
  effective_date: string | null
  authority_level: AuthorityLevel
  supersedes_document_id: string | null
  score: number | null
  in_scope: boolean
}

export interface ConflictVerdict {
  claim: string
  severity: 'low' | 'medium' | 'high'
  source_ids: string[]
  evidence: EvidenceRef[]
  status: AnswerStatus
  winner_source_ids: string[]
  reason: string
}

export interface StalenessFinding {
  source_id: string
  reason: string
  evidence: EvidenceRef[]
}

export interface UnsupportedClaimFinding {
  claim: string
  evidence: EvidenceRef[]
}

/** Everything behind an answer. */
export interface Verification {
  as_of: string
  stage: 'retrieval' | 'synthesis' | 'critic' | 'resolution'
  critic_ok: boolean
  passages: PassageView[]
  scope_document_ids: string[]
  conflicts: ConflictVerdict[]
  stale: StalenessFinding[]
  unsupported: UnsupportedClaimFinding[]
  winning_source_ids: string[]
  stale_source_ids: string[]
  claim_roles: Record<string, ClaimRole>
  caveats: string[]
  off_topic_ignored: number
  failure_reason: string | null
  model_attempts: number
  timings_ms: Record<string, number>
}

/** Response of POST /questions and GET /answers/{id}. */
export interface AnswerResponse {
  answer: FinalAnswer
  verification: Verification
  llm_mode: 'live' | 'record' | 'cache' | 'replay'
}

export interface AnswerSummary {
  answer_id: string
  question: string
  status: AnswerStatus
  as_of: string | null
  created_at: string
}

// ---- Benchmark (mirrors AGENT/truthguard_agent/evaluation) ----

export type ConfigName = 'baseline' | 'rag_critic' | 'full'

export interface Metric {
  key: string
  label: string
  definition: string
  numerator: number | null
  denominator: number | null
  value: number | null
  unit: 'ratio' | 'ms'
  higher_is_better: boolean | null
  applies: boolean
  note: string
}

export interface BenchmarkCase {
  case_id: string
  case_type: string
  question: string
  as_of: string
  expected_status: AnswerStatus
  relevant_document_ids: string[]
  expected_winner_document_ids: string[]
  expected_stale_document_ids: string[]
  expected_answer_contains: string[][]
  forbidden_answer_contains: string[]
  note: string
}

export interface CaseResult {
  case_id: string
  config: ConfigName
  repeat: number
  status: AnswerStatus
  answer: string
  answer_id: string | null
  citation_document_ids: string[]
  retrieved_document_ids: string[]
  winner_document_ids: string[]
  stale_document_ids: string[]
  conflicts_detected: number
  claims_total: number
  claims_supported: number
  latency_ms: number
  failure_reason: string | null
}

export interface BenchmarkRun {
  run_id: string
  created_at: string
  dataset_version: string
  settings: Record<string, unknown>
  config_labels: Record<ConfigName, string>
  cases: BenchmarkCase[]
  results: CaseResult[]
  metrics: Record<ConfigName, Record<string, Metric>>
  consistency: Record<ConfigName, Record<string, number>>
}

