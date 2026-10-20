/** TypeScript types that mirror the backend models. Add new ones here as endpoints are built. */

export interface HealthResponse {
  status: string
}

export type BackendStatus = 'checking' | 'connected' | 'offline'
