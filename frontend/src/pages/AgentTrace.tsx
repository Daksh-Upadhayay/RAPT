import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router'
import { getAgentTrace, getTicket, ticketKeys } from '../api/tickets'
import { AgentStepCard, type StepState } from '../components/AgentStepCard'
import { StatusBadge } from '../components/StatusBadge'
import { Card, ErrorMessage, Loading, PageHeader } from '../components/ui'
import { isRunning, milliseconds } from '../lib/format'
import { currentRun, errorOf, groupRuns, logFor, type Run } from '../lib/trace'
import { AGENT_NAMES } from '../types'

export function AgentTrace() {
  const { id = '' } = useParams()
  const ticketQuery = useQuery({
    queryKey: ticketKeys.detail(id),
    queryFn: () => getTicket(id),
    refetchInterval: (q) => (q.state.data && isRunning(q.state.data.status) ? 1500 : false),
  })
  const running = ticketQuery.data ? isRunning(ticketQuery.data.status) : false
  const traceQuery = useQuery({
    queryKey: ticketKeys.trace(id),
    queryFn: () => getAgentTrace(id),
    refetchInterval: running ? 1000 : false,
  })
  const [picked, setPicked] = useState<number | null>(null)

  if (ticketQuery.isPending || traceQuery.isPending) return <Loading label="Loading trace…" />
  const error = ticketQuery.error ?? traceQuery.error
  if (error) {
    return (
      <>
        <PageHeader title="Agent trace" back={{ to: `/tickets/${id}`, label: 'Ticket' }} />
        <ErrorMessage error={error} onRetry={() => void Promise.all([ticketQuery.refetch(), traceQuery.refetch()])} />
      </>
    )
  }

  const ticket = ticketQuery.data!
  const logs = traceQuery.data!
  const runs = groupRuns(logs)
  const latest = currentRun({ status: ticket.status, agent_logs: logs })
  const allRuns: Run[] = latest.number > runs.length ? [...runs, latest] : runs
  const run = allRuns.find((r) => r.number === picked) ?? latest
  const isLive = run.number === latest.number && running
  const total = run.logs.reduce((sum, l) => sum + (l.duration_ms ?? 0), 0)
  const nextAgent = AGENT_NAMES.find(
    (a) => !logFor(run, a) && !(a === 'order_lookup' && ticket.order_id === null),
  )

  function stateOf(agentIndex: number): StepState {
    const agent = AGENT_NAMES[agentIndex]
    const log = logFor(run, agent)
    if (log) return errorOf(log) ? 'failed' : 'done'
    if (agent === 'order_lookup' && ticket.order_id === null) return 'skipped'
    if (run.failed) return 'not_run'
    if (isLive && agent === nextAgent) return 'running'
    return 'pending'
  }

  return (
    <>
      <PageHeader
        back={{ to: `/tickets/${id}`, label: 'Back to ticket' }}
        title="Agent trace"
        subtitle={<span className="line-clamp-1">{ticket.subject}</span>}
        actions={<StatusBadge status={ticket.status} />}
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        {allRuns.length > 1 && (
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5" role="group" aria-label="Agent runs">
            {allRuns.map((r) => (
              <button
                key={r.number}
                type="button"
                onClick={() => setPicked(r.number)}
                aria-pressed={r.number === run.number}
                className={`rounded-md px-3 py-1 text-sm ${r.number === run.number ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
              >
                Run {r.number}
                {r.number === latest.number && ' (latest)'}
              </button>
            ))}
          </div>
        )}
        <p className="text-sm text-slate-500">
          {isLive ? 'Live: steps appear as each agent finishes.' : `${run.logs.length} steps · ${milliseconds(total)} total`}
          {run.failed && <span className="ml-2 font-medium text-red-700">Run stopped at an error</span>}
        </p>
      </div>

      {run.logs.length === 0 && !isLive ? (
        <Card>
          <p className="text-sm text-slate-500">No agent steps logged for this ticket yet.</p>
        </Card>
      ) : (
        <ol className="max-w-3xl">
          {AGENT_NAMES.map((agent, i) => (
            <AgentStepCard
              key={agent}
              agent={agent}
              log={logFor(run, agent)}
              state={stateOf(i)}
              index={i}
              last={i === AGENT_NAMES.length - 1}
            />
          ))}
        </ol>
      )}
    </>
  )
}
