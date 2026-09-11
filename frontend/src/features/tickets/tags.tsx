import { CATEGORY_COLORS, CATEGORY_LABELS, STATUS_LABELS, URGENCY_LABELS } from '../../lib/format'
import type { TicketCategory, TicketStatus, TicketUrgency } from '../../types'
import { CheckIcon, CorrectedMark, FlagIcon, Spinner, Tag } from '../../ui'

/** Category name with its fixed colour as a small key (colour never carries it alone). */
export function CategoryTag({ category, corrected = false }: { category: TicketCategory | null; corrected?: boolean }) {
  if (!category) return <Tag tone="muted">Not classified yet</Tag>
  return (
    <Tag
      title={corrected ? 'Corrected by a reviewer' : undefined}
      icon={<span className="size-2.5 rounded-[1px]" style={{ background: CATEGORY_COLORS[category] }} aria-hidden="true" />}
    >
      {CATEGORY_LABELS[category]}
      {corrected && <CorrectedMark />}
    </Tag>
  )
}

const URGENCY_BARS: Record<TicketUrgency, { bars: number; color: string }> = {
  low: { bars: 1, color: 'var(--color-ink-3)' },
  medium: { bars: 2, color: 'var(--color-ink)' },
  high: { bars: 3, color: 'var(--color-danger)' },
}

/** Urgency as a signal-strength icon plus its name. */
export function UrgencyTag({ urgency, corrected = false }: { urgency: TicketUrgency | null; corrected?: boolean }) {
  if (!urgency) return null
  const { bars, color } = URGENCY_BARS[urgency]
  return (
    <Tag
      title={corrected ? 'Corrected by a reviewer' : undefined}
      icon={
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <rect key={i} x={i * 4.5} y={8 - i * 3} width="3" height={4 + i * 3} rx="0.5" fill={i < bars ? color : 'var(--color-line)'} />
          ))}
        </svg>
      }
    >
      {URGENCY_LABELS[urgency]} urgency
      {corrected && <CorrectedMark />}
    </Tag>
  )
}

export function StatusTag({ status }: { status: TicketStatus }) {
  if (status === 'new' || status === 'in_progress') {
    return (
      <Tag tone="muted" icon={<Spinner className="size-3" />}>
        {STATUS_LABELS[status]}
      </Tag>
    )
  }
  if (status === 'resolved') {
    return (
      <Tag tone="ok" icon={<CheckIcon className="size-3" />}>
        {STATUS_LABELS.resolved}
      </Tag>
    )
  }
  return <Tag tone="accent">{STATUS_LABELS.awaiting_review}</Tag>
}

export function EscalationTag({ reason }: { reason?: string | null }) {
  return (
    <Tag tone="danger" title={reason ?? undefined} icon={<FlagIcon className="size-3" />}>
      Escalated
    </Tag>
  )
}
