import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { getSettings, settingsKeys, updateSettings } from '../../api/public'
import { Button, ErrorNotice, Loading, Sheet, Tag } from '../../ui'

/** Switch the public contact form on or off, and get the link to share. */
export function ContactSettings() {
  const queryClient = useQueryClient()
  const settings = useQuery({ queryKey: settingsKeys.all, queryFn: getSettings })
  const toggle = useMutation({
    mutationFn: (on: boolean) => updateSettings({ contact_form_enabled: on }),
    onSuccess: (data) => queryClient.setQueryData(settingsKeys.all, data),
  })
  const [copied, setCopied] = useState(false)

  if (settings.isPending) return <Loading label="Loading settings…" />
  if (settings.isError) return <ErrorNotice error={settings.error} onRetry={() => void settings.refetch()} />

  const { contact_form_enabled: on, slug } = settings.data
  const link = `${window.location.origin}/contact/${slug}`

  return (
    <Sheet title="Customer contact form" aside={on ? <Tag tone="ok">On</Tag> : <Tag tone="muted">Off</Tag>}>
      <p className="max-w-[65ch] text-small text-ink-2">
        A public page where your customers write to you without an account. Each message becomes a ticket in your review
        queue, with a drafted reply. Link to it from your website's contact or help page.
      </p>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button variant={on ? 'secondary' : 'primary'} loading={toggle.isPending} onClick={() => toggle.mutate(!on)}>
          {on ? 'Turn the form off' : 'Turn the form on'}
        </Button>
      </div>
      {toggle.isError && (
        <div className="mt-4">
          <ErrorNotice error={toggle.error} />
        </div>
      )}
      {on && (
        <div className="mt-6">
          <p className="mb-1.5 text-small font-semibold">Your form's link</p>
          <div className="flex flex-wrap items-center gap-2">
            <code className="min-w-0 truncate rounded-label border border-line bg-sunken px-3 py-2 font-mono text-small">{link}</code>
            <Button size="sm" onClick={() => void navigator.clipboard?.writeText(link).then(() => setCopied(true))}>
              {copied ? 'Copied' : 'Copy link'}
            </Button>
            <a href={link} target="_blank" rel="noreferrer" className="text-small font-semibold underline underline-offset-2">
              Open the form
            </a>
          </div>
          <p className="mt-2 text-tiny text-ink-3">Messages are limited to 5 per visitor and 100 per hour in total, to keep spam out.</p>
        </div>
      )}
    </Sheet>
  )
}
