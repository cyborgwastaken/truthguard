import { useEffect, useState } from 'react'
import { getHealth } from '../../api/client'
import type { BackendStatus } from '../../types'

const POLL_MS = 10_000

/** Checks GET /health now and every 10 seconds. */
export function useBackendStatus(): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>('checking')

  useEffect(() => {
    const controller = new AbortController()

    async function check() {
      try {
        const health = await getHealth(controller.signal)
        setStatus(health.status === 'ok' ? 'connected' : 'offline')
      } catch {
        if (!controller.signal.aborted) setStatus('offline')
      }
    }

    void check()
    const timer = setInterval(() => void check(), POLL_MS)
    return () => {
      controller.abort()
      clearInterval(timer)
    }
  }, [])

  return status
}
