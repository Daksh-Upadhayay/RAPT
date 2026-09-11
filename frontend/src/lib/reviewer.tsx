import { useState, type ReactNode } from 'react'
import { ReviewerContext } from './reviewerContext'

/** Placeholder reviewer identity (there is no auth yet), remembered in this browser. */
const STORAGE_KEY = 'rapt.reviewerId'
const DEFAULT_REVIEWER = 'reviewer'

function stored(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_REVIEWER
  } catch {
    return DEFAULT_REVIEWER
  }
}

export function ReviewerProvider({ children }: { children: ReactNode }) {
  const [reviewerId, setState] = useState(stored)
  const setReviewerId = (id: string) => {
    setState(id)
    try {
      localStorage.setItem(STORAGE_KEY, id)
    } catch {
      // storage unavailable (private mode): keep it for this session only
    }
  }
  return <ReviewerContext value={{ reviewerId, setReviewerId }}>{children}</ReviewerContext>
}
