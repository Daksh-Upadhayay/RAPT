import { CATEGORY_COLORS, CATEGORY_LABELS } from '../lib/format'
import type { TicketCategory } from '../types'

export function CategoryBadge({ category }: { category: TicketCategory | null }) {
  if (!category) {
    return <span className="badge text-slate-400">Unclassified</span>
  }
  return (
    <span className="badge">
      <span className="size-2 rounded-full" style={{ background: CATEGORY_COLORS[category] }} aria-hidden="true" />
      {CATEGORY_LABELS[category]}
    </span>
  )
}
