import { Navigate, Outlet, useLocation } from 'react-router'
import { ErrorNotice, Loading } from '../../ui'
import { useSession } from './hooks'

/** Renders the app for a signed-in user; anyone else goes to the sign-in page. */
export function RequireSession() {
  const session = useSession()
  const location = useLocation()
  if (session.isPending) return <Loading label="Checking your session…" />
  if (session.isError) return <ErrorNotice error={session.error} onRetry={() => void session.refetch()} />
  if (!session.data) {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  return <Outlet />
}
