import { useState, useEffect, useCallback, useId } from 'react'
import type { DocumentCreate, DocumentSummary, AuthorityLevel } from '../../types'
import { listDocuments, uploadDocument, ApiError } from '../../api/client'

const AUTHORITY_OPTIONS: AuthorityLevel[] = ['official', 'draft', 'informal', 'unknown']

// The pattern and limits mirror DocumentCreate in BACKEND/app/schemas/documents.py, so mistakes are
// caught here with a clear message; the server still checks everything.
const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.-]*$/
const ID_RULE = 'may contain only letters, digits, "_", "." and "-", and must start with a letter or digit'
const MAX = { id: 200, title: 500, version: 64, content: 1_000_000 }

function validate(form: DocumentCreate): string | null {
  if (!form.document_id || !form.title || !form.content) {
    return 'Document ID, title and content are required.'
  }
  if (!ID_PATTERN.test(form.document_id) || form.document_id.length > MAX.id) {
    return `Document ID ${ID_RULE} (at most ${MAX.id} characters).`
  }
  if (form.supersedes_document_id) {
    if (!ID_PATTERN.test(form.supersedes_document_id) || form.supersedes_document_id.length > MAX.id) {
      return `Supersedes document ID ${ID_RULE} (at most ${MAX.id} characters).`
    }
    if (form.supersedes_document_id === form.document_id) return 'A document cannot supersede itself.'
  }
  if (form.title.length > MAX.title) return `Title is too long (at most ${MAX.title} characters).`
  if (form.version && form.version.length > MAX.version) {
    return `Version is too long (at most ${MAX.version} characters).`
  }
  if (form.content.length > MAX.content) return 'Content is too long (at most 1,000,000 characters).'
  return null
}

function formatDate(val: string | null): string {
  return val ?? 'unknown'
}

function formatAuthority(level: AuthorityLevel): string {
  return level === 'unknown' ? 'unknown' : level.charAt(0).toUpperCase() + level.slice(1)
}

// ---- Document Table ----

interface TableProps {
  docs: DocumentSummary[]
  loading: boolean
  error: string | null
  onRetry: () => void
}

function DocumentTable({ docs, loading, error, onRetry }: TableProps) {
  if (loading) {
    return (
      <div className="doc-table-state" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        Loading documents…
      </div>
    )
  }
  if (error) {
    return (
      <div className="doc-table-state error-state" role="alert">
        <strong>Failed to load documents:</strong> {error}
        <button type="button" className="btn-secondary btn-sm" onClick={onRetry}>
          Retry
        </button>
      </div>
    )
  }
  if (docs.length === 0) {
    return (
      <div className="doc-table-state muted" role="status">
        No documents yet. Upload one using the form above.
      </div>
    )
  }
  return (
    <div className="table-wrap">
      <table className="doc-table" aria-label="Document list">
        <thead>
          <tr>
            <th scope="col">Title</th>
            <th scope="col">Version</th>
            <th scope="col">Effective date</th>
            <th scope="col">Authority</th>
            <th scope="col">Chunks</th>
            <th scope="col">Ingested</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.document_id}>
              <td>
                <span className="doc-title">{d.title}</span>
                <span className="doc-id muted">{d.document_id}</span>
              </td>
              <td>{d.version ?? <span className="muted">unknown</span>}</td>
              <td>{d.effective_date ?? <span className="muted">unknown</span>}</td>
              <td>
                <span className={`authority-badge authority-${d.authority_level}`}>
                  {formatAuthority(d.authority_level)}
                </span>
              </td>
              <td className="num">{d.chunk_count}</td>
              <td className="muted">{formatDate(d.ingested_at?.slice(0, 10) ?? null)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---- Upload Form ----

const EMPTY_FORM: Omit<DocumentCreate, 'content'> & { content: string } = {
  document_id: '',
  title: '',
  content: '',
  version: null,
  effective_date: null,
  authority_level: 'unknown',
  supersedes_document_id: null,
  source: null,
}

interface UploadFormProps {
  onUploaded: (doc: DocumentSummary) => void
}

function UploadForm({ onUploaded }: UploadFormProps) {
  const formId = useId()
  const [form, setForm] = useState(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  function field(name: keyof typeof form, value: string) {
    setForm((prev) => ({ ...prev, [name]: value === '' ? null : value }))
    setSuccess(null)
    setError(null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const problem = validate(form as DocumentCreate)
    if (problem) {
      setError(problem)
      return
    }
    setSubmitting(true)
    setError(null)
    setSuccess(null)
    try {
      const doc = await uploadDocument(form as DocumentCreate)
      setSuccess(`"${doc.title}" uploaded (${doc.chunk_count} chunks).`)
      setForm(EMPTY_FORM)
      setOpen(false)
      onUploaded(doc)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="upload-section">
      <button
        id={`${formId}-toggle`}
        type="button"
        className="btn-primary"
        aria-expanded={open}
        aria-controls={`${formId}-form`}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? '✕ Cancel' : '+ Upload document'}
      </button>

      {success && (
        <p className="inline-success" role="status" aria-live="polite">
          ✓ {success}
        </p>
      )}

      {open && (
        <form
          id={`${formId}-form`}
          className="upload-form"
          onSubmit={handleSubmit}
          aria-label="Upload document"
          noValidate
        >
          <div className="form-row">
            <label className="form-label" htmlFor={`${formId}-id`}>
              Document ID <span className="required">*</span>
            </label>
            <input
              id={`${formId}-id`}
              className="form-input"
              type="text"
              required
              pattern="[A-Za-z0-9][A-Za-z0-9_.\-]*"
              placeholder="e.g. policy-2024-v1"
              value={form.document_id ?? ''}
              onChange={(e) => field('document_id', e.target.value)}
            />
          </div>

          <div className="form-row">
            <label className="form-label" htmlFor={`${formId}-title`}>
              Title <span className="required">*</span>
            </label>
            <input
              id={`${formId}-title`}
              className="form-input"
              type="text"
              required
              placeholder="Document title"
              value={form.title ?? ''}
              onChange={(e) => field('title', e.target.value)}
            />
          </div>

          <div className="form-row">
            <label className="form-label" htmlFor={`${formId}-content`}>
              Content <span className="required">*</span>
            </label>
            <textarea
              id={`${formId}-content`}
              className="form-input form-textarea"
              required
              rows={6}
              placeholder="Paste document text here…"
              value={form.content ?? ''}
              onChange={(e) => field('content', e.target.value)}
            />
          </div>

          <div className="form-grid">
            <div className="form-row">
              <label className="form-label" htmlFor={`${formId}-version`}>
                Version
              </label>
              <input
                id={`${formId}-version`}
                className="form-input"
                type="text"
                placeholder="e.g. 2.1 (leave blank if unknown)"
                value={form.version ?? ''}
                onChange={(e) => field('version', e.target.value)}
              />
            </div>

            <div className="form-row">
              <label className="form-label" htmlFor={`${formId}-date`}>
                Effective date
              </label>
              <input
                id={`${formId}-date`}
                className="form-input"
                type="date"
                value={form.effective_date ?? ''}
                onChange={(e) => field('effective_date', e.target.value)}
              />
            </div>

            <div className="form-row">
              <label className="form-label" htmlFor={`${formId}-authority`}>
                Authority level
              </label>
              <select
                id={`${formId}-authority`}
                className="form-input"
                value={form.authority_level}
                onChange={(e) => field('authority_level', e.target.value)}
              >
                {AUTHORITY_OPTIONS.map((a) => (
                  <option key={a} value={a}>
                    {formatAuthority(a)}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-row">
              <label className="form-label" htmlFor={`${formId}-supersedes`}>
                Supersedes document ID
              </label>
              <input
                id={`${formId}-supersedes`}
                className="form-input"
                type="text"
                placeholder="Leave blank if not applicable"
                value={form.supersedes_document_id ?? ''}
                onChange={(e) => field('supersedes_document_id', e.target.value)}
              />
            </div>
          </div>

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}

          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Uploading…' : 'Upload'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}

// ---- Page ----

export function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // For retry and for the refresh after an upload, which should not flash the spinner.
  const fetchDocs = useCallback(async () => {
    try {
      setDocs(await listDocuments())
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'the backend could not be reached.')
    } finally {
      setLoading(false)
    }
  }, [])

  // The first load. Loading starts true; state is only set in the callbacks, and not at all once the
  // page has been left.
  useEffect(() => {
    let ignore = false
    listDocuments()
      .then((result) => {
        if (!ignore) setDocs(result)
      })
      .catch((err) => {
        if (!ignore) setError(err instanceof ApiError ? err.message : 'the backend could not be reached.')
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [])

  function retry() {
    setLoading(true)
    setError(null)
    void fetchDocs()
  }

  function handleUploaded(doc: DocumentSummary) {
    // show the new row at once, then refresh for the accurate list
    setDocs((prev) => {
      const idx = prev.findIndex((d) => d.document_id === doc.document_id)
      return idx >= 0 ? prev.map((d, i) => (i === idx ? doc : d)) : [doc, ...prev]
    })
    void fetchDocs()
  }

  return (
    <section>
      <h1>Documents</h1>
      <p className="muted page-subtitle">
        Upload and browse source documents. Missing metadata shows as "unknown".
      </p>

      <UploadForm onUploaded={handleUploaded} />

      <h2 className="section-heading">
        Document library
        {!loading && !error && (
          <span className="doc-count muted">({docs.length})</span>
        )}
      </h2>
      <DocumentTable docs={docs} loading={loading} error={error} onRetry={retry} />
    </section>
  )
}
