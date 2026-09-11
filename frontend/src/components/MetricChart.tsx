import { useState, type ReactNode } from 'react'

export interface TableView {
  columns: string[]
  rows: (string | number)[][]
}

/**
 * A chart card with a table view of the same numbers, so no value depends on colour or
 * hovering (a few category colours are below 3:1 contrast on white).
 */
export function MetricChart({ title, subtitle, table, action, empty, legend, children }: {
  title: string
  subtitle?: string
  legend?: { label: string; color: string }[] // for charts with two or more series
  table: TableView
  action?: ReactNode
  empty?: string | null
  children: ReactNode
}) {
  const [asTable, setAsTable] = useState(false)
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {action}
          <button type="button" className="text-xs font-medium text-indigo-600 hover:underline" onClick={() => setAsTable((v) => !v)}>
            {asTable ? 'Chart' : 'Table'}
          </button>
        </div>
      </header>
      {legend && !asTable && !empty && (
        <ul className="mb-2 flex flex-wrap gap-4 text-xs text-slate-600">
          {legend.map((item) => (
            <li key={item.label} className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm" style={{ background: item.color }} aria-hidden="true" />
              {item.label}
            </li>
          ))}
        </ul>
      )}
      {asTable ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {table.columns.map((c, i) => (
                  <th key={c} className={`py-2 font-medium ${i > 0 ? 'text-right' : ''}`}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, r) => (
                <tr key={r} className="border-b border-slate-100 last:border-0">
                  {row.map((cell, i) => (
                    <td key={i} className={`py-1.5 ${i > 0 ? 'text-right tabular-nums' : 'text-slate-800'}`}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : empty ? (
        <div className="flex h-56 items-center justify-center rounded-lg bg-slate-50 text-sm text-slate-500">{empty}</div>
      ) : (
        <div className="h-56">{children}</div>
      )}
    </section>
  )
}

/** Tooltip body: the value leads, the label follows. */
export function TooltipBox({ title, rows }: { title: string; rows: { label: string; value: string; color?: string }[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="mb-1 text-slate-500">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex items-center gap-2">
          {r.color && <span className="h-0.5 w-3 rounded" style={{ background: r.color }} aria-hidden="true" />}
          <span className="font-semibold text-slate-900 tabular-nums">{r.value}</span>
          <span className="text-slate-500">{r.label}</span>
        </p>
      ))}
    </div>
  )
}

export function StatTile({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
      {detail && <p className="mt-0.5 text-xs text-slate-500">{detail}</p>}
    </div>
  )
}
