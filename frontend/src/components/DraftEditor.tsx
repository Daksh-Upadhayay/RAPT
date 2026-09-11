import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { metricsKeys } from '../api/metrics'
import { approveDraft, editAndApproveDraft, reviewKeys } from '../api/reviews'
import { ticketKeys } from '../api/tickets'
import { useReviewer } from '../lib/reviewerContext'
import type { DraftResponseRead, TicketDetailResponse } from '../types'
import { CheckIcon, Spinner } from './icons'
import { ErrorMessage } from './ui'

/**
 * The AI draft, editable inline. "Approve" sends it as written; once the text changes,
 * "Edit & approve" sends the reviewer's version instead (both resolve the ticket).
 */
export function DraftEditor({ ticketId, draft }: { ticketId: string; draft: DraftResponseRead }) {
  const queryClient = useQueryClient()
  const { reviewerId } = useReviewer()
  const [text, setText] = useState(draft.draft_text)
  const edited = text.trim() !== draft.draft_text.trim()
  const empty = !text.trim()
  const reviewer = reviewerId.trim() || 'reviewer'

  const mutation = useMutation({
    mutationFn: () =>
      edited
        ? editAndApproveDraft(ticketId, { edited_text: text.trim(), reviewer_id: reviewer })
        : approveDraft(ticketId, { reviewer_id: reviewer }),
    onSuccess: (ticket: TicketDetailResponse) => {
      queryClient.setQueryData(ticketKeys.detail(ticketId), ticket)
      void queryClient.invalidateQueries({ queryKey: reviewKeys.queue })
      void queryClient.invalidateQueries({ queryKey: ticketKeys.all })
      void queryClient.invalidateQueries({ queryKey: metricsKeys.all })
    },
  })

  return (
    <div>
      <label htmlFor="draft" className="sr-only">
        Draft reply
      </label>
      <textarea
        id="draft"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={mutation.isPending}
        rows={Math.min(18, Math.max(8, text.split('\n').length + 2))}
        className={`input resize-y leading-relaxed ${edited ? 'border-amber-400 bg-amber-50/30' : ''}`}
      />
      <div className="mt-2 flex min-h-5 items-center justify-between text-xs text-slate-500">
        <span>{edited ? 'Edited: your version will be sent instead of the AI draft.' : 'Unchanged AI draft.'}</span>
        {edited && (
          <button type="button" className="font-medium text-slate-700 underline underline-offset-2" onClick={() => setText(draft.draft_text)}>
            Revert to AI draft
          </button>
        )}
      </div>

      {mutation.isError && (
        <div className="mt-3">
          <ErrorMessage error={mutation.error} />
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="btn-primary"
          disabled={mutation.isPending || edited}
          onClick={() => mutation.mutate()}
          title={edited ? 'You changed the text: use Edit & approve, or revert' : undefined}
        >
          {mutation.isPending && !edited ? <Spinner /> : <CheckIcon />}
          Approve
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={mutation.isPending || !edited || empty}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending && edited && <Spinner />}
          Edit &amp; approve
        </button>
        <span className="text-xs text-slate-500">as {reviewer}</span>
      </div>
    </div>
  )
}
