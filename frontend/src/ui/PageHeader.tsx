import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowLeftIcon } from './icons'

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="mb-4 inline-flex items-center gap-1.5 text-small font-medium text-ink-2 hover:text-ink">
      <ArrowLeftIcon className="size-4" />
      {children}
    </Link>
  )
}

/** Page title in the label face, a one-line explanation, and the page's actions. */
export function PageHeader({ title, intro, back, actions }: {
  title: ReactNode
  intro?: ReactNode
  back?: { to: string; label: string }
  actions?: ReactNode
}) {
  return (
    <header className="mb-8">
      {back && <BackLink to={back.to}>{back.label}</BackLink>}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 max-w-2xl">
          <h1 className="type-label text-display">{title}</h1>
          {intro && <p className="mt-2 text-body text-ink-2">{intro}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  )
}
