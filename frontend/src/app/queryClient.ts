import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { authKeys } from '../api/auth'
import { ApiError } from '../api/client'

// A 401 from any request means the session has ended (expired, signed out elsewhere, or
// the password was reset): mark the user signed out, and RequireSession sends them to
// the sign-in page.
function onAuthError(error: unknown) {
  if (error instanceof ApiError && error.status === 401) queryClient.setQueryData(authKeys.me, null)
}

export const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onAuthError }),
  mutationCache: new MutationCache({ onError: onAuthError }),
  defaultOptions: {
    queries: {
      staleTime: 2000,
      // 4xx won't fix itself on retry (401, 404, 422); network and 5xx errors might
      retry: (failures, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failures < 2,
    },
  },
})
