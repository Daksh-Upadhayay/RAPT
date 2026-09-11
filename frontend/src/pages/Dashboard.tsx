import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getMetricsSummary, metricsKeys } from '../api/metrics'
import { MetricChart, StatTile, TooltipBox } from '../components/MetricChart'
import { CHART } from '../lib/chart'
import { ErrorMessage, Loading, PageHeader } from '../components/ui'
import { CATEGORY_COLORS, CATEGORY_LABELS, calendarDate, duration, percent } from '../lib/format'
import type { MetricsSummary } from '../types'

const RANGES = [7, 30, 90] as const
const axisTick = { fill: CHART.muted, fontSize: 12 }

function CategoryChart({ data }: { data: MetricsSummary['tickets_by_category'] }) {
  const rows = data.map((d) => ({ ...d, label: CATEGORY_LABELS[d.category] }))
  const total = rows.reduce((s, r) => s + r.count, 0)
  return (
    <MetricChart
      title="Tickets by category"
      subtitle="As classified by the Triage Agent"
      table={{ columns: ['Category', 'Tickets'], rows: rows.map((r) => [r.label, r.count]) }}
      empty={total === 0 ? 'No classified tickets yet' : null}
    >
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 32 }}>
          <CartesianGrid horizontal={false} stroke={CHART.grid} />
          <XAxis type="number" allowDecimals={false} tick={axisTick} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="label" width={120} tick={{ ...axisTick, fill: CHART.secondary }} axisLine={{ stroke: CHART.axis }} tickLine={false} />
          <Tooltip
            cursor={{ fill: '#f1f5f9' }}
            content={({ active, payload }) =>
              active && payload?.[0] ? (
                <TooltipBox title={payload[0].payload.label} rows={[{ label: 'tickets', value: String(payload[0].payload.count) }]} />
              ) : null
            }
          />
          <Bar dataKey="count" barSize={20} radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.category} fill={CATEGORY_COLORS[r.category]} />
            ))}
            <LabelList dataKey="count" position="right" fill={CHART.secondary} fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </MetricChart>
  )
}

function EscalationChart({ data, days, setDays }: {
  data: MetricsSummary['escalation_by_day']
  days: number
  setDays: (d: number) => void
}) {
  const rows = data.map((d) => ({ ...d, label: calendarDate(d.date, { month: 'short', day: 'numeric' }) }))
  const any = rows.some((r) => r.processed > 0)
  return (
    <MetricChart
      title="Escalation rate over time"
      subtitle="Share of each day's tickets the Escalation Agent flagged (UTC days)"
      table={{
        columns: ['Day', 'Processed', 'Escalated', 'Rate'],
        rows: rows.filter((r) => r.processed > 0).map((r) => [r.label, r.processed, r.escalated, percent(r.rate)]),
      }}
      empty={any ? null : `No processed tickets in the last ${days} days`}
      action={
        <div className="inline-flex rounded-md border border-slate-200 p-0.5" role="group" aria-label="Range">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={r === days}
              onClick={() => setDays(r)}
              className={`rounded px-2 py-0.5 text-xs ${r === days ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
            >
              {r}d
            </button>
          ))}
        </div>
      }
    >
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 8, right: 16, left: -8 }}>
          <CartesianGrid vertical={false} stroke={CHART.grid} />
          <XAxis dataKey="label" tick={axisTick} axisLine={{ stroke: CHART.axis }} tickLine={false} minTickGap={24} />
          <YAxis domain={[0, 1]} tickFormatter={(v: number) => percent(v)} tick={axisTick} axisLine={false} tickLine={false} width={48} />
          <Tooltip
            cursor={{ stroke: CHART.axis }}
            content={({ active, payload }) => {
              const row = payload?.[0]?.payload as (typeof rows)[number] | undefined
              return active && row ? (
                <TooltipBox
                  title={row.label}
                  rows={[
                    { label: 'escalated', value: percent(row.rate), color: CHART.series1 },
                    { label: 'flagged / processed', value: `${row.escalated} / ${row.processed}` },
                  ]}
                />
              ) : null
            }}
          />
          <Line
            type="monotone"
            dataKey="rate"
            stroke={CHART.series1}
            strokeWidth={2}
            dot={{ r: 4, fill: CHART.series1, stroke: CHART.surface, strokeWidth: 2 }}
            activeDot={{ r: 5, stroke: CHART.surface, strokeWidth: 2 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </MetricChart>
  )
}

function OutcomeChart({ summary }: { summary: MetricsSummary }) {
  const rows = summary.review_outcomes.map((o) => ({
    ...o,
    label: o.outcome === 'approved_as_is' ? 'Approved as-is' : 'Edited',
    total: o.escalated + o.not_escalated,
  }))
  return (
    <MetricChart
      title="Draft approval"
      subtitle={`Reviewed drafts, split by escalation · ${percent(summary.approval_rate)} approved as-is`}
      legend={[
        { label: 'Not escalated', color: CHART.series1 },
        { label: 'Escalated', color: CHART.series2 },
      ]}
      table={{
        columns: ['Outcome', 'Not escalated', 'Escalated', 'Total'],
        rows: rows.map((r) => [r.label, r.not_escalated, r.escalated, r.total]),
      }}
      empty={summary.drafts_reviewed === 0 ? 'No drafts reviewed yet' : null}
    >
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 32 }}>
          <CartesianGrid horizontal={false} stroke={CHART.grid} />
          <XAxis type="number" allowDecimals={false} tick={axisTick} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="label" width={110} tick={{ ...axisTick, fill: CHART.secondary }} axisLine={{ stroke: CHART.axis }} tickLine={false} />
          <Tooltip
            cursor={{ fill: '#f1f5f9' }}
            content={({ active, payload }) => {
              const row = payload?.[0]?.payload as (typeof rows)[number] | undefined
              return active && row ? (
                <TooltipBox
                  title={row.label}
                  rows={[
                    { label: 'not escalated', value: String(row.not_escalated), color: CHART.series1 },
                    { label: 'escalated', value: String(row.escalated), color: CHART.series2 },
                  ]}
                />
              ) : null
            }}
          />
          {/* The white stroke is the 2px gap between stacked segments */}
          <Bar dataKey="not_escalated" name="Not escalated" stackId="a" fill={CHART.series1} stroke={CHART.surface} strokeWidth={2} barSize={22} isAnimationActive={false} />
          <Bar dataKey="escalated" name="Escalated" stackId="a" fill={CHART.series2} stroke={CHART.surface} strokeWidth={2} barSize={22} radius={[0, 4, 4, 0]} isAnimationActive={false}>
            <LabelList dataKey="total" position="right" fill={CHART.secondary} fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </MetricChart>
  )
}

/** Axis unit that keeps tick labels readable for the largest value. */
function timeUnit(maxSeconds: number): { divisor: number; suffix: string } {
  if (maxSeconds < 120) return { divisor: 1, suffix: 's' }
  if (maxSeconds < 7200) return { divisor: 60, suffix: 'min' }
  if (maxSeconds < 172_800) return { divisor: 3600, suffix: 'h' }
  return { divisor: 86_400, suffix: 'd' }
}

function ResolutionChart({ data }: { data: MetricsSummary['resolution_by_category'] }) {
  const unit = timeUnit(Math.max(0, ...data.map((d) => d.avg_resolution_seconds ?? 0)))
  const rows = data.map((d) => ({
    ...d,
    label: CATEGORY_LABELS[d.category],
    value: d.avg_resolution_seconds === null ? null : d.avg_resolution_seconds / unit.divisor,
    text: duration(d.avg_resolution_seconds),
  }))
  const resolved = rows.reduce((s, r) => s + r.resolved, 0)
  return (
    <MetricChart
      title="Average resolution time by category"
      subtitle="From ticket submitted to reply approved"
      table={{ columns: ['Category', 'Resolved', 'Average'], rows: rows.map((r) => [r.label, r.resolved, r.text]) }}
      empty={resolved === 0 ? 'No tickets resolved yet' : null}
    >
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 48 }}>
          <CartesianGrid horizontal={false} stroke={CHART.grid} />
          <XAxis type="number" tickFormatter={(v: number) => `${Number(v.toFixed(1))} ${unit.suffix}`} tick={axisTick} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="label" width={120} tick={{ ...axisTick, fill: CHART.secondary }} axisLine={{ stroke: CHART.axis }} tickLine={false} />
          <Tooltip
            cursor={{ fill: '#f1f5f9' }}
            content={({ active, payload }) => {
              const row = payload?.[0]?.payload as (typeof rows)[number] | undefined
              return active && row ? (
                <TooltipBox title={row.label} rows={[{ label: `average over ${row.resolved} resolved`, value: row.text }]} />
              ) : null
            }}
          />
          <Bar dataKey="value" barSize={20} radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.category} fill={CATEGORY_COLORS[r.category]} />
            ))}
            <LabelList dataKey="text" position="right" fill={CHART.secondary} fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </MetricChart>
  )
}

export function Dashboard() {
  const [days, setDays] = useState(30)
  const query = useQuery({
    queryKey: metricsKeys.summary(days),
    queryFn: () => getMetricsSummary(days),
    refetchInterval: 10_000,
    placeholderData: keepPreviousData, // keep the frame while a new range loads
  })

  if (query.isPending) return <Loading label="Loading metrics…" />
  if (query.isError) return <ErrorMessage error={query.error} onRetry={() => void query.refetch()} />

  const s = query.data
  const reviewed = s.drafts_reviewed
  return (
    <div className={query.isPlaceholderData ? 'opacity-60 transition-opacity' : 'transition-opacity'}>
      <PageHeader title="Dashboard" subtitle="All tickets to date; updates every 10 seconds." />
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatTile label="Tickets" value={s.total_tickets.toLocaleString()} detail={`${s.tickets_by_status.resolved} resolved`} />
        <StatTile label="Awaiting review" value={s.tickets_by_status.awaiting_review.toLocaleString()} detail={`${s.tickets_by_status.in_progress + s.tickets_by_status.new} with the agents`} />
        <StatTile label="Escalation rate" value={percent(s.escalation_rate)} detail="of tickets the agents finished" />
        <StatTile label="Approved as-is" value={percent(s.approval_rate)} detail={`of ${reviewed} reviewed ${reviewed === 1 ? 'draft' : 'drafts'}`} />
        <StatTile label="Avg resolution" value={duration(s.avg_resolution_seconds)} detail="submitted to approved" />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <CategoryChart data={s.tickets_by_category} />
        <EscalationChart data={s.escalation_by_day} days={days} setDays={setDays} />
        <OutcomeChart summary={s} />
        <ResolutionChart data={s.resolution_by_category} />
      </div>
    </div>
  )
}
