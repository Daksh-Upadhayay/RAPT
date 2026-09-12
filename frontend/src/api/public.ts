import type { ContactFormInfo, ContactReceipt, ContactRequest, TenantSettings, TenantSettingsUpdate } from '../types'
import { request } from './client'

export const contactKeys = { form: (slug: string) => ['contact', slug] as const }
export const settingsKeys = { all: ['settings'] as const }

export const getContactForm = (slug: string) => request<ContactFormInfo>(`/public/contact/${encodeURIComponent(slug)}`)

export const sendContactMessage = (slug: string, data: ContactRequest) =>
  request<ContactReceipt>(`/public/contact/${encodeURIComponent(slug)}`, { method: 'POST', body: data })

export const getSettings = () => request<TenantSettings>('/settings')

export const updateSettings = (data: TenantSettingsUpdate) => request<TenantSettings>('/settings', { method: 'PATCH', body: data })
