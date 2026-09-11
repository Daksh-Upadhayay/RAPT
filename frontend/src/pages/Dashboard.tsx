import { MetricsOverview } from '../features/metrics'
import { PageHeader } from '../ui'

export function Dashboard() {
  return (
    <>
      <PageHeader title="Dashboard" intro="How the agents and reviewers are doing, across every ticket so far." />
      <MetricsOverview />
    </>
  )
}
