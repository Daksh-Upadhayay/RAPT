import { STATUS_LABELS } from '../lib/format'
import type { TicketStatus } from '../types'
import { CheckIcon, FlagIcon, Spinner } from './icons'

const STYLES: Record<TicketStatus, string> = {
  new: 'bg-slate-100 text-slate-700',
  in_progress: 'bg-indigo-50 text-indigo-700',
  awaiting_review: 'bg-amber-50 text-amber-800',
  resolved: 'bg-emerald-50 text-emerald-800',
}

export function StatusBadge({ status }: { status: TicketStatus }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}>
      {(status === 'new' || status === 'in_progress') && <Spinner className="size-3" />}
      {status === 'resolved' && <CheckIcon className="size-3" />}
      {STATUS_LABELS[status]}
    </span>
  )
}

export function EscalationFlag({ reason, compact = false }: { reason?: string | null; compact?: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-800 ring-1 ring-red-200"
      title={reason ?? undefined}
    >
      <FlagIcon className="size-3" />
      Escalated
      {!compact && reason && <span className="font-normal text-red-700">· {reason}</span>}
    </span>
  )
}
