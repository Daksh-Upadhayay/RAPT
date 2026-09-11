import type { ErrorResponse } from '../types'

/** All requests go to /api, which the Vite server proxies to FastAPI (vite.config.ts). */
const BASE_URL = '/api'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function errorMessage(status: number, body: unknown): string {
  const detail = (body as Partial<ErrorResponse> | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    // FastAPI validation errors: "body.subject: String should have at least 1 character"
    return detail.map((e) => `${e.loc.slice(1).join('.') || e.loc.join('.')}: ${e.msg}`).join('; ')
  }
  if (status === 502 || status === 504) return 'Cannot reach the backend. Is it running on port 8000?'
  return `Request failed (${status})`
}

type Query = Record<string, string | number | undefined>

export async function request<T>(
  path: string,
  options: { method?: 'GET' | 'POST' | 'PUT'; body?: unknown; query?: Query } = {},
): Promise<T> {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const qs = params.size ? `?${params}` : ''

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}${qs}`, {
      method: options.method ?? 'GET',
      // The session is an httpOnly cookie (sent automatically, same origin). Requests that
      // change something also carry the CSRF header the API requires.
      headers: {
        ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...((options.method ?? 'GET') === 'GET' ? {} : { 'X-RAPT-CSRF': '1' }),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check your connection and that the dev server is running.')
  }

  const text = await response.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, data))
  return data as T
}
