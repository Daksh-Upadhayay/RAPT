import { useMutation, useQuery } from '@tanstack/react-query'
import { approveDraft, correctTriage, editAndApproveDraft, getReviewQueue, reviewKeys } from '../../api/reviews'
import type { TicketCategory, TicketUrgency } from '../../types'
import { useApplyTicketUpdate } from '../tickets'

/** Tickets awaiting review, in the order a reviewer should work them. */
export function useReviewQueue(pollMs: number | false = 5000) {
  return useQuery({ queryKey: reviewKeys.queue, queryFn: getReviewQueue, refetchInterval: pollMs })
}

/** Approve the draft as written, or with the reviewer's edited text (as the signed-in user). */
export function useApproveDraft(ticketId: string) {
  const apply = useApplyTicketUpdate()
  return useMutation({
    mutationFn: (editedText: string | null) =>
      editedText === null ? approveDraft(ticketId) : editAndApproveDraft(ticketId, { edited_text: editedText }),
    onSuccess: apply,
  })
}

/** Record the reviewer's category/urgency (Phase 6 feedback loop). */
export function useCorrectTriage(ticketId: string) {
  const apply = useApplyTicketUpdate()
  return useMutation({
    mutationFn: ({ category, urgency }: { category: TicketCategory; urgency: TicketUrgency }) =>
      correctTriage(ticketId, { corrected_category: category, corrected_urgency: urgency }),
    onSuccess: apply,
  })
}
