import type { ReactNode } from 'react'

/**
 * A sheet of label stock: the one container in the app. White on the grey ground, thin
 * border, no shadow. An optional header names what's on it.
 */
export function Sheet({ title, aside, children, className = '', padded = true, as: Tag = 'section' }: {
  title?: ReactNode
  aside?: ReactNode
  children: ReactNode
  className?: string
  padded?: boolean
  as?: 'section' | 'div' | 'article' | 'aside'
}) {
  return (
    <Tag className={`rounded-label border border-line bg-paper ${className}`}>
      {(title || aside) && (
        <header className="flex min-h-12 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line px-5 py-2.5">
          {title && <h2 className="type-heading text-small">{title}</h2>}
          {aside && <div className="text-tiny text-ink-3">{aside}</div>}
        </header>
      )}
      <div className={padded ? 'p-5' : ''}>{children}</div>
    </Tag>
  )
}
