import { useState, type ReactNode } from 'react'
import { Sheet } from '../../ui'

export interface TableView {
  columns: string[]
  rows: (string | number)[][]
}

/**
 * A chart on a sheet, with a table view of the same numbers, so no value depends on
 * colour or hovering (a few category colours are below 3:1 contrast on white).
 */
export function ChartCard({ title, intro, table, controls, empty, legend, children }: {
  title: string
  intro?: string
  table: TableView
  controls?: ReactNode
  empty?: string | null
  legend?: { label: string; color: string }[] // charts with two or more series
  children: ReactNode
}) {
  const [asTable, setAsTable] = useState(false)
  return (
    <Sheet
      title={title}
      aside={
        <div className="flex items-center gap-3">
          {controls}
          <button type="button" className="font-semibold text-ink underline-offset-2 hover:underline" onClick={() => setAsTable((v) => !v)}>
            {asTable ? 'Show chart' : 'Show table'}
          </button>
        </div>
      }
    >
      {intro && <p className="-mt-1 mb-4 text-small text-ink-2">{intro}</p>}
      {legend && !asTable && !empty && (
        <ul className="mb-3 flex flex-wrap gap-4 text-tiny text-ink-2">
          {legend.map((item) => (
            <li key={item.label} className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-[1px]" style={{ background: item.color }} aria-hidden="true" />
              {item.label}
            </li>
          ))}
        </ul>
      )}
      {asTable ? (
        <div className="overflow-x-auto">
          <table className="w-full text-small">
            <thead>
              <tr className="border-b-2 border-ink text-left">
                {table.columns.map((c, i) => (
                  <th key={c} className={`pb-2 font-semibold ${i > 0 ? 'text-right' : ''}`}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, r) => (
                <tr key={r} className="border-b border-line last:border-0">
                  {row.map((cell, i) => (
                    <td key={i} className={`py-2 ${i > 0 ? 'text-right tabular-nums' : ''}`}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : empty ? (
        <div className="flex h-56 items-center justify-center rounded-label bg-sunken px-6 text-center text-small text-ink-2">{empty}</div>
      ) : (
        <div className="h-56">{children}</div>
      )}
    </Sheet>
  )
}

/** Tooltip body: the value leads, the label follows. */
export function TooltipBox({ title, rows }: { title: string; rows: { label: string; value: string; color?: string }[] }) {
  return (
    <div className="rounded-label border border-ink bg-paper px-3 py-2 text-tiny">
      <p className="mb-1 text-ink-2">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex items-center gap-2">
          {r.color && <span className="h-0.5 w-3" style={{ background: r.color }} aria-hidden="true" />}
          <span className="font-bold tabular-nums">{r.value}</span>
          <span className="text-ink-2">{r.label}</span>
        </p>
      ))}
    </div>
  )
}
