import { useEffect, useState } from 'react'
import { ApiError, getEvidenceGraph } from '../../api/client'
import type { EvidenceGraph, GraphEdge, GraphNode } from '../../types'

const ROW = 84
const RELATION_TEXT: Record<GraphEdge['relation'], string> = {
  supports: 'supports',
  contradicts: 'is contradicted by',
  context: 'is given context by',
  supersedes: 'supersedes',
  conflicts: 'disagrees with',
}

function describe(edge: GraphEdge, byId: Map<string, GraphNode>): string {
  const a = byId.get(edge.source)?.label ?? edge.source
  const b = byId.get(edge.target)?.label ?? edge.target
  const tail =
    edge.relation === 'supersedes'
      ? edge.in_force ? ' (in force)' : ' (not in force on this date)'
      : edge.relation === 'conflicts'
        ? edge.settled ? ' (settled by the rules)' : ' (unresolved)'
        : ''
  const subject = byId.get(edge.source)?.kind === 'claim' ? `Claim “${a}”` : a
  return `${subject} ${RELATION_TEXT[edge.relation]} ${b}${tail}`
}

function Graph({ graph, onOpenPassage }: { graph: EvidenceGraph; onOpenPassage: (chunkId: string) => void }) {
  const claims = graph.nodes.filter((n) => n.kind === 'claim')
  // Winners first, then the documents they replaced, so a supersession reads top to bottom.
  const order = (n: GraphNode) => (n.role === 'winner' ? 0 : n.role === 'superseded' ? 2 : 1)
  const docs = graph.nodes.filter((n) => n.kind === 'document').sort((a, b) => order(a) - order(b))
  const rows = Math.max(claims.length, docs.length, 1)
  const height = rows * ROW
  const y = new Map<string, number>()
  claims.forEach((n, i) => y.set(n.id, i * ROW + ROW / 2))
  docs.forEach((n, i) => y.set(n.id, i * ROW + ROW / 2))
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))

  return (
    <div className="graph" style={{ height }}>
      <svg className="graph-lines" viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" aria-hidden="true">
        {graph.edges.map((e, i) => {
          if (e.relation === 'supersedes' || e.relation === 'conflicts') {
            const x = e.relation === 'supersedes' ? 94 : 98
            const a = y.get(e.source)
            const b = y.get(e.target)
            if (a === undefined || b === undefined) return null
            return (
              <path
                key={i}
                d={`M 92 ${a} L ${x} ${a} L ${x} ${b} L 92 ${b}`}
                className={`gl gl-${e.relation}${e.relation === 'supersedes' && !e.in_force ? ' gl-off' : ''}${e.relation === 'conflicts' && !e.settled ? ' gl-open' : ''}`}
                fill="none"
              />
            )
          }
          const a = y.get(e.source)
          const b = y.get(e.target)
          if (a === undefined || b === undefined) return null
          return <line key={i} x1={40} y1={a} x2={60} y2={b} className={`gl gl-${e.relation}`} />
        })}
      </svg>
      {claims.map((n, i) => (
        <div key={n.id} className={`gnode gclaim grole-${n.role}`} style={{ top: i * ROW + 6, height: ROW - 12 }}>
          <span className="gtag">{n.role === 'superseded' ? 'outdated claim' : n.role === 'unsupported' ? 'unsupported' : 'claim'}</span>
          <span className="gtext">{n.label}</span>
        </div>
      ))}
      {docs.map((n, i) => (
        <button
          key={n.id}
          type="button"
          className={`gnode gdoc grole-${n.role || 'none'}`}
          style={{ top: i * ROW + 6, height: ROW - 12 }}
          disabled={n.chunk_ids.length === 0}
          onClick={() => onOpenPassage(n.chunk_ids[0])}
          aria-label={`Open the passage from ${n.label}`}
        >
          <span className="gtag">
            {n.role === 'winner' ? 'takes precedence' : n.role === 'superseded' ? 'superseded' : 'source'}
            {n.version ? ` · v${n.version}` : ''}
          </span>
          <span className="gtext">{n.label}</span>
          <span className="gmeta">{n.authority_level} · effective {n.effective_date ?? 'unknown'}</span>
        </button>
      ))}
      <ul className="sr-only">
        {graph.edges.map((e, i) => <li key={i}>{describe(e, byId)}</li>)}
      </ul>
    </div>
  )
}

export function EvidenceGraphPanel({ answerId, onOpenPassage }: { answerId: string; onOpenPassage: (chunkId: string) => void }) {
  const [open, setOpen] = useState(false)
  const [graph, setGraph] = useState<EvidenceGraph | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || graph) return
    let ignore = false
    getEvidenceGraph(answerId)
      .then((g) => { if (!ignore) setGraph(g) })
      .catch((err) => { if (!ignore) setError(err instanceof ApiError ? err.message : 'The backend could not be reached.') })
    return () => { ignore = true }
  }, [open, graph, answerId])

  return (
    <details className="more" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>Evidence graph: claims, sources and how they relate</summary>
      {error && <p role="alert" className="form-error">Could not load the graph: {error}</p>}
      {!graph && !error && open && <p role="status" className="muted">Loading…</p>}
      {graph && graph.nodes.length === 0 && <p className="muted">There are no claims, so there is nothing to draw.</p>}
      {graph && graph.nodes.length > 0 && (
        <>
          <Graph graph={graph} onOpenPassage={onOpenPassage} />
          <ul className="graph-legend muted">
            <li><span className="lg lg-supports" /> supports</li>
            <li><span className="lg lg-contradicts" /> contradicts</li>
            <li><span className="lg lg-context" /> context only</li>
            <li><span className="lg lg-supersedes" /> supersedes (right edge, solid when in force)</li>
            <li><span className="lg lg-conflicts" /> sources disagree (far right; red dashed when unresolved)</li>
          </ul>
          <p className="muted">Select a source to read its passage.</p>
        </>
      )}
    </details>
  )
}
