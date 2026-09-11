import { Link } from 'react-router'
import { AGENT_LABELS, dateTime, isRunning, milliseconds } from '../../lib/format'
import type { DraftResponseRead, TicketDetailResponse } from '../../types'
import { ArrowRightIcon, Button, ButtonLink, CheckIcon, RefreshIcon, Sheet, Spinner, XIcon } from '../../ui'
import { currentRun, draftOutput, errorOf, expectedSteps, logFor, type Run } from '../trace/model'
import { DraftEditor } from './DraftEditor'
import { useReviewQueue } from './hooks'

function RunProgress({ run, hasOrder }: { run: Run; hasOrder: boolean }) {
  const steps = expectedSteps(hasOrder)
  const next = steps.findIndex((agent) => !logFor(run, agent))
  return (
    <ol className="space-y-3" aria-live="polite">
      {steps.map((agent, i) => {
        const log = logFor(run, agent)
        const failed = log ? errorOf(log) : null
        const active = !run.failed && i === next
        return (
          <li key={agent} className="flex items-center gap-3 text-small">
            <span
              className={`flex size-6 shrink-0 items-center justify-center rounded-full border ${
                failed ? 'border-danger bg-danger text-paper' : log ? 'border-ink bg-ink text-paper' : active ? 'border-ink' : 'border-line text-ink-3'
              }`}
            >
              {failed ? <XIcon className="size-3.5" /> : log ? <CheckIcon className="size-3.5" /> : active ? <Spinner className="size-3.5" /> : null}
            </span>
            <span className={log || active ? 'font-semibold' : 'text-ink-3'}>{AGENT_LABELS[agent]}</span>
            {log && <span className="ml-auto text-tiny text-ink-3 tabular-nums">{milliseconds(log.duration_ms)}</span>}
          </li>
        )
      })}
    </ol>
  )
}

function NextInQueue({ currentId }: { currentId: string }) {
  const { data } = useReviewQueue(false)
  const next = data?.find((t) => t.id !== currentId)
  return next ? (
    <ButtonLink to={`/tickets/${next.id}`} variant="primary">
      Next ticket <ArrowRightIcon />
    </ButtonLink>
  ) : (
    <ButtonLink to="/reviews">Back to the queue</ButtonLink>
  )
}

function ApprovedReply({ ticket, draft }: { ticket: TicketDetailResponse; draft: DraftResponseRead }) {
  const edited = draft.edited_text !== null
  return (
    <Sheet title="Approved reply" aside={edited ? 'Edited before approval' : 'Approved as the AI wrote it'}>
      <p className="max-w-[70ch] whitespace-pre-wrap leading-7">{draft.edited_text ?? draft.draft_text}</p>
      <p className="mt-5 text-tiny text-ink-3">
        Approved by {draft.reviewer_id}
        {draft.reviewed_at && `, ${dateTime(draft.reviewed_at)}`}
      </p>
      {edited && (
        <details className="mt-4 rounded-label bg-sunken px-4 py-3 text-small">
          <summary className="cursor-pointer font-semibold">Show the AI’s original draft</summary>
          <p className="mt-2 whitespace-pre-wrap leading-6 text-ink-2">{draft.draft_text}</p>
        </details>
      )}
      <div className="mt-6">
        <NextInQueue currentId={ticket.id} />
      </div>
    </Sheet>
  )
}

/** The main review area: live progress, the draft to approve, or the approved reply. */
export function ReviewPanel({ ticket, onRerun, rerunning }: { ticket: TicketDetailResponse; onRerun: () => void; rerunning: boolean }) {
  const run = currentRun(ticket)
  const latest = ticket.draft_responses.at(-1)

  if (isRunning(ticket.status)) {
    return (
      <Sheet title="The agents are working on this ticket" aside="Updates by itself">
        <RunProgress run={run} hasOrder={ticket.order_id !== null} />
        <p className="mt-5 text-small text-ink-2">
          <Link to={`/tickets/${ticket.id}/trace`} className="font-semibold text-ink underline underline-offset-2">
            Follow each step in the trace
          </Link>
        </p>
      </Sheet>
    )
  }

  if (ticket.status === 'resolved') {
    const approved = ticket.draft_responses.findLast((d) => d.approved)
    return approved ? <ApprovedReply ticket={ticket} draft={approved} /> : null
  }

  if (latest && latest.approved === null) {
    const { mode, model } = draftOutput(logFor(run, 'draft'))
    return (
      <Sheet title="Draft reply" aside={mode === 'offline' ? 'Placeholder text: no LLM is configured' : model && `Written by ${model}`}>
        <DraftEditor key={latest.id} ticketId={ticket.id} draft={latest} />
      </Sheet>
    )
  }

  // Awaiting review without a draft: the run stopped before the Draft Agent finished
  return (
    <Sheet title="No draft to review">
      <p className="text-small text-ink-2">
        The agents stopped before writing a draft. The{' '}
        <Link to={`/tickets/${ticket.id}/trace`} className="font-semibold text-ink underline underline-offset-2">
          trace
        </Link>{' '}
        shows which step failed. Run the agents again to get a draft.
      </p>
      <Button variant="primary" className="mt-5" icon={<RefreshIcon />} loading={rerunning} onClick={onRerun}>
        Run the agents again
      </Button>
    </Sheet>
  )
}
