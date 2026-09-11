import { AGENT_DESCRIPTIONS, AGENT_LABELS, milliseconds } from '../../lib/format'
import { AGENT_NAMES, type AgentLogResponse, type AgentName } from '../../types'
import { CheckIcon, Spinner, XIcon } from '../../ui'
import { errorOf, logFor, type Run } from './model'
import { headline, inputSummary, outputSummary } from './summaries'

export type StepState = 'done' | 'failed' | 'running' | 'waiting' | 'skipped' | 'not_run'

const STATE_NOTE: Partial<Record<StepState, string>> = {
  running: 'Working…',
  waiting: 'Waiting',
  skipped: 'Skipped: no order linked to the ticket',
  not_run: 'Not run: an earlier step failed',
}

const clock = (iso: string) => new Date(iso).toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

function Marker({ state }: { state: StepState }) {
  const base = 'relative z-[1] flex size-7 shrink-0 items-center justify-center rounded-full border-2'
  if (state === 'done') return <span className={`${base} border-ink bg-ink text-paper`}><CheckIcon className="size-3.5" /></span>
  if (state === 'failed') return <span className={`${base} border-danger bg-danger text-paper`}><XIcon className="size-3.5" /></span>
  if (state === 'running') return <span className={`${base} border-ink bg-accent`}><Spinner className="size-3.5" /></span>
  return <span className={`${base} border-line bg-ground`} />
}

function Event({ agent, log, state, last }: { agent: AgentName; log?: AgentLogResponse; state: StepState; last: boolean }) {
  const error = log ? errorOf(log) : null
  const quiet = state === 'waiting' || state === 'skipped' || state === 'not_run'
  return (
    <li className="grid grid-cols-[4.75rem_1.75rem_1fr] gap-x-4 sm:grid-cols-[5.5rem_1.75rem_1fr]">
      <div className="pt-1 text-right text-tiny text-ink-3 tabular-nums">{log ? clock(log.created_at) : ''}</div>
      <div className="relative flex justify-center">
        {!last && <span className="absolute top-7 bottom-0 w-0.5 bg-ink/15" aria-hidden="true" />}
        <Marker state={state} />
      </div>
      <div className={`pb-8 ${quiet ? 'text-ink-3' : ''}`}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4">
          <h3 className="type-heading text-body">{AGENT_LABELS[agent]}</h3>
          {log && <span className="text-tiny text-ink-3 tabular-nums">{milliseconds(log.duration_ms)}</span>}
        </div>
        <p className={`mt-0.5 text-small ${error ? 'font-semibold text-danger-ink' : quiet ? '' : 'font-semibold'}`}>
          {error ? 'Failed' : log ? headline(agent, log) : STATE_NOTE[state]}
        </p>
        {!log && <p className="text-tiny">{AGENT_DESCRIPTIONS[agent]}</p>}

        {log && (
          <div className="mt-3 rounded-label border border-line bg-paper p-4">
            {error ? (
              <p className="font-mono text-tiny text-danger-ink">{error}</p>
            ) : (
              <div className="grid gap-4 text-small text-ink-2 md:grid-cols-2">
                <div>
                  <p className="mb-1 text-tiny font-semibold text-ink">Received</p>
                  {inputSummary(agent, log)}
                </div>
                <div>
                  <p className="mb-1 text-tiny font-semibold text-ink">Produced</p>
                  {outputSummary(agent, log)}
                </div>
              </div>
            )}
            <details className="mt-3">
              <summary className="cursor-pointer text-tiny font-semibold text-ink-2 hover:text-ink">Raw log</summary>
              <pre className="mt-2 max-h-80 overflow-auto rounded-label bg-ink p-3 font-mono text-tiny leading-5 text-paper">
                {JSON.stringify({ input: log.input, output: log.output, tool_calls: log.tool_calls }, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </div>
    </li>
  )
}

/**
 * A run's steps as a carrier-style tracking history: time, what happened, how long it
 * took. Steps not reached yet stay in the list, so the whole route is visible.
 */
export function TraceTimeline({ run, hasOrder, live }: { run: Run; hasOrder: boolean; live: boolean }) {
  const next = AGENT_NAMES.find((a) => !logFor(run, a) && !(a === 'order_lookup' && !hasOrder))

  function stateOf(agent: AgentName): StepState {
    const log = logFor(run, agent)
    if (log) return errorOf(log) ? 'failed' : 'done'
    if (agent === 'order_lookup' && !hasOrder) return 'skipped'
    if (run.failed) return 'not_run'
    return live && agent === next ? 'running' : 'waiting'
  }

  return (
    <ol className="max-w-3xl" aria-live={live ? 'polite' : undefined}>
      {AGENT_NAMES.map((agent, i) => (
        <Event key={agent} agent={agent} log={logFor(run, agent)} state={stateOf(agent)} last={i === AGENT_NAMES.length - 1} />
      ))}
    </ol>
  )
}
