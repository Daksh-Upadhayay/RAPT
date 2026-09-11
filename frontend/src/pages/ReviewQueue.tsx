import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getReviewQueue, reviewKeys } from '../api/reviews'
import { listTickets, ticketKeys } from '../api/tickets'
import { TicketCard } from '../components/TicketCard'
import { EmptyState, ErrorMessage, Loading, PageHeader } from '../components/ui'

function Processing() {
  // Tickets the agents are still working on: they join the queue when the run ends
  const { data = [] } = useQuery({
    queryKey: ticketKeys.list({ status: 'in_progress' }),
    queryFn: () => listTickets({ status: 'in_progress' }),
    refetchInterval: 3000,
  })
  const { data: fresh = [] } = useQuery({
    queryKey: ticketKeys.list({ status: 'new' }),
    queryFn: () => listTickets({ status: 'new' }),
    refetchInterval: 3000,
  })
  const running = [...fresh, ...data]
  if (!running.length) return null
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold text-slate-700">
        Agents working <span className="font-normal text-slate-400">({running.length})</span>
      </h2>
      <div className="space-y-2">
        {running.map((t) => (
          <TicketCard key={t.id} ticket={t} showStatus />
        ))}
      </div>
    </section>
  )
}

export function ReviewQueue() {
  const queue = useQuery({ queryKey: reviewKeys.queue, queryFn: getReviewQueue, refetchInterval: 5000 })
  const escalated = queue.data?.filter((t) => t.needs_escalation).length ?? 0

  return (
    <>
      <PageHeader
        title="Review queue"
        subtitle="Every AI draft is checked by a person before it goes out. Escalated tickets first, then by urgency, then oldest."
        actions={
          <Link to="/submit" className="btn-secondary">
            Submit a ticket
          </Link>
        }
      />
      <Processing />
      {queue.isPending ? (
        <Loading label="Loading the queue…" />
      ) : queue.isError ? (
        <ErrorMessage error={queue.error} onRetry={() => void queue.refetch()} />
      ) : queue.data.length === 0 ? (
        <EmptyState title="Nothing to review">
          New tickets appear here once the agents finish.{' '}
          <Link to="/submit" className="font-medium text-indigo-600 hover:underline">
            Submit one
          </Link>{' '}
          to try it.
        </EmptyState>
      ) : (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-700">
            Awaiting review <span className="font-normal text-slate-400">({queue.data.length})</span>
            {escalated > 0 && <span className="ml-2 font-medium text-red-700">{escalated} escalated</span>}
          </h2>
          <div className="space-y-2">
            {queue.data.map((t) => (
              <TicketCard key={t.id} ticket={t} />
            ))}
          </div>
        </section>
      )}
    </>
  )
}
