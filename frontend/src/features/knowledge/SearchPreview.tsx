import { useState, type FormEvent } from 'react'
import { Button, ErrorNotice, Field, Input, Sheet } from '../../ui'
import { useSearchPreview } from './hooks'

/** Type what a customer might ask; see which sections a draft would be based on. */
export function SearchPreview() {
  const [query, setQuery] = useState('')
  const search = useSearchPreview()

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (query.trim()) search.mutate(query.trim())
  }

  return (
    <Sheet title="Test a question">
      <form onSubmit={onSubmit} className="space-y-3">
        <Field id="test-question" label="A customer asks…" hint="Shows the 3 sections a draft would be based on.">
          <Input id="test-question" value={query} onChange={(e) => setQuery(e.target.value)} />
        </Field>
        <Button type="submit" size="sm" loading={search.isPending} disabled={!query.trim()}>
          Find sections
        </Button>
      </form>
      {search.isError && (
        <div className="mt-4">
          <ErrorNotice error={search.error} />
        </div>
      )}
      {search.data && (
        <ol className="mt-5 space-y-4" aria-live="polite">
          {search.data.length === 0 && <li className="text-small text-ink-2">Nothing in the knowledge base yet.</li>}
          {search.data.map((hit) => (
            <li key={hit.id}>
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-small font-semibold">{hit.title}</p>
                <span className="text-tiny text-ink-3 tabular-nums">{hit.similarity.toFixed(2)}</span>
              </div>
              <p className="mt-1 line-clamp-3 text-small text-ink-2">{hit.content}</p>
            </li>
          ))}
        </ol>
      )}
    </Sheet>
  )
}
