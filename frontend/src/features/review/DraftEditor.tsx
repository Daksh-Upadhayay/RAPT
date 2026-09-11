import { useState } from 'react'
import type { DraftResponseRead } from '../../types'
import { Button, CheckIcon, ErrorNotice } from '../../ui'
import { useReviewer } from '../reviewer'
import { useApproveDraft } from './hooks'

/**
 * The draft reply, editable in place. "Approve" keeps the AI's text; once the text
 * changes, only "Approve my edits" is offered, so an edit can't be lost by accident.
 */
export function DraftEditor({ ticketId, draft }: { ticketId: string; draft: DraftResponseRead }) {
  const { reviewerId } = useReviewer()
  const [text, setText] = useState(draft.draft_text)
  const approve = useApproveDraft(ticketId)
  const edited = text.trim() !== draft.draft_text.trim()

  return (
    <div>
      <label htmlFor="draft" className="sr-only">
        Draft reply
      </label>
      <textarea
        id="draft"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={approve.isPending}
        rows={Math.min(20, Math.max(9, text.split('\n').length + 2))}
        className={`block w-full resize-y rounded-label border px-5 py-4 text-body leading-7 text-ink focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ink ${
          edited ? 'border-accent-deep bg-accent-wash/40' : 'border-line bg-paper'
        }`}
      />
      <div className="mt-2 flex min-h-5 flex-wrap items-center justify-between gap-2 text-tiny text-ink-3">
        <span>{edited ? 'You changed the AI draft. Your version is what gets approved.' : 'This is the AI draft, unchanged.'}</span>
        {edited && (
          <button type="button" className="font-semibold text-ink underline underline-offset-2" onClick={() => setText(draft.draft_text)}>
            Undo my edits
          </button>
        )}
      </div>

      {approve.isError && (
        <div className="mt-3">
          <ErrorNotice error={approve.error} />
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        {edited ? (
          <Button variant="primary" icon={<CheckIcon />} loading={approve.isPending} disabled={!text.trim()} onClick={() => approve.mutate(text.trim())}>
            Approve my edits
          </Button>
        ) : (
          <Button variant="primary" icon={<CheckIcon />} loading={approve.isPending} onClick={() => approve.mutate(null)}>
            Approve draft
          </Button>
        )}
        <span className="text-tiny text-ink-3">Approving as {reviewerId.trim() || 'reviewer'}. This resolves the ticket.</span>
      </div>
    </div>
  )
}
