import { AGENT_LABELS, milliseconds } from '../lib/format'
import { errorOf, expectedSteps, logFor, type Run } from '../lib/trace'
import { CheckIcon, Spinner, XIcon } from './icons'

/** Live checklist of the agent steps while a run is in progress. */
export function RunProgress({ run, hasOrder }: { run: Run; hasOrder: boolean }) {
  const steps = expectedSteps(hasOrder)
  const nextIndex = steps.findIndex((agent) => !logFor(run, agent))
  return (
    <ol className="space-y-2" aria-live="polite">
      {steps.map((agent, i) => {
        const log = logFor(run, agent)
        const failed = log ? errorOf(log) : null
        const active = !run.failed && i === nextIndex
        return (
          <li key={agent} className="flex items-center gap-3 text-sm">
            <span
              className={`flex size-6 shrink-0 items-center justify-center rounded-full ${
                failed
                  ? 'bg-red-100 text-red-700'
                  : log
                    ? 'bg-emerald-100 text-emerald-700'
                    : active
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'bg-slate-100 text-slate-400'
              }`}
            >
              {failed ? <XIcon className="size-3.5" /> : log ? <CheckIcon className="size-3.5" /> : active ? <Spinner className="size-3.5" /> : i + 1}
            </span>
            <span className={log || active ? 'text-slate-900' : 'text-slate-400'}>{AGENT_LABELS[agent]}</span>
            {log && <span className="ml-auto text-xs text-slate-500 tabular-nums">{milliseconds(log.duration_ms)}</span>}
          </li>
        )
      })}
    </ol>
  )
}
