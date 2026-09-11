import { Link } from 'react-router'
import { useReviewQueue } from '../features/review'
import { TicketStrip, useTicketsWithStatus } from '../features/tickets'
import { ButtonLink, EmptyState, ErrorNotice, Loading, PageHeader } from '../ui'

function WithTheAgents() {
  const fresh = useTicketsWithStatus('new')
  const running = useTicketsWithStatus('in_progress')
  const tickets = [...(fresh.data ?? []), ...(running.data ?? [])]
  if (!tickets.length) return null
  return (
    <section className="mb-10" aria-labelledby="with-agents">
      <h2 id="with-agents" className="type-heading mb-3 text-small text-ink-2">
        With the agents ({tickets.length})
      </h2>
      <div className="space-y-2">
        {tickets.map((t) => (
          <TicketStrip key={t.id} ticket={t} showStatus />
        ))}
      </div>
    </section>
  )
}

export function ReviewQueue() {
  const queue = useReviewQueue()
  const escalated = queue.data?.filter((t) => t.needs_escalation).length ?? 0

  return (
    <>
      <PageHeader
        title="Review queue"
        intro="Every AI draft waits here for a person to check it. Escalated tickets come first, then the most urgent, then the oldest."
        actions={<ButtonLink to="/submit">Submit a ticket</ButtonLink>}
      />
      <WithTheAgents />
      {queue.isPending ? (
        <Loading label="Loading the queue…" />
      ) : queue.isError ? (
        <ErrorNotice error={queue.error} onRetry={() => void queue.refetch()} />
      ) : queue.data.length === 0 ? (
        <EmptyState title="Nothing to review">
          Tickets arrive here once the agents have drafted a reply.{' '}
          <Link to="/submit" className="font-semibold text-ink underline underline-offset-2">
            Submit a ticket
          </Link>{' '}
          to start one.
        </EmptyState>
      ) : (
        <section aria-labelledby="awaiting">
          <h2 id="awaiting" className="type-heading mb-3 text-small text-ink-2">
            Awaiting review ({queue.data.length}){escalated > 0 && <span className="text-danger-ink">, {escalated} escalated</span>}
          </h2>
          <div className="space-y-2">
            {queue.data.map((t) => (
              <TicketStrip key={t.id} ticket={t} />
            ))}
          </div>
        </section>
      )}
    </>
  )
}
