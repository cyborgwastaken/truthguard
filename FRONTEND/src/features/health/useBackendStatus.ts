import { useState, useEffect } from 'react'
import type { BackendStatus } from '../../types'
import { getHealth } from '../../api/client'

export function useBackendStatus(): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>('checking')

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()

    async function check() {
      try {
        await getHealth(controller.signal)
        if (!cancelled) setStatus('connected')
      } catch {
        if (!cancelled) setStatus('offline')
      }
    }

    check()
    const id = setInterval(check, 15_000)
    return () => {
      cancelled = true
      controller.abort()
      clearInterval(id)
    }
  }, [])

  return status
}
