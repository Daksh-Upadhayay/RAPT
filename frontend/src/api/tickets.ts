import type {
  AgentLogResponse,
  TicketCategory,
  TicketCreate,
  TicketDetailResponse,
  TicketResponse,
  TicketStatus,
  TicketUrgency,
} from '../types'
import { request } from './client'

export interface TicketFilters {
  status?: TicketStatus
  category?: TicketCategory
  urgency?: TicketUrgency
}

export const ticketKeys = {
  all: ['tickets'] as const,
  list: (filters: TicketFilters) => ['tickets', 'list', filters] as const,
  detail: (id: string) => ['tickets', 'detail', id] as const,
  trace: (id: string) => ['tickets', 'trace', id] as const,
}

export const createTicket = (data: TicketCreate) =>
  request<TicketResponse>('/tickets', { method: 'POST', body: data })

export const listTickets = (filters: TicketFilters = {}) =>
  request<TicketResponse[]>('/tickets', { query: { ...filters } })

export const getTicket = (id: string) => request<TicketDetailResponse>(`/tickets/${id}`)

export const getAgentTrace = (id: string) => request<AgentLogResponse[]>(`/tickets/${id}/agent-trace`)

export const rerunAgents = (id: string) => request<TicketResponse>(`/tickets/${id}/rerun`, { method: 'POST' })
