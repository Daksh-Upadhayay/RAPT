import type { ReviewApproveRequest, ReviewEditRequest, TicketDetailResponse, TicketResponse } from '../types'
import { request } from './client'

export const reviewKeys = {
  queue: ['reviews', 'queue'] as const,
}

export const getReviewQueue = () => request<TicketResponse[]>('/reviews/queue')

export const approveDraft = (ticketId: string, data: ReviewApproveRequest) =>
  request<TicketDetailResponse>(`/reviews/${ticketId}/approve`, { method: 'POST', body: data })

export const editAndApproveDraft = (ticketId: string, data: ReviewEditRequest) =>
  request<TicketDetailResponse>(`/reviews/${ticketId}/edit`, { method: 'POST', body: data })
