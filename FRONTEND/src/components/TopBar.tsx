import type { BackendStatus } from '../types'

export type PageId = 'chat' | 'documents' | 'benchmark'

const PAGES: { id: PageId; label: string }[] = [
  { id: 'chat', label: 'Chat' },
  { id: 'documents', label: 'Documents' },
  { id: 'benchmark', label: 'Benchmark' },
]

const STATUS_TEXT: Record<BackendStatus, string> = {
  checking: 'Backend: checking…',
  connected: 'Backend: connected',
  offline: 'Backend: offline',
}

interface TopBarProps {
  page: PageId
  onNavigate: (page: PageId) => void
  backend: BackendStatus
}

export function TopBar({ page, onNavigate, backend }: TopBarProps) {
  return (
    <header className="topbar">
      <span className="brand">TruthGuard</span>
      <nav className="nav" aria-label="Main">
        {PAGES.map((p) => (
          <button
            key={p.id}
            type="button"
            className={p.id === page ? 'nav-item active' : 'nav-item'}
            aria-current={p.id === page ? 'page' : undefined}
            onClick={() => onNavigate(p.id)}
          >
            {p.label}
          </button>
        ))}
      </nav>
      <span className={`status status-${backend}`} role="status">
        <span className="status-dot" aria-hidden="true" />
        {STATUS_TEXT[backend]}
      </span>
    </header>
  )
}
