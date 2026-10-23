import { useState } from 'react'
import { TopBar } from './components/TopBar'
import type { PageId } from './components/TopBar'
import { ChatPage } from './features/chat/ChatPage'
import { BenchmarkPage } from './features/benchmark/BenchmarkPage'
import { DocumentsPage } from './features/documents/DocumentsPage'
import { useBackendStatus } from './features/health/useBackendStatus'

export default function App() {
  const [page, setPage] = useState<PageId>('chat')
  const backend = useBackendStatus()

  return (
    <>
      <TopBar page={page} onNavigate={setPage} backend={backend} />
      <main className="content">
        {page === 'chat' ? <ChatPage /> : page === 'documents' ? <DocumentsPage /> : <BenchmarkPage />}
      </main>
    </>
  )
}
