/**
 * TypeScript mirrors of the backend's Pydantic schemas (backend/app/schemas/) and enums
 * (backend/app/core/enums.py). Keep them in step with the backend: one interface per
 * schema, same field names, same nullability.
 *
 * JSON mapping: UUID -> string, datetime -> ISO 8601 string, date -> "YYYY-MM-DD",
 * Decimal -> string (money is never sent as a float).
 */

export type UUID = string
export type ISODateTime = string
export type ISODate = string
export type DecimalString = string

// --- Enums (app/core/enums.py) ---

export const TICKET_CATEGORIES = [
  'order_status',
  'refund_request',
  'damaged_item',
  'delivery_delay',
  'product_question',
  'cancellation',
] as const
export type TicketCategory = (typeof TICKET_CATEGORIES)[number]

export const TICKET_URGENCIES = ['low', 'medium', 'high'] as const
export type TicketUrgency = (typeof TICKET_URGENCIES)[number]

export const TICKET_STATUSES = ['new', 'in_progress', 'awaiting_review', 'resolved'] as const
export type TicketStatus = (typeof TICKET_STATUSES)[number]

export type OrderStatus = 'processing' | 'shipped' | 'delivered' | 'delayed' | 'cancelled'

export const AGENT_NAMES = ['triage', 'knowledge', 'order_lookup', 'draft', 'escalation'] as const
export type AgentName = (typeof AGENT_NAMES)[number]

// --- Customers (app/schemas/customer.py) ---

export interface CustomerResponse {
  id: UUID
  name: string
  email: string
}

// --- Orders (app/schemas/order.py) ---

export interface OrderResponse {
  id: UUID
  customer_id: UUID
  item_name: string
  status: OrderStatus
  tracking_number: string | null
  amount: DecimalString
  order_date: ISODate
  expected_delivery: ISODate | null
}

// --- Tickets (app/schemas/ticket.py) ---

export interface TicketCreate {
  customer_id: UUID
  subject: string
  body: string
  order_id?: UUID | null
}

export interface TicketResponse {
  id: UUID
  customer_id: UUID
  order_id: UUID | null
  subject: string
  body: string
  category: TicketCategory | null
  urgency: TicketUrgency | null
  status: TicketStatus
  needs_escalation: boolean | null
  escalation_reason: string | null
  // A reviewer's correction of the triage; null = no correction (the model's label stands)
  corrected_category: TicketCategory | null
  corrected_urgency: TicketUrgency | null
  corrected_by: string | null
  corrected_at: ISODateTime | null
  created_at: ISODateTime
  updated_at: ISODateTime
}

export interface AgentLogResponse {
  id: UUID
  agent_name: AgentName
  input: Record<string, unknown>
  output: Record<string, unknown>
  tool_calls: unknown[] | null
  duration_ms: number | null
  created_at: ISODateTime
}

export interface DraftResponseRead {
  id: UUID
  draft_text: string
  approved: boolean | null
  edited_text: string | null
  reviewer_id: string | null
  reviewed_at: ISODateTime | null
  created_at: ISODateTime
}

export interface TicketDetailResponse extends TicketResponse {
  order: OrderResponse | null
  draft_responses: DraftResponseRead[]
  agent_logs: AgentLogResponse[]
}

// --- Reviews (app/schemas/review.py) ---

export interface ReviewApproveRequest {
  reviewer_id: string
}

export interface ReviewEditRequest {
  edited_text: string
  reviewer_id: string
}

export interface TriageCorrectionRequest {
  corrected_category?: TicketCategory | null
  corrected_urgency?: TicketUrgency | null
  reviewer_id: string
}

// --- Knowledge base (app/schemas/knowledge_base.py) ---

export interface KnowledgeBaseResponse {
  id: UUID
  title: string
  content: string
  created_at: ISODateTime
}

export interface RetrievedDoc {
  id: string
  title: string
  content: string
  similarity: number
}

// --- Agent tool schemas (app/schemas/prediction.py, app/schemas/agents.py) ---

export interface CategoryPrediction {
  label: TicketCategory
  confidence: number
  model_version: string
}

export interface UrgencyPrediction {
  label: TicketUrgency
  confidence: number
  model_version: string
}

export interface OrderLookupResult {
  order_id: string
  status: string
  tracking_number: string | null
  amount: number
  expected_delivery: string | null
  item_name: string
  order_date: string
}

export interface EscalationDecision {
  needs_escalation: boolean
  reason: string | null
}

// --- Metrics (app/schemas/metrics.py) ---

export interface CategoryCount {
  category: TicketCategory
  count: number
}

export interface DailyEscalation {
  date: ISODate
  processed: number
  escalated: number
  rate: number | null
}

export interface ReviewOutcome {
  outcome: 'approved_as_is' | 'edited'
  escalated: number
  not_escalated: number
}

export interface CategoryResolution {
  category: TicketCategory
  resolved: number
  avg_resolution_seconds: number | null
}

export interface MetricsSummary {
  total_tickets: number
  tickets_by_status: Record<TicketStatus, number>
  tickets_by_category: CategoryCount[]
  escalation_rate: number | null
  escalation_by_day: DailyEscalation[]
  drafts_reviewed: number
  approval_rate: number | null
  review_outcomes: ReviewOutcome[]
  avg_resolution_seconds: number | null
  resolution_by_category: CategoryResolution[]
}

// --- FastAPI errors ---

export interface ValidationErrorItem {
  loc: (string | number)[]
  msg: string
  type: string
}

export interface ErrorResponse {
  detail: string | ValidationErrorItem[]
}
