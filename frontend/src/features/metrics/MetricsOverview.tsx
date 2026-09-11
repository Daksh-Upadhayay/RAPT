import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getMetricsSummary, metricsKeys } from '../../api/metrics'
import { duration, percent } from '../../lib/format'
import { ErrorNotice, Loading } from '../../ui'
import { CategoryChart, EscalationChart, OutcomeChart, ResolutionChart } from './charts'

function Figure({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="bg-paper px-5 py-4 last:col-span-2 lg:last:col-span-1">
      <dt className="text-small text-ink-2">{label}</dt>
      <dd className="type-label mt-1 text-title">{value}</dd>
      <dd className="mt-0.5 text-tiny text-ink-3">{detail}</dd>
    </div>
  )
}

/** Headline figures on one strip, then the four charts. Refreshes every 10 seconds. */
export function MetricsOverview() {
  const [days, setDays] = useState(30)
  const query = useQuery({
    queryKey: metricsKeys.summary(days),
    queryFn: () => getMetricsSummary(days),
    refetchInterval: 10_000,
    placeholderData: keepPreviousData, // keep the frame while another range loads
  })

  if (query.isPending) return <Loading label="Loading figures…" />
  if (query.isError) return <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />

  const s = query.data
  const withAgents = s.tickets_by_status.new + s.tickets_by_status.in_progress
  return (
    <div className={`space-y-6 transition-opacity ${query.isPlaceholderData ? 'opacity-60' : ''}`}>
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-label border border-line bg-line lg:grid-cols-5">
        <Figure label="Tickets" value={s.total_tickets.toLocaleString()} detail={`${s.tickets_by_status.resolved} resolved`} />
        <Figure label="Awaiting review" value={s.tickets_by_status.awaiting_review.toLocaleString()} detail={`${withAgents} with the agents`} />
        <Figure label="Escalated" value={percent(s.escalation_rate)} detail="of tickets the agents finished" />
        <Figure label="Approved as written" value={percent(s.approval_rate)} detail={`of ${s.drafts_reviewed} reviewed ${s.drafts_reviewed === 1 ? 'draft' : 'drafts'}`} />
        <Figure label="Time to resolve" value={duration(s.avg_resolution_seconds)} detail="average, submitted to approved" />
      </dl>
      <div className="grid gap-6 lg:grid-cols-2">
        <CategoryChart data={s.tickets_by_category} />
        <EscalationChart data={s.escalation_by_day} days={days} setDays={setDays} />
        <OutcomeChart summary={s} />
        <ResolutionChart data={s.resolution_by_category} />
      </div>
    </div>
  )
}
