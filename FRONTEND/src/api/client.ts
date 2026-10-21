import type { DocumentCreate, DocumentSummary, FinalAnswer, HealthResponse } from '../types'

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (body?.detail) detail = String(body.detail)
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

// ---- Questions (T14 not yet merged: uses a mock) ----
// Swap the body of this function for a real fetch when T14 lands.

export async function askQuestion(question: string, _signal?: AbortSignal): Promise<FinalAnswer> {
  // MOCK – returns after a short delay so loading states are exercised
  await new Promise((r) => setTimeout(r, 800))
  return {
    answer_id: 'mock-' + Date.now(),
    question,
    answer:
      'This is a mock answer. Connect the real POST /questions endpoint when T14 is merged.',
    status: 'resolved',
    citations: [],
    conflicts_detected: 0,
    resolution_reason: null,
    created_at: new Date().toISOString(),
  }
}
