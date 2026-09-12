import { Link } from 'react-router'
import { effectiveCategory, effectiveUrgency, timeAgo } from '../../lib/format'
import type { TicketResponse } from '../../types'
import { CategoryTag, ChannelTag, EscalationTag, StatusTag, UrgencyTag } from './tags'

/**
 * One ticket in a list, shaped like a shipping label: its stickers on top, the subject in
 * the label face, the customer's words underneath. Escalated tickets carry a red edge.
 */
export function TicketStrip({ ticket, showStatus = false }: { ticket: TicketResponse; showStatus?: boolean }) {
  const escalated = ticket.needs_escalation === true
  return (
    <Link
      to={`/tickets/${ticket.id}`}
      className={`group block rounded-label border border-line border-l-4 bg-paper px-5 py-4 transition-colors hover:border-ink/50 ${
        escalated ? 'border-l-danger hover:border-l-danger' : 'border-l-paper hover:border-l-ink'
      }`}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        {showStatus && <StatusTag status={ticket.status} />}
        {escalated && <EscalationTag reason={ticket.escalation_reason} />}
        <CategoryTag category={effectiveCategory(ticket)} corrected={ticket.corrected_category !== null} />
        <UrgencyTag urgency={effectiveUrgency(ticket)} corrected={ticket.corrected_urgency !== null} />
        <ChannelTag channel={ticket.channel} />
        <time
          dateTime={ticket.created_at}
          title={new Date(ticket.created_at).toLocaleString()}
          className="ml-auto text-tiny text-ink-3"
        >
          {timeAgo(ticket.created_at)}
        </time>
      </div>
      <p className="type-label mt-3 truncate text-heading group-hover:underline group-hover:decoration-2 group-hover:underline-offset-4">
        {ticket.subject}
      </p>
      <p className="mt-1 line-clamp-1 max-w-[72ch] text-small text-ink-2">{ticket.body}</p>
      {escalated && ticket.escalation_reason && (
        <p className="mt-2 text-tiny font-semibold text-danger-ink">{ticket.escalation_reason}</p>
      )}
    </Link>
  )
}
