import type {
  ReviewApproveRequest,
  ReviewEditRequest,
  TicketDetailResponse,
  TicketResponse,
  TriageCorrectionRequest,
} from '../types'
import { request } from './client'

export const reviewKeys = {
  queue: ['reviews', 'queue'] as const,
}

export const getReviewQueue = () => request<TicketResponse[]>('/reviews/queue')

export const approveDraft = (ticketId: string, data: ReviewApproveRequest) =>
  request<TicketDetailResponse>(`/reviews/${ticketId}/approve`, { method: 'POST', body: data })

export const editAndApproveDraft = (ticketId: string, data: ReviewEditRequest) =>
  request<TicketDetailResponse>(`/reviews/${ticketId}/edit`, { method: 'POST', body: data })

/** Replaces any earlier correction; a value equal to the model's label is stored as no correction. */
export const correctTriage = (ticketId: string, data: TriageCorrectionRequest) =>
  request<TicketDetailResponse>(`/reviews/${ticketId}/triage`, { method: 'PUT', body: data })
