import { RequireAdmin } from '../features/auth'
import { ContactSettings } from '../features/contact'
import { PageHeader } from '../ui'

export function Settings() {
  return (
    <>
      <PageHeader title="Settings" intro="How your customers reach you." />
      <RequireAdmin>
        <div className="max-w-3xl">
          <ContactSettings />
        </div>
      </RequireAdmin>
    </>
  )
}
