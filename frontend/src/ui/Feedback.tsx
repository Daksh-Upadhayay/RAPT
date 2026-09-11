import type { ReactNode } from 'react'
import { ApiError } from '../api/client'
import { Spinner } from './icons'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-16 text-small text-ink-2" role="status">
      <Spinner />
      {label}
    </div>
  )
}

/** Says what went wrong in the interface's voice, with a way to retry. */
export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof ApiError || error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div role="alert" className="flex items-start justify-between gap-4 rounded-label border border-danger/40 bg-danger-wash px-4 py-3 text-small text-danger-ink">
      <span>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="shrink-0 font-semibold underline underline-offset-2">
          Try again
        </button>
      )}
    </div>
  )
}

/** An empty screen is an invitation to act: say what goes here and how to get it. */
export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-label border border-dashed border-ink/30 px-6 py-14 text-center">
      <p className="type-heading text-heading">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-small text-ink-2">{children}</div>}
    </div>
  )
}
