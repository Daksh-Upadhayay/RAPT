import type { InviteRequest, MemberUpdate, PasswordIssued, TeamMember } from '../types'
import { request } from './client'

export const teamKeys = { all: ['team'] as const }

export const listTeam = () => request<TeamMember[]>('/team')

export const inviteMember = (data: InviteRequest) => request<PasswordIssued>('/team', { method: 'POST', body: data })

export const updateMember = (id: string, data: MemberUpdate) => request<TeamMember>(`/team/${id}`, { method: 'PATCH', body: data })

export const resetMemberPassword = (id: string) => request<PasswordIssued>(`/team/${id}/reset-password`, { method: 'POST' })
