import type { AgentName, OrderStatus, TicketCategory, TicketStatus, TicketUrgency } from '../types'

export const CATEGORY_LABELS: Record<TicketCategory, string> = {
  order_status: 'Order status',
  refund_request: 'Refund request',
  damaged_item: 'Damaged item',
  delivery_delay: 'Delivery delay',
  product_question: 'Product question',
  cancellation: 'Cancellation',
}

/**
 * One fixed colour per category, used everywhere (badges and charts), so a reviewer
 * learns them once. Categorical slots 1-6 in fixed order, validated for colour-blind
 * separation. Colours mark identity only; text stays in ink colours.
 */
export const CATEGORY_COLORS: Record<TicketCategory, string> = {
  order_status: '#2a78d6',
  refund_request: '#eb6834',
  damaged_item: '#1baf7a',
  delivery_delay: '#eda100',
  product_question: '#e87ba4',
  cancellation: '#008300',
}

export const URGENCY_LABELS: Record<TicketUrgency, string> = { low: 'Low', medium: 'Medium', high: 'High' }

export const STATUS_LABELS: Record<TicketStatus, string> = {
  new: 'New',
  in_progress: 'Agents running',
  awaiting_review: 'Awaiting review',
  resolved: 'Resolved',
}

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  processing: 'Processing',
  shipped: 'Shipped',
  delivered: 'Delivered',
  delayed: 'Delayed',
  cancelled: 'Cancelled',
}

export const AGENT_LABELS: Record<AgentName, string> = {
  triage: 'Triage Agent',
  knowledge: 'Knowledge Agent',
  order_lookup: 'Order Lookup Tool',
  draft: 'Draft Agent',
  escalation: 'Escalation Agent',
}

export const AGENT_DESCRIPTIONS: Record<AgentName, string> = {
  triage: 'Classifies category and urgency with the trained models',
  knowledge: 'Finds the closest knowledge-base entries (pgvector)',
  order_lookup: 'Reads the linked order record',
  draft: 'Writes a reply grounded in the knowledge and order data',
  escalation: 'Applies the escalation rules',
}

export const isRunning = (status: TicketStatus) => status === 'new' || status === 'in_progress'

export function percent(value: number | null, digits = 0): string {
  return value === null ? '–' : `${(value * 100).toFixed(digits)}%`
}

export function duration(seconds: number | null): string {
  if (seconds === null) return '–'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const minutes = seconds / 60
  if (minutes < 60) return `${Math.round(minutes)} min`
  const hours = minutes / 60
  if (hours < 48) return `${hours.toFixed(hours < 10 ? 1 : 0)} h`
  return `${(hours / 24).toFixed(1)} days`
}

export function milliseconds(ms: number | null): string {
  if (ms === null) return '–'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export function timeAgo(iso: string, now: number = Date.now()): string {
  const seconds = (new Date(iso).getTime() - now) / 1000
  const abs = Math.abs(seconds)
  if (abs < 45) return 'just now'
  if (abs < 3600) return relative.format(Math.round(seconds / 60), 'minute')
  if (abs < 86400) return relative.format(Math.round(seconds / 3600), 'hour')
  return relative.format(Math.round(seconds / 86400), 'day')
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString('en', { dateStyle: 'medium', timeStyle: 'short' })
}

/** A "YYYY-MM-DD" date as a calendar date (no timezone shift). */
export function calendarDate(isoDate: string, options: Intl.DateTimeFormatOptions = { dateStyle: 'medium' }): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en', options)
}

export function money(amount: string | number): string {
  return new Intl.NumberFormat('en', { style: 'currency', currency: 'USD' }).format(Number(amount))
}
