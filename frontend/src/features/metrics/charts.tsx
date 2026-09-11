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
import { CATEGORY_COLORS, CATEGORY_LABELS, calendarDate, duration, percent } from '../../lib/format'
import type { MetricsSummary } from '../../types'
import { Segmented } from '../../ui'
import { ChartCard, TooltipBox } from './ChartCard'
import { CHART, axisTick, categoryTick } from './chartTheme'

const RANGES = [7, 30, 90] as const

export function CategoryChart({ data }: { data: MetricsSummary['tickets_by_category'] }) {
  const rows = data.map((d) => ({ ...d, label: CATEGORY_LABELS[d.category] }))
  const total = rows.reduce((s, r) => s + r.count, 0)
  return (
    <ChartCard
      title="Tickets by category"
      intro="As classified by the Triage Agent"
      table={{ columns: ['Category', 'Tickets'], rows: rows.map((r) => [r.label, r.count]) }}
      empty={total === 0 ? 'No classified tickets yet' : null}
    >
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 32 }}>
          <CartesianGrid horizontal={false} stroke={CHART.grid} />
          <XAxis type="number" allowDecimals={false} tick={axisTick} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="label" width={120} tick={categoryTick} axisLine={{ stroke: CHART.axis }} tickLine={false} />
          <Tooltip
            cursor={{ fill: CHART.hover }}
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
            <LabelList dataKey="count" position="right" fill={CHART.label} fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

export function EscalationChart({ data, days, setDays }: {
  data: MetricsSummary['escalation_by_day']
  days: number
  setDays: (d: number) => void
}) {
  const rows = data.map((d) => ({ ...d, label: calendarDate(d.date, { month: 'short', day: 'numeric' }) }))
  const any = rows.some((r) => r.processed > 0)
  return (
    <ChartCard
      title="Escalation rate over time"
      intro="Share of each day's tickets the Escalation Agent flagged (UTC days)"
      table={{
        columns: ['Day', 'Processed', 'Escalated', 'Rate'],
        rows: rows.filter((r) => r.processed > 0).map((r) => [r.label, r.processed, r.escalated, percent(r.rate)]),
      }}
      empty={any ? null : `No processed tickets in the last ${days} days`}
      controls={
        <Segmented label="Range" value={days} onChange={setDays} options={RANGES.map((r) => ({ value: r, label: `${r} days` }))} />
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
                    { label: 'escalated', value: percent(row.rate), color: CHART.ink },
                    { label: 'flagged / processed', value: `${row.escalated} / ${row.processed}` },
                  ]}
                />
              ) : null
            }}
          />
          <Line
            type="monotone"
            dataKey="rate"
            stroke={CHART.ink}
            strokeWidth={2}
            dot={{ r: 4, fill: CHART.ink, stroke: CHART.surface, strokeWidth: 2 }}
            activeDot={{ r: 5, stroke: CHART.surface, strokeWidth: 2 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

export function OutcomeChart({ summary }: { summary: MetricsSummary }) {
  const rows = summary.review_outcomes.map((o) => ({
    ...o,
    label: o.outcome === 'approved_as_is' ? 'Approved as-is' : 'Edited',
    total: o.escalated + o.not_escalated,
  }))
  return (
    <ChartCard
      title="Draft approval"
      intro={`Reviewed drafts, split by escalation · ${percent(summary.approval_rate)} approved as-is`}
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
          <YAxis type="category" dataKey="label" width={110} tick={categoryTick} axisLine={{ stroke: CHART.axis }} tickLine={false} />
          <Tooltip
            cursor={{ fill: CHART.hover }}
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
            <LabelList dataKey="total" position="right" fill={CHART.label} fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

/** Axis unit that keeps tick labels readable for the largest value. */
function timeUnit(maxSeconds: number): { divisor: number; suffix: string } {
  if (maxSeconds < 120) return { divisor: 1, suffix: 's' }
  if (maxSeconds < 7200) return { divisor: 60, suffix: 'min' }
  if (maxSeconds < 172_800) return { divisor: 3600, suffix: 'h' }
  return { divisor: 86_400, suffix: 'd' }
}

export function ResolutionChart({ data }: { data: MetricsSummary['resolution_by_category'] }) {
  const unit = timeUnit(Math.max(0, ...data.map((d) => d.avg_resolution_seconds ?? 0)))
  const rows = data.map((d) => ({
    ...d,
    label: CATEGORY_LABELS[d.category],
    value: d.avg_resolution_seconds === null ? null : d.avg_resolution_seconds / unit.divisor,
    text: duration(d.avg_resolution_seconds),
  }))
  const resolved = rows.reduce((s, r) => s + r.resolved, 0)
  return (
    <ChartCard
      title="Average resolution time by category"
      intro="From ticket submitted to reply approved"
      table={{ columns: ['Category', 'Resolved', 'Average'], rows: rows.map((r) => [r.label, r.resolved, r.text]) }}
      empty={resolved === 0 ? 'No tickets resolved yet' : null}
    >
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 48 }}>
          <CartesianGrid horizontal={false} stroke={CHART.grid} />
          <XAxis type="number" tickFormatter={(v: number) => `${Number(v.toFixed(1))} ${unit.suffix}`} tick={axisTick} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="label" width={120} tick={categoryTick} axisLine={{ stroke: CHART.axis }} tickLine={false} />
          <Tooltip
            cursor={{ fill: CHART.hover }}
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
            <LabelList dataKey="text" position="right" fill={CHART.label} fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

