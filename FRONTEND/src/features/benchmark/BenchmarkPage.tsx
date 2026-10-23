import { Fragment, useEffect, useState } from 'react'
import { ApiError, getLatestBenchmark } from '../../api/client'
import type {
  AnswerStatus,
  BenchmarkCase,
  BenchmarkRun,
  CaseResult,
  ConfigName,
  Metric,
} from '../../types'

const CONFIGS: ConfigName[] = ['baseline', 'rag_critic', 'full']

// The order the metrics are shown in: what the system is for first, then supporting numbers.
const METRIC_ORDER = [
  'status_accuracy',
  'key_fact_accuracy',
  'outdated_value_rate',
  'false_conflict_rate',
  'conflict_recall',
  'abstention_recall',
  'abstention_precision',
  'winner_accuracy',
  'stale_detection',
  'retrieval_recall',
  'citation_precision',
  'claim_support_rate',
  'verification_failed_rate',
  'latency_mean_ms',
  'latency_p95_ms',
]

const SHORT_STATUS: Record<AnswerStatus, string> = {
  resolved: 'resolved',
  conflict_unresolved: 'conflict',
  insufficient_evidence: 'no evidence',
  verification_failed: 'failed',
}

function includes(text: string, needle: string): boolean {
  return text.toLowerCase().includes(needle.toLowerCase())
}

/** The same checks the Python metrics use: right status, every expected fact, no outdated value. */
function passes(c: BenchmarkCase, r: CaseResult): boolean {
  if (r.status !== c.expected_status) return false
  if (!c.expected_answer_contains.every((group) => group.some((s) => includes(r.answer, s)))) return false
  if (c.forbidden_answer_contains.some((s) => includes(r.answer, s))) return false
  return true
}

function formatValue(m: Metric): string {
  if (!m.applies) return 'n/a'
  if (m.value === null) return '–'
  if (m.unit === 'ms') return `${(m.value / 1000).toFixed(1)} s`
  return `${Math.round(m.value * 100)}%`
}

function bestConfigs(metrics: Record<ConfigName, Record<string, Metric>>, key: string): Set<ConfigName> {
  const candidates = CONFIGS.map((c) => ({ c, m: metrics[c]?.[key] })).filter(
    (x) => x.m && x.m.applies && x.m.value !== null,
  )
  if (candidates.length === 0 || candidates[0].m.higher_is_better === null) return new Set()
  const higher = candidates[0].m.higher_is_better
  const values = candidates.map((x) => x.m.value as number)
  const target = higher ? Math.max(...values) : Math.min(...values)
  // Nothing to highlight if every setup is equal.
  if (values.every((v) => v === target)) return new Set()
  return new Set(candidates.filter((x) => x.m.value === target).map((x) => x.c))
}

function MetricsTable({ run }: { run: BenchmarkRun }) {
  const keys = METRIC_ORDER.filter((k) => CONFIGS.some((c) => run.metrics[c]?.[k]))
  return (
    <div className="table-wrap">
      <table className="doc-table bench-table" aria-label="Benchmark metrics">
        <thead>
          <tr>
            <th scope="col">Metric</th>
            {CONFIGS.map((c) => (
              <th key={c} scope="col">{run.config_labels[c]}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => {
            const first = CONFIGS.map((c) => run.metrics[c]?.[key]).find(Boolean) as Metric
            const best = bestConfigs(run.metrics, key)
            return (
              <tr key={key}>
                <th scope="row" className="metric-name">
                  {first.label}
                  <span className="metric-def muted">
                    {first.definition}
                    {first.higher_is_better === false ? ' (lower is better)' : ''}
                  </span>
                </th>
                {CONFIGS.map((c) => {
                  const m = run.metrics[c]?.[key]
                  if (!m) return <td key={c}>–</td>
                  const isBest = best.has(c)
                  return (
                    <td key={c} className={isBest ? 'cell-best' : ''} title={m.note || undefined}>
                      <strong>{formatValue(m)}</strong>
                      {isBest && <span className="sr-only"> (best)</span>}
                      {m.applies && m.unit === 'ratio' && m.denominator !== null && (
                        <span className="muted frac"> {m.numerator}/{m.denominator}</span>
                      )}
                      {!m.applies && <span className="muted frac">{m.note}</span>}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function CaseGrid({ run }: { run: BenchmarkRun }) {
  const [open, setOpen] = useState<string | null>(null)
  const repeats = Number(run.settings.repeats ?? 1)
  return (
    <div className="table-wrap">
      <table className="doc-table bench-table" aria-label="Results per case">
        <thead>
          <tr>
            <th scope="col">Case</th>
            <th scope="col">Expected</th>
            {CONFIGS.map((c) => (
              <th key={c} scope="col">{run.config_labels[c]}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {run.cases.map((c) => {
            const isOpen = open === c.case_id
            return (
              <Fragment key={c.case_id}>
                <tr>
                  <th scope="row" className="metric-name">
                    <button
                      type="button"
                      className="link-btn"
                      aria-expanded={isOpen}
                      onClick={() => setOpen(isOpen ? null : c.case_id)}
                    >
                      {c.case_id}
                    </button>
                    <span className="metric-def muted">{c.question}</span>
                  </th>
                  <td>
                    <span className={`answer-badge answer-badge-${c.expected_status}`}>{SHORT_STATUS[c.expected_status]}</span>
                    <span className="metric-def muted">{c.case_type.replace(/_/g, ' ')}</span>
                  </td>
                  {CONFIGS.map((cfg) => {
                    const rs = run.results.filter((r) => r.case_id === c.case_id && r.config === cfg)
                    if (rs.length === 0) return <td key={cfg}>–</td>
                    const ok = rs.filter((r) => passes(c, r)).length
                    const allOk = ok === rs.length
                    return (
                      <td key={cfg} className={allOk ? 'cell-pass' : ok === 0 ? 'cell-fail' : 'cell-mixed'}>
                        <span aria-label={allOk ? 'passes' : ok === 0 ? 'fails' : 'passes in some repeats'}>
                          {allOk ? '✓' : ok === 0 ? '✗' : '~'}
                        </span>{' '}
                        {rs.length === 1 ? SHORT_STATUS[rs[0].status] : `${ok}/${rs.length}`}
                      </td>
                    )
                  })}
                </tr>
                {isOpen && (
                  <tr className="case-detail">
                    <td colSpan={2 + CONFIGS.length}>
                      <p className="muted">{c.note}</p>
                      <div className="case-answers">
                        {CONFIGS.map((cfg) =>
                          run.results
                            .filter((r) => r.case_id === c.case_id && r.config === cfg)
                            .slice(0, repeats > 1 ? repeats : 1)
                            .map((r) => (
                              <article key={`${cfg}-${r.repeat}`} className="case-answer">
                                <strong>{run.config_labels[cfg]}{repeats > 1 ? ` (run ${r.repeat})` : ''}</strong>
                                <div className="muted">
                                  {SHORT_STATUS[r.status]} · {(r.latency_ms / 1000).toFixed(1)} s
                                  {r.winner_document_ids.length > 0 && ` · winner ${r.winner_document_ids.join(', ')}`}
                                </div>
                                <p>{r.answer || <span className="muted">(no answer text)</span>}</p>
                                {r.failure_reason && <p className="form-error">{r.failure_reason}</p>}
                              </article>
                            )),
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function BenchmarkPage() {
  const [run, setRun] = useState<BenchmarkRun | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading')
  const [error, setError] = useState('')

  useEffect(() => {
    let ignore = false
    getLatestBenchmark()
      .then((r) => {
        if (ignore) return
        setRun(r)
        setState('ready')
      })
      .catch((err) => {
        if (ignore) return
        if (err instanceof ApiError && err.status === 404) {
          setState('empty')
        } else {
          setError(err instanceof ApiError ? err.message : 'The backend could not be reached.')
          setState('error')
        }
      })
    return () => {
      ignore = true
    }
  }, [])

  return (
    <section>
      <h1>Benchmark</h1>
      <p className="muted page-subtitle">
        The same 18 labeled questions answered three ways: plain search-and-answer, with the critic added, and the
        full system. Every number shows the cases behind it.
      </p>
      {state === 'loading' && <p role="status" className="muted">Loading the latest run…</p>}
      {state === 'error' && <p role="alert" className="form-error">Could not load the benchmark: {error}</p>}
      {state === 'empty' && (
        <p role="status" className="doc-table-state muted">
          No benchmark has been run yet. Run it with <code>cd BACKEND &amp;&amp; python -m app.benchmark</code>.
        </p>
      )}
      {state === 'ready' && run && (
        <>
          <p className="muted bench-run">
            Run {run.run_id} · dataset {run.dataset_version} ({run.cases.length} cases) · model{' '}
            {String(run.settings.model ?? 'unknown')} · temperature {String(run.settings.temperature ?? 'default')} ·{' '}
            {String(run.settings.repeats ?? 1)} run(s) per case
          </p>
          <p className="bench-honesty">
            A small synthetic set, measured once on this model: it shows how the three setups differ, not how the
            system would score on other documents. Failed checks are counted on their own and never as correct answers.
          </p>
          <h2 className="section-heading">Metrics</h2>
          <MetricsTable run={run} />
          <h2 className="section-heading">Every case</h2>
          <p className="muted">✓ means the right status, every expected fact, and no outdated value. Select a case to read each answer.</p>
          <CaseGrid run={run} />
        </>
      )}
    </section>
  )
}
