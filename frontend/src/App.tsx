import { lazy, Suspense } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router'
import { AppShell } from './app/AppShell'
import { RequireSession } from './features/auth'
import { EmptyState, Loading } from './ui'
import { AgentTrace } from './pages/AgentTrace'
import { Knowledge } from './pages/Knowledge'
import { Login } from './pages/Login'
import { ReviewQueue } from './pages/ReviewQueue'
import { SubmitTicket } from './pages/SubmitTicket'
import { Team } from './pages/Team'
import { TicketDetail } from './pages/TicketDetail'

// Recharts is most of the bundle: load it only when the dashboard is opened
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })))

function NotFound() {
  return (
    <EmptyState title="There’s no page here">
      <Link to="/reviews" className="font-semibold text-ink underline underline-offset-2">
        Go to the review queue
      </Link>
    </EmptyState>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      {/* Everything else needs a session */}
      <Route element={<RequireSession />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/reviews" replace />} />
          <Route path="reviews" element={<ReviewQueue />} />
          <Route path="submit" element={<SubmitTicket />} />
          <Route path="tickets/:id" element={<TicketDetail />} />
          <Route path="tickets/:id/trace" element={<AgentTrace />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="team" element={<Team />} />
          <Route
            path="dashboard"
            element={
              <Suspense fallback={<Loading label="Loading dashboard…" />}>
                <Dashboard />
              </Suspense>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  )
}
