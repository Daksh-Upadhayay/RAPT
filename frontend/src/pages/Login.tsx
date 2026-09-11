import { Navigate, useNavigate, useSearchParams } from 'react-router'
import { LoginForm, useSession } from '../features/auth'
import { Loading, Sheet } from '../ui'

/** Only same-app paths, so a crafted link can't bounce a user to another site after sign-in. */
function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/reviews'
}

export function Login() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const session = useSession()
  const next = safeNext(params.get('next'))

  if (session.isPending) return <Loading label="Checking your session…" />
  if (session.data) return <Navigate to={next} replace />

  return (
    <main className="flex min-h-screen items-start justify-center px-4 pt-[14vh]">
      <div className="w-full max-w-sm">
        <p className="type-label mb-6 border-b-2 border-ink pb-3 text-display">RAPT</p>
        <Sheet title="Sign in to review tickets">
          <LoginForm onSignedIn={() => navigate(next, { replace: true })} />
        </Sheet>
        <p className="mt-4 text-small text-ink-2">Accounts are created by your RAPT contact. Ask them if you need access or a new password.</p>
      </div>
    </main>
  )
}
