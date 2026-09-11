import { useQuery } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router'
import { getReviewQueue, reviewKeys } from '../api/reviews'
import { useReviewer } from '../lib/reviewerContext'

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
          isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
        }`
      }
    >
      {children}
    </NavLink>
  )
}

function QueueCount() {
  // Shares the review queue's cache; keeps the nav count fresh on every page
  const { data } = useQuery({ queryKey: reviewKeys.queue, queryFn: getReviewQueue, refetchInterval: 5000 })
  if (!data?.length) return null
  return (
    <span className="rounded-full bg-amber-400 px-1.5 text-xs font-semibold text-amber-950 tabular-nums">
      {data.length}
    </span>
  )
}

function ReviewerField() {
  const { reviewerId, setReviewerId } = useReviewer()
  return (
    <label className="ml-auto flex items-center gap-2 text-xs text-slate-500 sm:ml-0">
      <span className="hidden sm:inline">Reviewing as</span>
      <input
        value={reviewerId}
        onChange={(e) => setReviewerId(e.target.value)}
        onBlur={(e) => !e.target.value.trim() && setReviewerId('reviewer')}
        className="w-28 rounded-md border border-slate-200 bg-white px-2 py-1 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
        aria-label="Reviewer name"
      />
    </label>
  )
}

export function Layout() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <NavLink to="/reviews" className="flex items-center gap-2 font-semibold text-slate-900">
            <img src="/favicon.svg" alt="" className="size-6" />
            RAPT <span className="hidden font-normal text-slate-500 sm:inline">Support Copilot</span>
          </NavLink>
          {/* Below sm the nav takes its own full-width row after the reviewer field */}
          <nav className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto whitespace-nowrap sm:order-none sm:mx-0 sm:w-auto sm:flex-1">
            <NavItem to="/reviews">
              Review queue <QueueCount />
            </NavItem>
            <NavItem to="/submit">Submit ticket</NavItem>
            <NavItem to="/dashboard">Dashboard</NavItem>
          </nav>
          <ReviewerField />
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
