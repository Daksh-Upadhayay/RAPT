import { lazy, Suspense } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import { EmptyState, Loading } from './components/ui'
import { AgentTrace } from './pages/AgentTrace'
import { ReviewQueue } from './pages/ReviewQueue'
import { SubmitTicket } from './pages/SubmitTicket'
import { TicketDetail } from './pages/TicketDetail'

// Recharts is most of the bundle: load it only when the dashboard is opened
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })))

function NotFound() {
  return (
    <EmptyState title="Page not found">
      <Link to="/reviews" className="font-medium text-indigo-600 hover:underline">
        Go to the review queue
      </Link>
    </EmptyState>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/reviews" replace />} />
        <Route path="reviews" element={<ReviewQueue />} />
        <Route path="submit" element={<SubmitTicket />} />
        <Route path="tickets/:id" element={<TicketDetail />} />
        <Route path="tickets/:id/trace" element={<AgentTrace />} />
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
    </Routes>
  )
}
