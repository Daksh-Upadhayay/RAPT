import type { LoginRequest, MeResponse } from '../types'
import { ApiError, request } from './client'

export const authKeys = {
  me: ['auth', 'me'] as const,
}

export const login = (data: LoginRequest) => request<MeResponse>('/auth/login', { method: 'POST', body: data })

export const logout = () => request<null>('/auth/logout', { method: 'POST' })

/** The signed-in user, or null when there is no valid session. */
export async function getMe(): Promise<MeResponse | null> {
  try {
    return await request<MeResponse>('/auth/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}
