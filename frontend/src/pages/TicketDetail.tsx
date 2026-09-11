import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { getReviewQueue, reviewKeys } from '../api/reviews'
import { getTicket, rerunAgents, ticketKeys } from '../api/tickets'
import { CategoryBadge } from '../components/CategoryBadge'
import { DraftEditor } from '../components/DraftEditor'
import { KnowledgeSnippets } from '../components/KnowledgeSnippets'
import { OrderCard } from '../components/OrderCard'
import { RunProgress } from '../components/RunProgress'
import { EscalationFlag, StatusBadge } from '../components/StatusBadge'
import { ArrowRightIcon, CheckIcon, FlagIcon, RefreshIcon, Spinner } from '../components/icons'
import { Card, ErrorMessage, Loading, PageHeader } from '../components/ui'
import { UrgencyBadge } from '../components/UrgencyBadge'
import { CATEGORY_LABELS, URGENCY_LABELS, dateTime, isRunning, percent, timeAgo } from '../lib/format'
import { currentRun, draftOutput, logFor, retrievedHits, triageOutput } from '../lib/trace'
import type { DraftResponseRead, TicketDetailResponse } from '../types'

function Confidence({ label, value, version }: { label: string; value: number; version: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium text-slate-900">{label}</span>
        <span className="text-slate-500 tabular-nums">{percent(value)}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-indigo-100" role="meter" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={`${label} confidence`}>
        <div className="h-full rounded-full bg-indigo-500" style={{ width: `${value * 100}%` }} />
      </div>
      <p className="mt-1 text-xs text-slate-400">model {version}</p>
    </div>
  )
}

function TriageCard({ ticket }: { ticket: TicketDetailResponse }) {
  const { category, urgency } = triageOutput(logFor(currentRun(ticket), 'triage'))
  return (
    <Card title="Triage">
      {category && urgency ? (
        <div className="space-y-4">
          <Confidence label={CATEGORY_LABELS[category.label]} value={category.confidence} version={category.model_version} />
          <Confidence label={`${URGENCY_LABELS[urgency.label]} urgency`} value={urgency.confidence} version={urgency.model_version} />
        </div>
      ) : (
        <p className="text-sm text-slate-500">Not classified yet.</p>
      )}
    </Card>
  )
}

function NextInQueue({ currentId }: { currentId: string }) {
  const { data } = useQuery({ queryKey: reviewKeys.queue, queryFn: getReviewQueue })
  const next = data?.find((t) => t.id !== currentId)
  return next ? (
    <Link to={`/tickets/${next.id}`} className="btn-primary">
      Next in queue <ArrowRightIcon />
    </Link>
  ) : (
    <Link to="/reviews" className="btn-secondary">
      Queue is clear, back to queue
    </Link>
  )
}

function ResolvedReply({ ticket, draft }: { ticket: TicketDetailResponse; draft: DraftResponseRead }) {
  const edited = draft.edited_text !== null
  return (
    <Card
      title="Reply sent"
      action={
        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
          <CheckIcon className="size-3.5" />
          {edited ? 'Edited and approved' : 'Approved as written'}
        </span>
      }
    >
      <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-800">{draft.edited_text ?? draft.draft_text}</p>
      <p className="mt-4 text-xs text-slate-500">
        By {draft.reviewer_id} · {draft.reviewed_at ? dateTime(draft.reviewed_at) : ''}
      </p>
      {edited && (
        <details className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
          <summary className="cursor-pointer font-medium text-slate-700">Original AI draft</summary>
          <p className="mt-2 leading-relaxed whitespace-pre-wrap text-slate-600">{draft.draft_text}</p>
        </details>
      )}
      <div className="mt-5">
        <NextInQueue currentId={ticket.id} />
      </div>
    </Card>
  )
}

function ReviewPanel({ ticket, onRerun, rerunning }: { ticket: TicketDetailResponse; onRerun: () => void; rerunning: boolean }) {
  const run = currentRun(ticket)
  const latest = ticket.draft_responses.at(-1)

  if (isRunning(ticket.status)) {
    return (
      <Card title="Agents are working on this ticket">
        <RunProgress run={run} hasOrder={ticket.order_id !== null} />
        <p className="mt-4 text-xs text-slate-500">
          This page updates by itself.{' '}
          <Link to={`/tickets/${ticket.id}/trace`} className="font-medium text-indigo-600 hover:underline">
            Watch the full trace
          </Link>
        </p>
      </Card>
    )
  }

  if (ticket.status === 'resolved') {
    const approved = ticket.draft_responses.findLast((d) => d.approved)
    return approved ? <ResolvedReply ticket={ticket} draft={approved} /> : null
  }

  if (latest && latest.approved === null) {
    const { mode, model } = draftOutput(logFor(run, 'draft'))
    return (
      <Card
        title="AI draft"
        action={model && <span className="text-xs text-slate-500">{mode === 'offline' ? 'offline placeholder' : model}</span>}
      >
        <DraftEditor key={latest.id} ticketId={ticket.id} draft={latest} />
      </Card>
    )
  }

  // Awaiting review but no draft: the run failed before the Draft Agent finished
  return (
    <Card title="No draft to review">
      <p className="text-sm text-slate-600">
        The agent run stopped before a draft was written. Check the{' '}
        <Link to={`/tickets/${ticket.id}/trace`} className="font-medium text-indigo-600 hover:underline">
          agent trace
        </Link>{' '}
        for the error, then rerun the agents.
      </p>
      <button type="button" className="btn-primary mt-4" onClick={onRerun} disabled={rerunning}>
        {rerunning ? <Spinner /> : <RefreshIcon />}
        Rerun agents
      </button>
    </Card>
  )
}

export function TicketDetail() {
  const { id = '' } = useParams()
  const queryClient = useQueryClient()
  const ticketQuery = useQuery({
    queryKey: ticketKeys.detail(id),
    queryFn: () => getTicket(id),
    // Poll while the agents run, so each step shows up as it finishes
    refetchInterval: (q) => (q.state.data && isRunning(q.state.data.status) ? 1500 : false),
  })
  const rerun = useMutation({
    mutationFn: () => rerunAgents(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ticketKeys.detail(id) })
      void queryClient.invalidateQueries({ queryKey: reviewKeys.queue })
    },
  })

  if (ticketQuery.isPending) return <Loading label="Loading ticket…" />
  if (ticketQuery.isError) {
    return (
      <>
        <PageHeader title="Ticket" back={{ to: '/reviews', label: 'Review queue' }} />
        <ErrorMessage error={ticketQuery.error} onRetry={() => void ticketQuery.refetch()} />
      </>
    )
  }

  const ticket = ticketQuery.data
  const hits = retrievedHits(logFor(currentRun(ticket), 'knowledge'))
  const canRerun = ticket.status === 'awaiting_review'

  return (
    <>
      <PageHeader
        back={{ to: '/reviews', label: 'Review queue' }}
        title={ticket.subject}
        subtitle={
          <span title={dateTime(ticket.created_at)}>
            Submitted {timeAgo(ticket.created_at)} · <span className="font-mono text-xs">{ticket.id.slice(0, 8)}</span>
          </span>
        }
        actions={
          <>
            <Link to={`/tickets/${ticket.id}/trace`} className="btn-secondary">
              Agent trace
            </Link>
            {canRerun && (
              <button type="button" className="btn-ghost" onClick={() => rerun.mutate()} disabled={rerun.isPending}>
                {rerun.isPending ? <Spinner /> : <RefreshIcon />}
                Rerun agents
              </button>
            )}
          </>
        }
      />

      <div className="-mt-3 mb-6 flex flex-wrap items-center gap-2">
        <StatusBadge status={ticket.status} />
        <CategoryBadge category={ticket.category} />
        <UrgencyBadge urgency={ticket.urgency} />
        {ticket.needs_escalation && <EscalationFlag compact />}
      </div>

      {rerun.isError && (
        <div className="mb-4">
          <ErrorMessage error={rerun.error} />
        </div>
      )}

      {ticket.needs_escalation && (
        <div className="mb-6 flex gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900" role="note">
          <FlagIcon className="mt-0.5 size-4 shrink-0 text-red-700" />
          <div>
            <p className="font-semibold">Flagged for escalation</p>
            <p className="mt-0.5 text-red-800">{ticket.escalation_reason ?? 'No reason recorded.'}</p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Customer message">
            <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-800">{ticket.body}</p>
          </Card>
          <ReviewPanel ticket={ticket} onRerun={() => rerun.mutate()} rerunning={rerun.isPending} />
        </div>
        <div className="space-y-6">
          <TriageCard ticket={ticket} />
          {ticket.order && <OrderCard order={ticket.order} />}
          <KnowledgeSnippets hits={hits} />
        </div>
      </div>
    </>
  )
}
