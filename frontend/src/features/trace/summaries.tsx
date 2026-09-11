/** Plain-language readings of each agent's log, for the trace view. */
import type { ReactNode } from 'react'
import { CATEGORY_LABELS, ORDER_STATUS_LABELS, URGENCY_LABELS, calendarDate, money, percent } from '../../lib/format'
import type { AgentLogResponse, AgentName, OrderStatus } from '../../types'
import { draftOutput, escalationOutput, orderLookupOutput, retrievedHits, triageOutput } from './model'

/** One line: what the step concluded. */
export function headline(agent: AgentName, log: AgentLogResponse): string {
  switch (agent) {
    case 'triage': {
      const { category, urgency } = triageOutput(log)
      return category && urgency ? `${CATEGORY_LABELS[category.label]}, ${URGENCY_LABELS[urgency.label].toLowerCase()} urgency` : 'Classified'
    }
    case 'knowledge': {
      const n = retrievedHits(log).length
      return `Found ${n} knowledge-base ${n === 1 ? 'entry' : 'entries'}`
    }
    case 'order_lookup': {
      const order = orderLookupOutput(log)
      return order ? `${order.item_name}, ${ORDER_STATUS_LABELS[order.status as OrderStatus]?.toLowerCase() ?? order.status}` : 'No order found'
    }
    case 'draft': {
      const out = draftOutput(log)
      return out.mode === 'offline' ? 'Wrote a placeholder draft (no LLM configured)' : `Drafted a reply with ${out.model ?? 'the LLM'}`
    }
    case 'escalation': {
      const { decision } = escalationOutput(log)
      return decision?.needs_escalation ? 'Flagged for escalation' : 'No escalation needed'
    }
  }
}

export function inputSummary(agent: AgentName, log: AgentLogResponse): ReactNode {
  const input = log.input
  switch (agent) {
    case 'triage':
    case 'knowledge':
      return <p className="line-clamp-3">“{`${input.subject ?? ''}. ${input.body ?? ''}`.trim()}”</p>
    case 'order_lookup':
      return (
        <p>
          Order <span className="font-mono text-tiny">{String(input.order_id ?? '')}</span>
        </p>
      )
    case 'draft': {
      const prompt = String(input.user_prompt ?? '')
      const entries = (prompt.match(/<entry /g) ?? []).length
      return (
        <p>
          The customer’s message, {prompt.includes('<order>') ? 'the order record' : 'no order'} and {entries} knowledge{' '}
          {entries === 1 ? 'entry' : 'entries'}.
        </p>
      )
    }
    case 'escalation': {
      const amount = (input.order_data as { amount?: number } | null)?.amount
      const cat = typeof input.category === 'string' ? CATEGORY_LABELS[input.category as keyof typeof CATEGORY_LABELS] : '–'
      const urg = typeof input.urgency === 'string' ? URGENCY_LABELS[input.urgency as keyof typeof URGENCY_LABELS] : '–'
      return (
        <p>
          {cat} ({percent(typeof input.category_confidence === 'number' ? input.category_confidence : null)} sure), {urg.toLowerCase()} urgency (
          {percent(typeof input.urgency_confidence === 'number' ? input.urgency_confidence : null)} sure)
          {amount !== undefined && `, order of ${money(amount)}`}.
        </p>
      )
    }
  }
}

export function outputSummary(agent: AgentName, log: AgentLogResponse): ReactNode {
  switch (agent) {
    case 'triage': {
      const { category, urgency } = triageOutput(log)
      return (
        <p>
          {category && `${CATEGORY_LABELS[category.label]} (${percent(category.confidence)} sure, model ${category.model_version})`}
          <br />
          {urgency && `${URGENCY_LABELS[urgency.label]} urgency (${percent(urgency.confidence)} sure, model ${urgency.model_version})`}
        </p>
      )
    }
    case 'knowledge': {
      const hits = retrievedHits(log)
      return hits.length ? (
        <ol className="space-y-0.5">
          {hits.map((h) => (
            <li key={h.id} className="flex justify-between gap-3">
              <span className="truncate">{h.title}</span>
              <span className="shrink-0 text-ink-3 tabular-nums">{h.similarity.toFixed(2)}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p>Nothing close enough.</p>
      )
    }
    case 'order_lookup': {
      const order = orderLookupOutput(log)
      if (!order) return <p>No order with that ID.</p>
      return (
        <p>
          {money(order.amount)}
          {order.expected_delivery && `, expected ${calendarDate(order.expected_delivery)}`}
          {order.tracking_number && (
            <>
              , tracking <span className="font-mono text-tiny">{order.tracking_number}</span>
            </>
          )}
        </p>
      )
    }
    case 'draft': {
      const out = draftOutput(log)
      const usage = out.usage
      return (
        <>
          <p className="line-clamp-3 whitespace-pre-wrap">{out.draft_text ?? ''}</p>
          {usage?.input_tokens !== undefined && (
            <p className="mt-1 text-tiny text-ink-3">
              {usage.input_tokens} tokens in, {usage.output_tokens ?? '?'} out
            </p>
          )}
          {out.attempts?.some((a) => !a.ok) && (
            <ul className="mt-2 space-y-0.5 text-tiny">
              {out.attempts.map((a) => (
                <li key={a.provider} className={a.ok ? 'text-ink' : 'text-ink-3'}>
                  {a.provider}: {a.ok ? 'wrote the draft' : a.skipped ?? a.error}
                </li>
              ))}
            </ul>
          )}
        </>
      )
    }
    case 'escalation': {
      const { decision, rules } = escalationOutput(log)
      if (!decision) return null
      return decision.needs_escalation ? <p className="font-semibold text-danger-ink">{rules.join('; ') || decision.reason}</p> : <p>No rule fired.</p>
    }
  }
}
