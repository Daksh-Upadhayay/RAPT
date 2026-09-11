import { EmptyState } from '../../ui'
import { useSession } from './hooks'
import type { ReactNode } from 'react'

/** Admin-only screens; reviewers get an explanation instead (the API refuses them too). */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { data: me } = useSession()
  if (me?.role !== 'admin') {
    return <EmptyState title="Only admins can open this page">Ask an admin of {me?.tenant_name ?? 'your team'} for access.</EmptyState>
  }
  return children
}
