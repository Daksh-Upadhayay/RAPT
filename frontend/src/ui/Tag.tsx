import type { ReactNode } from 'react'

export type TagTone = 'neutral' | 'accent' | 'danger' | 'ok' | 'muted'

const TONES: Record<TagTone, string> = {
  neutral: 'border-line bg-paper text-ink',
  accent: 'border-accent-deep bg-accent-wash text-ink',
  danger: 'border-danger/40 bg-danger-wash text-danger-ink',
  ok: 'border-ok/30 bg-ok-wash text-ok',
  muted: 'border-line bg-sunken text-ink-3',
}

/** A small printed sticker: a label with an optional leading key (icon, colour square). */
export function Tag({ tone = 'neutral', icon, title, children }: { tone?: TagTone; icon?: ReactNode; title?: string; children: ReactNode }) {
  return (
    <span
      title={title}
      className={`inline-flex h-6 items-center gap-1.5 rounded-label border px-2 text-tiny font-semibold whitespace-nowrap ${TONES[tone]}`}
    >
      {icon}
      {children}
    </span>
  )
}
