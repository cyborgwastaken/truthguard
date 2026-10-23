import { useEffect, useRef } from 'react'
import { EvidenceGraphPanel } from './EvidenceGraphView'
import { TrustPanel } from './TrustPanel'
import type {
  AnswerResponse,
  AnswerStatus,
  AuthorityLevel,
  ConflictVerdict,
  PassageView,
  Verification,
} from '../../types'

const STATUS_LABELS: Record<AnswerStatus, string> = {
  resolved: 'Resolved',
  conflict_unresolved: 'Conflict – unresolved',
  insufficient_evidence: 'Insufficient evidence',
  verification_failed: 'Verification failed',
}

export function StatusBadge({ status }: { status: AnswerStatus }) {
  return (
    <span className={`answer-badge answer-badge-${status}`} aria-label={`Status: ${STATUS_LABELS[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  )
}

function Authority({ level }: { level: AuthorityLevel }) {
  return (
    <span className={`authority-badge authority-${level}`}>
      {level === 'unknown' ? 'unknown' : level.charAt(0).toUpperCase() + level.slice(1)}
    </span>
  )
}

type DocRole = 'winner' | 'superseded' | 'none'

function roleOf(documentId: string, v: Verification): DocRole {
  if (v.winning_source_ids.includes(documentId)) return 'winner'
  if (v.stale_source_ids.includes(documentId)) return 'superseded'
  return 'none'
}

const ROLE_TEXT: Record<DocRole, string> = {
  winner: 'Takes precedence',
  superseded: 'Superseded',
  none: '',
}

function shorten(text: string, max = 380): string {
  return text.length <= max ? text : text.slice(0, max).trimEnd() + '…'
}

// ---- Passage dialog (opens when a citation is clicked) ----

interface DialogProps {
  passage: PassageView
  verification: Verification
  onClose: () => void
}

export function PassageDialog({ passage, verification, onClose }: DialogProps) {
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const role = roleOf(passage.document_id, verification)
  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={`Source passage from ${passage.title}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="dialog-head">
          <div>
            <strong>{passage.title}</strong>
            <div className="muted dialog-id">{passage.document_id} · {passage.chunk_id}</div>
          </div>
          <button ref={closeRef} type="button" className="btn-secondary btn-sm" onClick={onClose}>
            Close
          </button>
        </div>
        <dl className="meta-grid">
          <dt>Authority</dt>
          <dd><Authority level={passage.authority_level} /></dd>
          <dt>Effective date</dt>
          <dd>{passage.effective_date ?? <span className="muted">unknown</span>}</dd>
          <dt>Version</dt>
          <dd>{passage.version ?? <span className="muted">unknown</span>}</dd>
          <dt>Supersedes</dt>
          <dd>{passage.supersedes_document_id ?? <span className="muted">nothing</span>}</dd>
          {role !== 'none' && (
            <>
              <dt>In this answer</dt>
              <dd><span className={`col-tag col-${role}`}>{ROLE_TEXT[role]}</span></dd>
            </>
          )}
        </dl>
        <blockquote className="passage-text">{passage.text}</blockquote>
      </div>
    </div>
  )
}

// ---- Conflict comparison ----

function ConflictCard({
  conflict,
  verification,
  onOpen,
  showReason,
}: {
  conflict: ConflictVerdict
  verification: Verification
  onOpen: (chunkId: string) => void
  showReason: boolean
}) {
  const sources = Array.from(new Set([...conflict.source_ids, ...conflict.winner_source_ids]))
  const resolved = conflict.status === 'resolved'
  return (
    <section className={`conflict ${resolved ? 'conflict-resolved' : 'conflict-open'}`} aria-label="Conflict between sources">
      <header className="conflict-head">
        <strong>Sources disagree: {conflict.claim}</strong>
        <span className={`col-tag ${resolved ? 'col-winner' : 'col-open'}`}>
          {resolved ? 'Resolved by the metadata' : 'Unresolved: no precedence'}
        </span>
      </header>
      <div className="conflict-cols">
        {sources.map((id) => {
          const inEvidence = conflict.evidence.filter((e) => e.source_id === id).map((e) => e.chunk_id)
          const passage =
            verification.passages.find((p) => inEvidence.includes(p.chunk_id)) ??
            verification.passages.find((p) => p.document_id === id)
          const role = roleOf(id, verification)
          const tag = role !== 'none' ? ROLE_TEXT[role] : resolved ? 'Not preferred' : 'No precedence'
          const tagClass = role !== 'none' ? `col-${role}` : resolved ? 'col-stale' : 'col-open'
          return (
            <article key={id} className={`conflict-col col-border-${role}`}>
              <div className="conflict-col-head">
                <strong>{passage?.title ?? id}</strong>
                <span className={`col-tag ${tagClass}`}>{tag}</span>
              </div>
              {passage && (
                <>
                  <div className="conflict-meta">
                    <Authority level={passage.authority_level} />
                    <span>effective {passage.effective_date ?? 'unknown'}</span>
                    {passage.version && <span>v{passage.version}</span>}
                  </div>
                  <p className="conflict-text">{shorten(passage.text)}</p>
                  <button type="button" className="link-btn" onClick={() => onOpen(passage.chunk_id)}>
                    Open full passage
                  </button>
                </>
              )}
            </article>
          )
        })}
      </div>
      {showReason && <p className="muted conflict-reason">{conflict.reason}</p>}
    </section>
  )
}

// ---- The answer ----

interface Props {
  response: AnswerResponse
  onOpenPassage: (chunkId: string) => void
}

export function AnswerView({ response, onOpenPassage }: Props) {
  const { answer, verification: v } = response
  const byChunk = new Map(v.passages.map((p) => [p.chunk_id, p]))
  const insufficient = answer.status === 'insufficient_evidence'
  const failed = answer.status === 'verification_failed'
  const notUsed = answer.claims.filter((c) => {
    const role = v.claim_roles[c.claim_id]
    return role === 'superseded' || role === 'unsupported'
  })
  const titleOf = (id: string) => v.passages.find((p) => p.document_id === id)?.title ?? id
  const shownInConflicts = new Set(v.conflicts.flatMap((c) => [...c.source_ids, ...c.winner_source_ids]))

  return (
    <div className="msg-bubble msg-answer answer-card">
      <div className="answer-head">
        <StatusBadge status={answer.status} />
        <span className="tag">as of {v.as_of}</span>
        {response.llm_mode === 'replay' && (
          <span className="tag tag-replay" title="Recorded model replies were used, not a live call">
            Replayed recording
          </span>
        )}
      </div>

      {failed ? (
        <div className="failed-block" role="alert">
          <strong>Verification failed at the {v.stage} stage.</strong> No answer is shown, because the check did not
          finish. {answer.resolution_reason}
        </div>
      ) : insufficient ? (
        <p className="answer-text">
          <strong>Not answered:</strong> the documents do not contain enough information to answer this question.
        </p>
      ) : (
        <p className="answer-text">{answer.answer}</p>
      )}

      {answer.resolution_reason && !failed && (
        <p className="answer-why">
          <strong>Why:</strong> {answer.resolution_reason}
        </p>
      )}

      {v.stale.filter((s) => !shownInConflicts.has(s.source_id)).map((s) => (
        <p key={s.source_id} className="stale-banner" role="note">
          <strong>Outdated source:</strong> {titleOf(s.source_id)} ({s.source_id}) is not current. {s.reason}.
        </p>
      ))}

      {answer.citations.length > 0 && (
        <div className="citations">
          <span className="muted">Sources:</span>
          <ul className="chips">
            {answer.citations.map((c) => {
              const p = byChunk.get(c.chunk_id)
              const role = roleOf(c.source_id, v)
              return (
                <li key={c.chunk_id}>
                  <button
                    type="button"
                    className={`chip chip-${role}`}
                    onClick={() => onOpenPassage(c.chunk_id)}
                    aria-label={`Open the source passage from ${p?.title ?? c.source_id}`}
                  >
                    {p?.title ?? c.source_id}
                    {p?.version ? ` · v${p.version}` : ''}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {v.conflicts.map((c, i) => (
        <ConflictCard key={i} conflict={c} verification={v} onOpen={onOpenPassage} showReason={v.conflicts.length > 1} />
      ))}

      {notUsed.length > 0 && (
        <details className="more">
          <summary>Statements not used in the answer ({notUsed.length})</summary>
          <ul className="not-used">
            {notUsed.map((c) => (
              <li key={c.claim_id}>
                <s>{c.text}</s>{' '}
                <span className="muted">
                  {v.claim_roles[c.claim_id] === 'superseded'
                    ? '(from a source that a newer document replaces)'
                    : '(its cited passage does not back it up)'}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {v.caveats.length > 0 && (
        <details className="more">
          <summary>Notes from the model ({v.caveats.length})</summary>
          <ul className="not-used">
            {v.caveats.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
          <p className="muted">Shown for information. They never decide the status.</p>
        </details>
      )}

      <EvidenceGraphPanel answerId={answer.answer_id} onOpenPassage={onOpenPassage} />
      <TrustPanel answerId={answer.answer_id} />

      <details className="more">
        <summary>How this was checked</summary>
        <ul className="not-used">
          <li>Retrieved {new Set(v.passages.map((p) => p.document_id)).size} documents; the check looked at {v.scope_document_ids.length} that the answer relies on.</li>
          <li>Last stage reached: {v.stage}. Model calls: {v.model_attempts}. {v.off_topic_ignored > 0 && `${v.off_topic_ignored} unrelated disagreement(s) ignored.`}</li>
          <li>
            Time: {Object.entries(v.timings_ms).map(([k, ms]) => `${k} ${(ms / 1000).toFixed(1)} s`).join(', ') || 'n/a'}
          </li>
          <li className="muted">{answer.model_version} · {answer.prompt_version}</li>
        </ul>
      </details>
    </div>
  )
}
