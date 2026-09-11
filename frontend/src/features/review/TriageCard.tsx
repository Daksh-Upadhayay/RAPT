import { useState } from 'react'
import { CATEGORY_LABELS, URGENCY_LABELS, dateTime, effectiveCategory, effectiveUrgency, isRunning, percent } from '../../lib/format'
import { TICKET_CATEGORIES, TICKET_URGENCIES, type TicketCategory, type TicketDetailResponse, type TicketUrgency } from '../../types'
import { Button, ErrorNotice, Field, Meter, Select, Sheet } from '../../ui'
import { currentRun, logFor, triageOutput } from '../trace/model'
import { useCorrectTriage } from './hooks'

function Prediction({ label, confidence, version }: { label: string; confidence: number; version: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-semibold">{label}</span>
        <span className="text-small text-ink-2 tabular-nums">{percent(confidence)} sure</span>
      </div>
      <div className="mt-1.5">
        <Meter label={`${label}: model confidence`} value={confidence} />
      </div>
      <p className="mt-1 text-tiny text-ink-3">Model {version}</p>
    </div>
  )
}

function CorrectionForm({ ticket, onDone }: { ticket: TicketDetailResponse; onDone: () => void }) {
  const [category, setCategory] = useState<TicketCategory>(effectiveCategory(ticket)!)
  const [urgency, setUrgency] = useState<TicketUrgency>(effectiveUrgency(ticket)!)
  const correct = useCorrectTriage(ticket.id)
  const unchanged = category === effectiveCategory(ticket) && urgency === effectiveUrgency(ticket)

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        correct.mutate({ category, urgency }, { onSuccess: onDone })
      }}
    >
      <Field id="corrected-category" label="Category">
        <Select id="corrected-category" value={category} onChange={(e) => setCategory(e.target.value as TicketCategory)}>
          {TICKET_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABELS[c]}
              {c === ticket.category ? ' (model’s choice)' : ''}
            </option>
          ))}
        </Select>
      </Field>
      <Field id="corrected-urgency" label="Urgency" hint="Corrections become training data for the next model version.">
        <Select id="corrected-urgency" value={urgency} onChange={(e) => setUrgency(e.target.value as TicketUrgency)}>
          {TICKET_URGENCIES.map((u) => (
            <option key={u} value={u}>
              {URGENCY_LABELS[u]}
              {u === ticket.urgency ? ' (model’s choice)' : ''}
            </option>
          ))}
        </Select>
      </Field>
      {correct.isError && <ErrorNotice error={correct.error} />}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" loading={correct.isPending} disabled={unchanged}>
          Save correction
        </Button>
        <Button variant="ghost" size="sm" onClick={onDone} disabled={correct.isPending}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

function CorrectionNote({ ticket, onChange }: { ticket: TicketDetailResponse; onChange: () => void }) {
  return (
    <div className="rounded-label border border-accent-deep bg-accent-wash px-4 py-3 text-small">
      <p className="font-semibold">Corrected by {ticket.corrected_by}</p>
      <dl className="mt-1.5 space-y-1">
        {ticket.corrected_category && (
          <div>
            <dt className="inline text-ink-2">Category: </dt>
            <dd className="inline font-semibold">{CATEGORY_LABELS[ticket.corrected_category]}</dd>
            <span className="text-ink-2"> (model said {CATEGORY_LABELS[ticket.category!]})</span>
          </div>
        )}
        {ticket.corrected_urgency && (
          <div>
            <dt className="inline text-ink-2">Urgency: </dt>
            <dd className="inline font-semibold">{URGENCY_LABELS[ticket.corrected_urgency]}</dd>
            <span className="text-ink-2"> (model said {URGENCY_LABELS[ticket.urgency!]})</span>
          </div>
        )}
      </dl>
      {ticket.corrected_at && <p className="mt-1.5 text-tiny text-ink-2">{dateTime(ticket.corrected_at)}</p>}
      <button type="button" className="mt-2 text-tiny font-semibold underline underline-offset-2" onClick={onChange}>
        Change correction
      </button>
    </div>
  )
}

/** What the Triage Agent decided, how sure it was, and the reviewer's correction. */
export function TriageCard({ ticket }: { ticket: TicketDetailResponse }) {
  const [editing, setEditing] = useState(false)
  const { category, urgency } = triageOutput(logFor(currentRun(ticket), 'triage'))
  const canCorrect = ticket.category !== null && ticket.urgency !== null && !isRunning(ticket.status)
  const corrected = ticket.corrected_category !== null || ticket.corrected_urgency !== null

  return (
    <Sheet title="Triage" aside="Trained classifiers">
      {category && urgency ? (
        <div className="space-y-5">
          <Prediction label={CATEGORY_LABELS[category.label]} confidence={category.confidence} version={category.model_version} />
          <Prediction label={`${URGENCY_LABELS[urgency.label]} urgency`} confidence={urgency.confidence} version={urgency.model_version} />
          {canCorrect &&
            (editing ? (
              <CorrectionForm ticket={ticket} onDone={() => setEditing(false)} />
            ) : corrected ? (
              <CorrectionNote ticket={ticket} onChange={() => setEditing(true)} />
            ) : (
              <Button className="w-full" onClick={() => setEditing(true)}>
                Correct the triage
              </Button>
            ))}
        </div>
      ) : (
        <p className="text-small text-ink-2">The Triage Agent hasn’t classified this ticket yet.</p>
      )}
    </Sheet>
  )
}
