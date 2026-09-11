import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router'
import { useReviewQueue } from '../features/review'
import { ReviewerField } from '../features/reviewer'

function QueueCount() {
  // Shares the review queue's cache, so the count stays fresh on every page
  const { data } = useReviewQueue()
  if (!data?.length) return null
  return (
    <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1.5 text-tiny font-bold text-ink tabular-nums">
      {data.length}
      <span className="sr-only"> awaiting review</span>
    </span>
  )
}

function NavItem({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `relative inline-flex h-14 items-center px-1 text-small font-semibold whitespace-nowrap transition-colors ${
          isActive ? 'text-ink after:absolute after:inset-x-0 after:bottom-0 after:h-1 after:bg-accent' : 'text-ink-2 hover:text-ink'
        }`
      }
    >
      {children}
    </NavLink>
  )
}

/** The frame around every page: wordmark, the three places, and who is reviewing. */
export function AppShell() {
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:bg-paper focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-10 border-b-2 border-ink bg-paper">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 px-4 sm:px-6">
          <NavLink to="/reviews" className="type-label flex h-14 items-center text-heading">
            RAPT
          </NavLink>
          <nav aria-label="Main" className="order-last -mx-1 flex w-full gap-6 overflow-x-auto px-1 sm:order-none sm:mx-0 sm:w-auto sm:flex-1 sm:px-0">
            <NavItem to="/reviews">
              Review queue
              <QueueCount />
            </NavItem>
            <NavItem to="/submit">Submit a ticket</NavItem>
            <NavItem to="/dashboard">Dashboard</NavItem>
          </nav>
          <div className="ml-auto flex h-14 items-center sm:ml-0">
            <ReviewerField />
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
