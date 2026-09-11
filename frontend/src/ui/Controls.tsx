/** Pick one of a few options (e.g. a date range, a run). */
export function Segmented<T extends string | number>({ label, options, value, onChange }: {
  label: string
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-label border border-ink/35 bg-paper p-0.5">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
          className={`h-7 rounded-[2px] px-2.5 text-tiny font-semibold ${o.value === value ? 'bg-ink text-paper' : 'text-ink-2 hover:bg-ink/5'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/** A 0..1 value as a bar, e.g. model confidence. */
export function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div
      className="h-1.5 overflow-hidden rounded-full bg-ink/10"
      role="meter"
      aria-label={label}
      aria-valuenow={Math.round(value * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className="h-full rounded-full bg-ink" style={{ width: `${Math.min(1, Math.max(0, value)) * 100}%` }} />
    </div>
  )
}
