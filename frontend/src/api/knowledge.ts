import type {
  KnowledgeBaseResponse,
  KnowledgeBaseUpdate,
  KnowledgeDocumentDetail,
  KnowledgeDocumentResponse,
  KnowledgePasteRequest,
  KnowledgeSearchRequest,
  KnowledgeUploadResult,
  RetrievedDoc,
} from '../types'
import { request } from './client'

export const knowledgeKeys = {
  all: ['knowledge'] as const,
  documents: ['knowledge', 'documents'] as const,
  document: (id: string) => ['knowledge', 'documents', id] as const,
}

export const listDocuments = () => request<KnowledgeDocumentResponse[]>('/knowledge-base/documents')

export const getDocument = (id: string) => request<KnowledgeDocumentDetail>(`/knowledge-base/documents/${id}`)

export function uploadDocuments(files: File[]) {
  const form = new FormData()
  for (const file of files) form.append('files', file)
  return request<KnowledgeUploadResult[]>('/knowledge-base/documents/upload', { method: 'POST', body: form })
}

export const pasteDocument = (data: KnowledgePasteRequest) =>
  request<KnowledgeDocumentResponse>('/knowledge-base/documents/paste', { method: 'POST', body: data })

export const deleteDocument = (id: string) => request<null>(`/knowledge-base/documents/${id}`, { method: 'DELETE' })

export const updateSection = (id: string, data: KnowledgeBaseUpdate) =>
  request<KnowledgeBaseResponse>(`/knowledge-base/${id}`, { method: 'PATCH', body: data })

export const deleteSection = (id: string) => request<null>(`/knowledge-base/${id}`, { method: 'DELETE' })

export const searchKnowledge = (data: KnowledgeSearchRequest) =>
  request<RetrievedDoc[]>('/knowledge-base/search', { method: 'POST', body: data })
