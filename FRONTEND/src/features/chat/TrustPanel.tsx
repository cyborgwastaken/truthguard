import { useEffect, useState } from 'react'
import { ApiError, getTrustReport } from '../../api/client'
import type { TrustDimension, TrustLevel, TrustReport } from '../../types'

const LEVEL_TEXT: Record<TrustLevel, string> = {
  ok: 'OK',
  attention: 'Needs attention',
  problem: 'Problem',
  unknown: 'Unknown',
}

function Dimension({ d }: { d: TrustDimension }) {
  return (
    <li className={`trust-dim trust-${d.level}`}>
      <div className="trust-dim-head">
        <strong>{d.label}</strong>
        <span className={`trust-level trust-level-${d.level}`}>{LEVEL_TEXT[d.level]}</span>
        {d.denominator !== null && d.numerator !== null && (
          <span className="muted trust-frac">{d.numerator} of {d.denominator}</span>
        )}
      </div>
      <p className="trust-detail">{d.detail}</p>
      <p className="muted trust-def">{d.definition}</p>
    </li>
  )
}

/** Loads the report when the section is opened, not before. */
export function TrustPanel({ answerId }: { answerId: string }) {
  const [open, setOpen] = useState(false)
  const [report, setReport] = useState<TrustReport | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || report) return
    let ignore = false
    getTrustReport(answerId)
      .then((r) => { if (!ignore) setReport(r) })
      .catch((err) => { if (!ignore) setError(err instanceof ApiError ? err.message : 'The backend could not be reached.') })
    return () => { ignore = true }
  }, [open, report, answerId])

  return (
    <details className="more" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>Trust report: what was checked</summary>
      {error && <p role="alert" className="form-error">Could not load the report: {error}</p>}
      {!report && !error && open && <p role="status" className="muted">Loading…</p>}
      {report && (
        <>
          {report.warnings.map((w, i) => (
            <p key={i} className="trust-warning" role="note">{w}</p>
          ))}
          <ul className="trust-list">
            {report.dimensions.map((d) => <Dimension key={d.key} d={d} />)}
          </ul>
          <p className="muted trust-def">
            Each dimension is reported on its own. There is deliberately no overall score: a single number would hide
            exactly the cases (an unresolved conflict, an unknown date) that matter.
          </p>
        </>
      )}
    </details>
  )
}
