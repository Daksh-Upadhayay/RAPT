import type { RetrievedHit } from '../lib/trace'
import { Card } from './ui'

/** What the Knowledge Agent retrieved, so the reviewer can check the draft's grounding. */
export function KnowledgeSnippets({ hits }: { hits: RetrievedHit[] }) {
  return (
    <Card title="Retrieved knowledge" action={<span className="text-xs text-slate-500">cosine similarity</span>}>
      {hits.length === 0 ? (
        <p className="text-sm text-slate-500">Nothing retrieved for this run.</p>
      ) : (
        <ol className="space-y-3">
          {hits.map((hit, i) => (
            <li key={hit.id} className="rounded-lg bg-slate-50 p-3">
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-sm font-medium text-slate-900">
                  <span className="mr-1.5 text-slate-400">{i + 1}.</span>
                  {hit.title}
                </p>
                <span className="shrink-0 text-xs text-slate-500 tabular-nums">{hit.similarity.toFixed(2)}</span>
              </div>
              {hit.content ? (
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{hit.content}</p>
              ) : (
                <p className="mt-1.5 text-xs text-slate-400 italic">Content not recorded for this run (logged before Phase 5).</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}
