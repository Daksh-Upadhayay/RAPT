import { useReviewer } from './context'

/** "Reviewing as": the placeholder identity sent with approvals and corrections. */
export function ReviewerField() {
  const { reviewerId, setReviewerId } = useReviewer()
  return (
    <label className="flex items-center gap-2 text-tiny text-ink-2">
      <span className="hidden md:inline">Reviewing as</span>
      <input
        value={reviewerId}
        onChange={(e) => setReviewerId(e.target.value)}
        onBlur={(e) => !e.target.value.trim() && setReviewerId('reviewer')}
        aria-label="Reviewer name"
        className="h-8 w-28 rounded-label border border-ink/35 bg-paper px-2 text-small text-ink focus:border-ink focus:outline-none"
      />
    </label>
  )
}
