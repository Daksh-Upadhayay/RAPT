import { createContext, useContext } from 'react'

export interface ReviewerContextValue {
  reviewerId: string
  setReviewerId: (id: string) => void
}

export const ReviewerContext = createContext<ReviewerContextValue | null>(null)

export function useReviewer(): ReviewerContextValue {
  const value = useContext(ReviewerContext)
  if (!value) throw new Error('useReviewer must be used inside <ReviewerProvider>')
  return value
}
