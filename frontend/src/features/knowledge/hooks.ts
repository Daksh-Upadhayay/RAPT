import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteDocument,
  deleteSection,
  getDocument,
  knowledgeKeys,
  listDocuments,
  pasteDocument,
  searchKnowledge,
  updateSection,
  uploadDocuments,
} from '../../api/knowledge'
import type { KnowledgeBaseUpdate, KnowledgePasteRequest } from '../../types'

/** The tenant's documents; polls while any is still being split and embedded. */
export function useDocuments() {
  return useQuery({
    queryKey: knowledgeKeys.documents,
    queryFn: listDocuments,
    refetchInterval: (q) => (q.state.data?.some((d) => d.status === 'processing') ? 1500 : false),
  })
}

export function useDocument(id: string, enabled: boolean) {
  return useQuery({ queryKey: knowledgeKeys.document(id), queryFn: () => getDocument(id), enabled })
}

function useRefreshKnowledge() {
  const queryClient = useQueryClient()
  return () => void queryClient.invalidateQueries({ queryKey: knowledgeKeys.all })
}

export function useUpload() {
  const refresh = useRefreshKnowledge()
  return useMutation({ mutationFn: (files: File[]) => uploadDocuments(files), onSuccess: refresh })
}

export function usePaste() {
  const refresh = useRefreshKnowledge()
  return useMutation({ mutationFn: (data: KnowledgePasteRequest) => pasteDocument(data), onSuccess: refresh })
}

export function useDeleteDocument() {
  const refresh = useRefreshKnowledge()
  return useMutation({ mutationFn: (id: string) => deleteDocument(id), onSuccess: refresh })
}

export function useUpdateSection() {
  const refresh = useRefreshKnowledge()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: KnowledgeBaseUpdate }) => updateSection(id, data), onSuccess: refresh })
}

export function useDeleteSection() {
  const refresh = useRefreshKnowledge()
  return useMutation({ mutationFn: (id: string) => deleteSection(id), onSuccess: refresh })
}

export function useSearchPreview() {
  return useMutation({ mutationFn: (query: string) => searchKnowledge({ query, k: 3 }) })
}
