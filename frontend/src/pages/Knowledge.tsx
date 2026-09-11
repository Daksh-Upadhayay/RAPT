import { useSession } from '../features/auth'
import { AddDocuments, DocumentList, SearchPreview } from '../features/knowledge'
import { PageHeader } from '../ui'

export function Knowledge() {
  const { data: me } = useSession()
  const isAdmin = me?.role === 'admin'
  return (
    <>
      <PageHeader
        title="Knowledge base"
        intro="Your help documents, split into sections. Drafts may only quote what is here, so keep it complete and current."
      />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-6">
          {isAdmin && <AddDocuments />}
          <DocumentList editable={isAdmin} />
        </div>
        <aside>
          <SearchPreview />
        </aside>
      </div>
    </>
  )
}
