import { useNavigate } from 'react-router'
import { Button } from '../../ui'
import { useLogout, useSession } from './hooks'

/** Who is signed in, for which business, and the way out. */
export function UserMenu() {
  const { data: me } = useSession()
  const signOut = useLogout()
  const navigate = useNavigate()
  if (!me) return null
  return (
    <div className="flex items-center gap-3">
      <div className="hidden text-right leading-tight md:block">
        <p className="text-small font-semibold">{me.name}</p>
        <p className="text-tiny text-ink-3">{me.tenant_name}</p>
      </div>
      <Button variant="ghost" size="sm" loading={signOut.isPending} onClick={() => signOut.mutate(undefined, { onSettled: () => navigate('/login') })}>
        Sign out
      </Button>
    </div>
  )
}
