import { URGENCY_LABELS } from '../lib/format'
import type { TicketUrgency } from '../types'

// Status colours (never category colours), always with the level icon and a label
const LEVEL: Record<TicketUrgency, { bars: number; color: string }> = {
  low: { bars: 1, color: '#898781' },
  medium: { bars: 2, color: '#e09a00' },
  high: { bars: 3, color: '#d03b3b' },
}

export function UrgencyBadge({ urgency }: { urgency: TicketUrgency | null }) {
  if (!urgency) return null
  const { bars, color } = LEVEL[urgency]
  return (
    <span className="badge" title={`${URGENCY_LABELS[urgency]} urgency`}>
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <rect
            key={i}
            x={i * 4.5}
            y={8 - i * 3}
            width="3"
            height={4 + i * 3}
            rx="1"
            fill={i < bars ? color : '#e1e0d9'}
          />
        ))}
      </svg>
      {URGENCY_LABELS[urgency]}
    </span>
  )
}
