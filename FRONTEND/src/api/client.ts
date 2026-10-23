import type {
  AnswerResponse,
  AnswerSummary,
  BenchmarkRun,
  DocumentCreate,
  DocumentSummary,
  EvidenceGraph,
  HealthResponse,
  TrustReport,
} from '../types'

/** Backend address. Override with VITE_API_URL in FRONTEND/.env.local */
export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** FastAPI sends `detail` as a string for 404/409 and as a list of { loc, msg } objects for 422. */
export function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          const { loc, msg } = item as { loc?: unknown; msg: unknown }
          const field = Array.isArray(loc) ? loc.filter((part) => part !== 'body').join('.') : ''
          return field ? `${field}: ${String(msg)}` : String(msg)
        }
        return String(item)
      })
      .join('; ')
  }
  return ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      detail = formatDetail(body?.detail) || detail
    } catch { /* ignore */ }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

// ---- Health ----

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { signal })
}

// ---- Documents (T06 backend is live) ----

export function listDocuments(signal?: AbortSignal): Promise<DocumentSummary[]> {
  return request<DocumentSummary[]>('/documents', { signal })
}

export function uploadDocument(payload: DocumentCreate): Promise<DocumentSummary> {
  return request<DocumentSummary>('/documents', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

// ---- Questions and answers ----

/** Runs the full verification pipeline. With the real model this takes several seconds. */
export function askQuestion(question: string, asOf?: string, signal?: AbortSignal): Promise<AnswerResponse> {
  return request<AnswerResponse>('/questions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, as_of: asOf ?? null }),
    signal,
  })
}

export function getAnswer(answerId: string, signal?: AbortSignal): Promise<AnswerResponse> {
  return request<AnswerResponse>(`/answers/${encodeURIComponent(answerId)}`, { signal })
}

export function listAnswers(limit = 20, signal?: AbortSignal): Promise<AnswerSummary[]> {
  return request<AnswerSummary[]>(`/answers?limit=${limit}`, { signal })
}

export function getTrustReport(answerId: string, signal?: AbortSignal): Promise<TrustReport> {
  return request<TrustReport>(`/answers/${encodeURIComponent(answerId)}/trust-report`, { signal })
}

export function getEvidenceGraph(answerId: string, signal?: AbortSignal): Promise<EvidenceGraph> {
  return request<EvidenceGraph>(`/answers/${encodeURIComponent(answerId)}/evidence-graph`, { signal })
}

// ---- Benchmark ----

/** The latest benchmark run. 404 (ApiError) until `python -m app.benchmark` has been run once. */
export function getLatestBenchmark(signal?: AbortSignal): Promise<BenchmarkRun> {
  return request<BenchmarkRun>('/evaluations/latest', { signal })
}
