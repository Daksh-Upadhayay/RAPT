import { useParams } from 'react-router'
import { GroundingList, OrderSlip, ReviewPanel, TriageCard } from '../features/review'
import { TicketLabel, useRerunAgents, useTicket } from '../features/tickets'
import { currentRun, logFor, retrievedHits } from '../features/trace'
import { Button, ButtonLink, ErrorNotice, FlagIcon, Loading, PageHeader, RefreshIcon, Sheet } from '../ui'

export function TicketDetail() {
  const { id = '' } = useParams()
  const ticketQuery = useTicket(id)
  const rerun = useRerunAgents(id)

  if (ticketQuery.isPending) return <Loading label="Loading ticket…" />
  if (ticketQuery.isError) {
    return (
      <>
        <PageHeader title="Ticket" back={{ to: '/reviews', label: 'Review queue' }} />
        <ErrorNotice error={ticketQuery.error} onRetry={() => void ticketQuery.refetch()} />
      </>
    )
  }

  const ticket = ticketQuery.data
  const hits = retrievedHits(logFor(currentRun(ticket), 'knowledge'))

  return (
    <>
      <TicketLabel
        ticket={ticket}
        back={{ to: '/reviews', label: 'Review queue' }}
        actions={
          <>
            <ButtonLink to={`/tickets/${ticket.id}/trace`} size="sm">
              Agent trace
            </ButtonLink>
            {ticket.status === 'awaiting_review' && (
              <Button variant="ghost" size="sm" icon={<RefreshIcon />} loading={rerun.isPending} onClick={() => rerun.mutate()}>
                Run agents again
              </Button>
            )}
          </>
        }
      />

      {rerun.isError && (
        <div className="mb-6">
          <ErrorNotice error={rerun.error} />
        </div>
      )}

      {ticket.needs_escalation && (
        <div role="note" className="mb-6 flex gap-3 rounded-label border-l-4 border-danger bg-danger-wash px-4 py-3">
          <FlagIcon className="mt-0.5 size-4 shrink-0 text-danger" />
          <div>
            <p className="font-semibold text-danger-ink">
              {ticket.status === 'resolved' ? 'This ticket was escalated' : 'Escalated: review this one first'}
            </p>
            <p className="text-small text-danger-ink">{ticket.escalation_reason ?? 'No reason was recorded.'}</p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-6">
          <Sheet title="Customer’s message">
            <p className="max-w-[70ch] whitespace-pre-wrap leading-7">{ticket.body}</p>
          </Sheet>
          <ReviewPanel ticket={ticket} onRerun={() => rerun.mutate()} rerunning={rerun.isPending} />
        </div>
        <aside className="space-y-6" aria-label="Context for the review">
          <TriageCard ticket={ticket} />
          {ticket.order && <OrderSlip order={ticket.order} />}
          <GroundingList hits={hits} />
        </aside>
      </div>
    </>
  )
}
