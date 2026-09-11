import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authKeys, getMe, login, logout } from '../../api/auth'
import type { LoginRequest } from '../../types'

/** The signed-in user (null when signed out). Checked once, then kept fresh by 401s. */
export function useSession() {
  return useQuery({ queryKey: authKeys.me, queryFn: getMe, staleTime: Infinity, retry: false })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: LoginRequest) => login(data),
    onSuccess: (me) => {
      // A different user may sign in on this browser: drop everything cached for the last one
      queryClient.clear()
      queryClient.setQueryData(authKeys.me, me)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear()
      queryClient.setQueryData(authKeys.me, null)
    },
  })
}
