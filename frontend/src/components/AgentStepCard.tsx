import type { ReactNode } from 'react'
import { AGENT_DESCRIPTIONS, AGENT_LABELS, CATEGORY_LABELS, ORDER_STATUS_LABELS, URGENCY_LABELS, milliseconds, money, percent } from '../lib/format'
import { draftOutput, errorOf, escalationOutput, orderLookupOutput, retrievedHits, triageOutput } from '../lib/trace'
import type { AgentLogResponse, AgentName, OrderStatus } from '../types'
import { CheckIcon, SkipIcon, Spinner, XIcon } from './icons'

export type StepState = 'done' | 'failed' | 'running' | 'pending' | 'skipped' | 'not_run'

function Summary({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-medium tracking-wide text-slate-400 uppercase">{label}</p>
      <div className="mt-1 text-sm text-slate-700">{children}</div>
    </div>
  )
}

function inputSummary(agent: AgentName, log: AgentLogResponse): ReactNode {
  const input = log.input
  switch (agent) {
    case 'triage':
    case 'knowledge': {
      const text = `${input.subject ?? ''} ${input.body ?? ''}`.trim()
      return (
        <>
          <p className="line-clamp-2 italic">“{text}”</p>
          {agent === 'knowledge' && <p className="mt-1 text-xs text-slate-500">Embedded and matched against the knowledge base, top 3</p>}
        </>
      )
    }
    case 'order_lookup':
      return <span className="font-mono text-xs">order_id {String(input.order_id ?? '–')}</span>
    case 'draft': {
      const prompt = String(input.user_prompt ?? '')
      const kb = (prompt.match(/<entry /g) ?? []).length
      return (
        <p>
          Customer message, {prompt.includes('<order>') ? 'order record' : 'no order'}, {kb} knowledge{' '}
          {kb === 1 ? 'entry' : 'entries'} <span className="text-slate-400">· {prompt.length.toLocaleString()} character prompt</span>
        </p>
      )
    }
    case 'escalation': {
      const amount = (input.order_data as { amount?: number } | null)?.amount
      return (
        <p>
          {String(input.category ?? '–')} ({percent(Number(input.category_confidence ?? NaN) || null)}), {String(input.urgency ?? '–')} urgency (
          {percent(Number(input.urgency_confidence ?? NaN) || null)}){amount !== undefined && <>, order {money(amount)}</>}
        </p>
      )
    }
  }
}

function outputSummary(agent: AgentName, log: AgentLogResponse): ReactNode {
  switch (agent) {
    case 'triage': {
      const { category, urgency } = triageOutput(log)
      return (
        <p>
          {category ? `${CATEGORY_LABELS[category.label]} (${percent(category.confidence)})` : '–'} ·{' '}
          {urgency ? `${URGENCY_LABELS[urgency.label]} urgency (${percent(urgency.confidence)})` : '–'}
        </p>
      )
    }
    case 'knowledge': {
      const hits = retrievedHits(log)
      if (!hits.length) return <p>No entries retrieved</p>
      return (
        <ol className="space-y-0.5">
          {hits.map((h) => (
            <li key={h.id} className="flex justify-between gap-3">
              <span className="truncate">{h.title}</span>
              <span className="shrink-0 text-slate-400 tabular-nums">{h.similarity.toFixed(2)}</span>
            </li>
          ))}
        </ol>
      )
    }
    case 'order_lookup': {
      const order = orderLookupOutput(log)
      if (!order) return <p>No order found</p>
      const status = ORDER_STATUS_LABELS[order.status as OrderStatus] ?? order.status
      return (
        <p>
          {order.item_name} · {status} · {money(order.amount)}
          {order.expected_delivery && <> · due {order.expected_delivery}</>}
        </p>
      )
    }
    case 'draft': {
      const out = draftOutput(log)
      const usage = out.usage
      return (
        <>
          <p className="line-clamp-3 whitespace-pre-wrap">{out.draft_text ?? '–'}</p>
          <p className="mt-1 text-xs text-slate-500">
            {out.mode === 'offline' ? 'Offline placeholder' : out.model}
            {usage?.input_tokens !== undefined && ` · ${usage.input_tokens} in / ${usage.output_tokens ?? '?'} out tokens`}
          </p>
        </>
      )
    }
    case 'escalation': {
      const { decision, rules } = escalationOutput(log)
      if (!decision) return <p>–</p>
      return decision.needs_escalation ? (
        <p className="font-medium text-red-800">
          Escalate: <span className="font-normal">{rules.join('; ') || decision.reason}</span>
        </p>
      ) : (
        <p>No escalation rule fired</p>
      )
    }
  }
}

function Raw({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-slate-500">{label}</p>
      <pre className="max-h-80 overflow-auto rounded-lg bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

const DOT: Record<StepState, string> = {
  done: 'bg-emerald-600 text-white',
  failed: 'bg-red-600 text-white',
  running: 'bg-indigo-600 text-white',
  pending: 'bg-white text-slate-400 ring-2 ring-slate-200',
  skipped: 'bg-slate-100 text-slate-400',
  not_run: 'bg-slate-100 text-slate-400',
}

export function AgentStepCard({ agent, log, state, index, last }: {
  agent: AgentName
  log?: AgentLogResponse
  state: StepState
  index: number
  last: boolean
}) {
  const error = log ? errorOf(log) : null
  return (
    <li className="relative flex gap-4">
      {!last && <span className="absolute top-9 bottom-0 left-[15px] w-0.5 bg-slate-200" aria-hidden="true" />}
      <span className={`relative z-[1] flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${DOT[state]}`}>
        {state === 'done' ? <CheckIcon /> : state === 'failed' ? <XIcon /> : state === 'running' ? <Spinner /> : state === 'skipped' || state === 'not_run' ? <SkipIcon /> : index + 1}
      </span>
      <div className={`mb-6 min-w-0 flex-1 rounded-xl border bg-white ${state === 'failed' ? 'border-red-200' : 'border-slate-200'} ${state === 'pending' || state === 'skipped' || state === 'not_run' ? 'opacity-60' : ''}`}>
        <header className="flex flex-wrap items-baseline justify-between gap-2 px-4 pt-3">
          <div>
            <h3 className="font-semibold text-slate-900">{AGENT_LABELS[agent]}</h3>
            <p className="text-xs text-slate-500">{AGENT_DESCRIPTIONS[agent]}</p>
          </div>
          <span className="text-sm text-slate-500 tabular-nums">
            {state === 'skipped' ? 'skipped: no order linked' : state === 'not_run' ? 'not run' : state === 'running' ? 'running…' : log ? milliseconds(log.duration_ms) : 'waiting'}
          </span>
        </header>
        {log && (
          <div className="p-4">
            {error ? (
              <p className="rounded-lg bg-red-50 px-3 py-2 font-mono text-xs text-red-800">{error}</p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                <Summary label="Input">{inputSummary(agent, log)}</Summary>
                <Summary label="Output">{outputSummary(agent, log)}</Summary>
              </div>
            )}
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer text-xs font-medium text-indigo-600 hover:underline">Raw log</summary>
              <div className="mt-3 space-y-3">
                <Raw label="input" value={log.input} />
                <Raw label="output" value={log.output} />
                {log.tool_calls && <Raw label="tool_calls" value={log.tool_calls} />}
              </div>
            </details>
          </div>
        )}
      </div>
    </li>
  )
}
