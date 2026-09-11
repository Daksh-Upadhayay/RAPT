import { Link } from 'react-router'
import { timeAgo } from '../lib/format'
import type { TicketResponse } from '../types'
import { CategoryBadge } from './CategoryBadge'
import { EscalationFlag, StatusBadge } from './StatusBadge'
import { ArrowRightIcon } from './icons'
import { UrgencyBadge } from './UrgencyBadge'

/** One row of the review queue: scannable at a glance (subject, badges, age). */
export function TicketCard({ ticket, showStatus = false }: { ticket: TicketResponse; showStatus?: boolean }) {
  return (
    <Link
      to={`/tickets/${ticket.id}`}
      className={`group flex items-center gap-4 rounded-xl border bg-white px-4 py-3.5 transition hover:border-indigo-300 hover:shadow-sm ${
        ticket.needs_escalation ? 'border-red-200 border-l-4 border-l-red-500' : 'border-slate-200'
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-medium text-slate-900">{ticket.subject}</p>
          {ticket.needs_escalation && <EscalationFlag reason={ticket.escalation_reason} compact />}
        </div>
        <p className="mt-0.5 truncate text-sm text-slate-500">{ticket.body}</p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {showStatus && <StatusBadge status={ticket.status} />}
          <CategoryBadge category={ticket.category} />
          <UrgencyBadge urgency={ticket.urgency} />
          {ticket.needs_escalation && ticket.escalation_reason && (
            <span className="truncate text-xs text-red-700">{ticket.escalation_reason}</span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-2 text-xs text-slate-400">
        <time dateTime={ticket.created_at} title={new Date(ticket.created_at).toLocaleString()}>
          {timeAgo(ticket.created_at)}
        </time>
        <ArrowRightIcon className="size-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-indigo-500" />
      </div>
    </Link>
  )
}
