/**
 * Typed views over agent_logs rows. The API types `input`/`output` as free-form JSON
 * (dict[str, Any]); the shapes below are what backend/app/agents/nodes.py writes. Every
 * reader tolerates missing fields, since old runs or failed steps may lack them.
 */
import type {
  AgentLogResponse,
  AgentName,
  CategoryPrediction,
  EscalationDecision,
  OrderLookupResult,
  TicketDetailResponse,
  UrgencyPrediction,
} from '../types'

export interface RetrievedHit {
  id: string
  title: string
  similarity: number
  content?: string // added in Phase 5; older runs logged title and score only
}

export interface Run {
  number: number // 1-based, oldest first
  logs: AgentLogResponse[]
  finished: boolean // reached the Escalation Agent, or stopped at an error
  failed: boolean
}

export const errorOf = (log: AgentLogResponse): string | null =>
  typeof log.output.error === 'string' ? log.output.error : null

/** Split a ticket's logs into runs: each run starts with a Triage Agent log. */
export function groupRuns(logs: AgentLogResponse[]): Run[] {
  const runs: Run[] = []
  for (const log of logs) {
    if (log.agent_name === 'triage' || runs.length === 0) {
      runs.push({ number: runs.length + 1, logs: [], finished: false, failed: false })
    }
    const run = runs[runs.length - 1]
    run.logs.push(log)
    if (errorOf(log)) run.failed = true
    if (log.agent_name === 'escalation' || errorOf(log)) run.finished = true
  }
  return runs
}

/**
 * The run to show for a ticket. While agents are running and the newest logged run is
 * already finished, the new run hasn't written its first log yet: show an empty run.
 */
export function currentRun(ticket: Pick<TicketDetailResponse, 'status' | 'agent_logs'>): Run {
  const runs = groupRuns(ticket.agent_logs)
  const last = runs[runs.length - 1]
  const running = ticket.status === 'new' || ticket.status === 'in_progress'
  if (!last || (running && last.finished)) {
    return { number: runs.length + 1, logs: [], finished: false, failed: false }
  }
  return last
}

/** The steps a run goes through: Order Lookup only runs when the ticket links an order. */
export function expectedSteps(hasOrder: boolean): AgentName[] {
  return hasOrder
    ? ['triage', 'knowledge', 'order_lookup', 'draft', 'escalation']
    : ['triage', 'knowledge', 'draft', 'escalation']
}

export const logFor = (run: Run, agent: AgentName) => run.logs.find((l) => l.agent_name === agent)

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null

export function triageOutput(log?: AgentLogResponse) {
  const out = log?.output
  return {
    category: isObject(out?.category) ? (out.category as unknown as CategoryPrediction) : null,
    urgency: isObject(out?.urgency) ? (out.urgency as unknown as UrgencyPrediction) : null,
  }
}

export function retrievedHits(log?: AgentLogResponse): RetrievedHit[] {
  const hits = log?.output.retrieved
  return Array.isArray(hits) ? (hits.filter(isObject) as unknown as RetrievedHit[]) : []
}

export function orderLookupOutput(log?: AgentLogResponse): OrderLookupResult | null {
  const result = log?.output.result
  return isObject(result) ? (result as unknown as OrderLookupResult) : null
}

export interface DraftOutput {
  draft_text?: string
  mode?: string
  model?: string
  usage?: Record<string, number>
}

export const draftOutput = (log?: AgentLogResponse): DraftOutput => (log?.output ?? {}) as DraftOutput

export function escalationOutput(log?: AgentLogResponse): { decision: EscalationDecision | null; rules: string[] } {
  const out = log?.output
  return {
    decision: isObject(out?.decision) ? (out.decision as unknown as EscalationDecision) : null,
    rules: Array.isArray(out?.rules_fired) ? (out.rules_fired as string[]) : [],
  }
}
