import { useState } from 'react'
import { dateTime } from '../../lib/format'
import type { KnowledgeBaseResponse, KnowledgeDocumentResponse } from '../../types'
import { Button, CheckIcon, EmptyState, ErrorNotice, Input, Loading, Spinner, Tag, Textarea, XIcon } from '../../ui'
import { useDeleteDocument, useDeleteSection, useDocument, useDocuments, useUpdateSection } from './hooks'

function StatusTag({ document }: { document: KnowledgeDocumentResponse }) {
  if (document.status === 'processing') return <Tag tone="muted" icon={<Spinner className="size-3" />}>Indexing</Tag>
  if (document.status === 'failed') return <Tag tone="danger" icon={<XIcon className="size-3" />} title={document.error ?? undefined}>Failed</Tag>
  return <Tag tone="ok" icon={<CheckIcon className="size-3" />}>{document.section_count} {document.section_count === 1 ? 'section' : 'sections'}</Tag>
}

function SectionItem({ section, editable }: { section: KnowledgeBaseResponse; editable: boolean }) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(section.title)
  const [content, setContent] = useState(section.content)
  const update = useUpdateSection()
  const remove = useDeleteSection()

  if (editing) {
    return (
      <li className="space-y-3 rounded-label bg-sunken p-4">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Section title" maxLength={200} />
        <Textarea value={content} onChange={(e) => setContent(e.target.value)} rows={6} aria-label="Section text" />
        {update.isError && <ErrorNotice error={update.error} />}
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="primary"
            loading={update.isPending}
            disabled={!title.trim() || !content.trim()}
            onClick={() => update.mutate({ id: section.id, data: { title: title.trim(), content: content.trim() } }, { onSuccess: () => setEditing(false) })}
          >
            Save section
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      </li>
    )
  }
  return (
    <li className="border-l-2 border-line pl-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold">{section.title}</p>
        {editable && (
          <div className="flex gap-3 text-tiny font-semibold">
            <button type="button" className="underline underline-offset-2" onClick={() => setEditing(true)}>
              Edit
            </button>
            <button type="button" className="text-danger-ink underline underline-offset-2" disabled={remove.isPending} onClick={() => remove.mutate(section.id)}>
              Remove
            </button>
          </div>
        )}
      </div>
      <p className="mt-1 max-w-[72ch] whitespace-pre-wrap text-small leading-6 text-ink-2">{section.content}</p>
    </li>
  )
}

function DocumentRow({ document, editable }: { document: KnowledgeDocumentResponse; editable: boolean }) {
  const [open, setOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const detail = useDocument(document.id, open && document.status === 'ready')
  const remove = useDeleteDocument()

  return (
    <li className="rounded-label border border-line bg-paper">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4">
        <button
          type="button"
          className="min-w-0 flex-1 text-left disabled:cursor-default"
          onClick={() => setOpen((v) => !v)}
          disabled={document.status !== 'ready'}
          aria-expanded={open}
        >
          <p className="type-heading truncate">{document.title}</p>
          <p className="mt-0.5 text-tiny text-ink-3">
            {document.filename ?? 'Pasted text'}, added by {document.uploaded_by}, {dateTime(document.created_at)}
          </p>
        </button>
        <StatusTag document={document} />
        {editable &&
          (confirming ? (
            <span className="flex items-center gap-2 text-small">
              Remove it and its sections?
              <Button size="sm" variant="secondary" loading={remove.isPending} onClick={() => remove.mutate(document.id)}>
                Remove
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
                Keep
              </Button>
            </span>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}>
              Remove
            </Button>
          ))}
      </div>
      {document.status === 'failed' && <p className="border-t border-line px-5 py-3 text-small text-danger-ink">{document.error}</p>}
      {open && (
        <div className="border-t border-line px-5 py-4">
          {detail.isPending ? (
            <Loading label="Loading sections…" />
          ) : detail.isError ? (
            <ErrorNotice error={detail.error} />
          ) : (
            <ol className="space-y-5">
              {detail.data.sections.map((s) => (
                <SectionItem key={s.id} section={s} editable={editable} />
              ))}
            </ol>
          )}
        </div>
      )}
    </li>
  )
}

export function DocumentList({ editable }: { editable: boolean }) {
  const documents = useDocuments()
  if (documents.isPending) return <Loading label="Loading documents…" />
  if (documents.isError) return <ErrorNotice error={documents.error} onRetry={() => void documents.refetch()} />
  if (!documents.data.length) {
    return (
      <EmptyState title="No help documents yet">
        {editable ? 'Add your FAQ, returns and shipping policies. Drafts can only quote what is here.' : 'An admin adds the help documents that drafts quote.'}
      </EmptyState>
    )
  }
  return (
    <ul className="space-y-2">
      {documents.data.map((d) => (
        <DocumentRow key={d.id} document={d} editable={editable} />
      ))}
    </ul>
  )
}
