import { useState } from 'react'
import { useParams } from 'react-router'
import { isRunning, milliseconds } from '../lib/format'
import { StatusTag, useAgentTrace, useTicket } from '../features/tickets'
import { TraceTimeline, currentRun, groupRuns, type Run } from '../features/trace'
import { ErrorNotice, Loading, PageHeader, Segmented, Sheet } from '../ui'

export function AgentTrace() {
  const { id = '' } = useParams()
  const ticketQuery = useTicket(id)
  const live = ticketQuery.data ? isRunning(ticketQuery.data.status) : false
  const traceQuery = useAgentTrace(id, live)
  const [picked, setPicked] = useState<number | null>(null)

  if (ticketQuery.isPending || traceQuery.isPending) return <Loading label="Loading the trace…" />
  const error = ticketQuery.error ?? traceQuery.error
  if (error) {
    return (
      <>
        <PageHeader title="Agent trace" back={{ to: `/tickets/${id}`, label: 'Ticket' }} />
        <ErrorNotice error={error} onRetry={() => void Promise.all([ticketQuery.refetch(), traceQuery.refetch()])} />
      </>
    )
  }

  const ticket = ticketQuery.data!
  const logs = traceQuery.data!
  const runs = groupRuns(logs)
  const latest = currentRun({ status: ticket.status, agent_logs: logs })
  const allRuns: Run[] = latest.number > runs.length ? [...runs, latest] : runs
  const run = allRuns.find((r) => r.number === picked) ?? latest
  const runIsLive = live && run.number === latest.number
  const total = run.logs.reduce((sum, l) => sum + (l.duration_ms ?? 0), 0)

  return (
    <>
      <PageHeader
        back={{ to: `/tickets/${id}`, label: 'Back to the ticket' }}
        title="Agent trace"
        intro={ticket.subject}
        actions={<StatusTag status={ticket.status} />}
      />
      <div className="mb-8 flex flex-wrap items-center gap-4">
        {allRuns.length > 1 && (
          <Segmented
            label="Agent runs"
            value={run.number}
            onChange={setPicked}
            options={allRuns.map((r) => ({ value: r.number, label: r.number === latest.number ? `Run ${r.number} (latest)` : `Run ${r.number}` }))}
          />
        )}
        <p className="text-small text-ink-2">
          {runIsLive
            ? 'Live. Each step appears as the agent finishes it.'
            : run.failed
              ? 'This run stopped at an error.'
              : `${run.logs.length} steps in ${milliseconds(total)}.`}
        </p>
      </div>
      {run.logs.length === 0 && !runIsLive ? (
        <Sheet>
          <p className="text-small text-ink-2">No agent has worked on this ticket yet.</p>
        </Sheet>
      ) : (
        <TraceTimeline run={run} hasOrder={ticket.order_id !== null} live={runIsLive} />
      )}
    </>
  )
}
