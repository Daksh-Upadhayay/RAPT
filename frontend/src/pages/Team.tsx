import { RequireAdmin } from '../features/auth'
import { TeamManager } from '../features/team'
import { PageHeader } from '../ui'

export function Team() {
  return (
    <>
      <PageHeader title="Team" intro="Who can sign in to review tickets. New members get a one-time password to pass on." />
      <RequireAdmin>
        <TeamManager />
      </RequireAdmin>
    </>
  )
}
