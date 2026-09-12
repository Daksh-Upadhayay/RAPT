import type { ReactNode } from 'react'
import { dateTime, effectiveCategory, effectiveUrgency, timeAgo } from '../../lib/format'
import type { TicketResponse } from '../../types'
import { BackLink } from '../../ui'
import { CategoryTag, ChannelTag, EscalationTag, StatusTag, UrgencyTag } from './tags'

/**
 * The ticket's header, printed like a label's routing line: the subject in heavy
 * expanded type on a thick black rule, its stickers underneath.
 */
export function TicketLabel({ ticket, back, actions }: {
  ticket: TicketResponse
  back: { to: string; label: string }
  actions?: ReactNode
}) {
  return (
    <header className="mb-8">
      <BackLink to={back.to}>{back.label}</BackLink>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-small text-ink-2">
        <StatusTag status={ticket.status} />
        <span title={dateTime(ticket.created_at)}>Submitted {timeAgo(ticket.created_at)}</span>
        <span className="font-mono text-tiny text-ink-3" title="Ticket ID">
          {ticket.id.slice(0, 8)}
        </span>
      </div>
      <h1 className="type-label mt-3 border-b-2 border-ink pb-3 text-display text-balance">{ticket.subject}</h1>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {ticket.needs_escalation && <EscalationTag reason={ticket.escalation_reason} />}
        <CategoryTag category={effectiveCategory(ticket)} corrected={ticket.corrected_category !== null} />
        <UrgencyTag urgency={effectiveUrgency(ticket)} corrected={ticket.corrected_urgency !== null} />
        <ChannelTag channel={ticket.channel} />
        {actions && <div className="flex w-full flex-wrap items-center gap-2 pt-1 sm:ml-auto sm:w-auto sm:pt-0">{actions}</div>}
      </div>
    </header>
  )
}
