import { Sheet } from '../../ui'
import type { RetrievedHit } from '../trace/model'

/** The knowledge-base entries the draft was allowed to use, closest match first. */
export function GroundingList({ hits }: { hits: RetrievedHit[] }) {
  return (
    <Sheet title="What the draft is based on" aside="Match score">
      {hits.length === 0 ? (
        <p className="text-small text-ink-2">No knowledge-base entries were retrieved for this run.</p>
      ) : (
        <ol className="space-y-4">
          {hits.map((hit) => (
            <li key={hit.id}>
              <div className="flex items-baseline justify-between gap-3">
                <p className="font-semibold">{hit.title}</p>
                <span className="shrink-0 text-tiny text-ink-3 tabular-nums">{hit.similarity.toFixed(2)}</span>
              </div>
              {hit.content ? (
                <p className="mt-1 border-l-2 border-line pl-3 text-small leading-6 text-ink-2">{hit.content}</p>
              ) : (
                <p className="mt-1 text-tiny text-ink-3">The entry’s text wasn’t recorded for this older run.</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </Sheet>
  )
}
