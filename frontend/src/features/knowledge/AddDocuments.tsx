import { useRef, useState, type DragEvent, type FormEvent } from 'react'
import type { KnowledgeUploadResult } from '../../types'
import { Button, CheckIcon, ErrorNotice, Field, Input, Segmented, Sheet, Textarea, XIcon } from '../../ui'
import { usePaste, useUpload } from './hooks'

const ACCEPT = '.md,.markdown,.txt,.html,.htm,.pdf'

function UploadResults({ results }: { results: KnowledgeUploadResult[] }) {
  return (
    <ul className="mt-4 space-y-1.5 text-small" aria-live="polite">
      {results.map((r) => (
        <li key={r.filename} className="flex items-start gap-2">
          {r.error ? <XIcon className="mt-0.5 size-4 shrink-0 text-danger" /> : <CheckIcon className="mt-0.5 size-4 shrink-0 text-ok" />}
          <span>
            <span className="font-semibold">{r.filename}</span>
            <span className="text-ink-2">{r.error ? `: ${r.error}` : ': added, being indexed'}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

function UploadFiles() {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const upload = useUpload()

  function send(files: FileList | null) {
    if (files?.length) upload.mutate(Array.from(files))
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    send(e.dataTransfer.files)
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`rounded-label border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragging ? 'border-ink bg-accent-wash' : 'border-ink/25 bg-sunken'
        }`}
      >
        <p className="font-semibold">Drop your help documents here</p>
        <p className="mt-1 text-small text-ink-2">FAQ, returns and shipping policies. Markdown, text, HTML or PDF, up to 5 MB each.</p>
        <Button className="mt-4" variant="secondary" loading={upload.isPending} onClick={() => input.current?.click()}>
          Choose files
        </Button>
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          aria-label="Choose files"
          onChange={(e) => {
            send(e.target.files)
            e.target.value = ''
          }}
        />
      </div>
      {upload.isError && (
        <div className="mt-4">
          <ErrorNotice error={upload.error} />
        </div>
      )}
      {upload.data && <UploadResults results={upload.data} />}
    </div>
  )
}

function PasteText() {
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const paste = usePaste()

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    paste.mutate({ title: title.trim(), text }, { onSuccess: () => (setTitle(''), setText('')) })
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Field id="paste-title" label="Title">
        <Input id="paste-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
      </Field>
      <Field id="paste-text" label="Text" hint="Lines starting with # or ## become section headings.">
        <Textarea id="paste-text" rows={8} value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
      {paste.isError && <ErrorNotice error={paste.error} />}
      {paste.isSuccess && <p className="text-small text-ok">Added. It will be searchable in a few seconds.</p>}
      <Button type="submit" variant="primary" loading={paste.isPending} disabled={!title.trim() || !text.trim()}>
        Add text
      </Button>
    </form>
  )
}

export function AddDocuments() {
  const [mode, setMode] = useState<'upload' | 'paste'>('upload')
  return (
    <Sheet
      title="Add help documents"
      aside={
        <Segmented
          label="How to add"
          value={mode}
          onChange={setMode}
          options={[
            { value: 'upload', label: 'Upload files' },
            { value: 'paste', label: 'Paste text' },
          ]}
        />
      }
    >
      {mode === 'upload' ? <UploadFiles /> : <PasteText />}
    </Sheet>
  )
}
