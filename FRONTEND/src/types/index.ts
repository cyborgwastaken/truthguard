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

/** Mirrors EvidenceRef in models.py */
export interface EvidenceRef {
  source_id: string
  chunk_id: string
}

/** Mirrors FinalAnswer in models.py */
export interface FinalAnswer {
  answer_id: string
  question: string
  answer: string
  status: AnswerStatus
  citations: EvidenceRef[]
  conflicts_detected: number
  resolution_reason: string | null
  created_at: string
}
