import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { sendContactMessage } from '../../api/public'
import type { ContactReceipt } from '../../types'
import { Button, CheckIcon, ErrorNotice, Field, Input, Textarea } from '../../ui'

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

function Sent({ receipt, email }: { receipt: ContactReceipt; email: string }) {
  return (
    <div role="status" className="text-center">
      <span className="mx-auto flex size-12 items-center justify-center rounded-full bg-ok-wash text-ok">
        <CheckIcon className="size-6" />
      </span>
      <p className="type-heading mt-4 text-heading">Message sent</p>
      <p className="mt-2 text-body text-ink-2">
        {receipt.business_name} will reply to <span className="font-semibold text-ink">{email}</span>.
      </p>
      <p className="mt-4 text-small text-ink-3">
        Your reference: <span className="font-mono text-ink">{receipt.reference}</span>
      </p>
    </div>
  )
}

/** The customer's side: write to the business, no account needed. */
export function ContactForm({ slug, businessName }: { slug: string; businessName: string }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [website, setWebsite] = useState('') // honeypot
  const [attempted, setAttempted] = useState(false)
  const send = useMutation({ mutationFn: () => sendContactMessage(slug, { name: name.trim(), email: email.trim(), subject: subject.trim(), message: message.trim(), website }) })

  const errors = {
    name: name.trim() ? null : 'Add your name.',
    email: EMAIL.test(email.trim()) ? null : 'Add an email address we can reply to.',
    subject: subject.trim() ? null : 'Add a subject.',
    message: message.trim().length >= 10 ? null : 'Tell us a little more (at least 10 characters).',
  }
  const shown = (key: keyof typeof errors) => (attempted ? errors[key] : null)

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setAttempted(true)
    if (Object.values(errors).some(Boolean)) return
    send.mutate()
  }

  if (send.isSuccess) return <Sent receipt={send.data} email={email.trim()} />

  const error =
    send.error instanceof ApiError && send.error.status === 422
      ? new Error('Some details look wrong. Check the fields and try again.')
      : send.error

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="c-name" label="Your name" error={shown('name')}>
          <Input id="c-name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} invalid={!!shown('name')} />
        </Field>
        <Field id="c-email" label="Email" error={shown('email')}>
          <Input id="c-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} invalid={!!shown('email')} />
        </Field>
      </div>
      <Field id="c-subject" label="Subject" error={shown('subject')}>
        <Input id="c-subject" value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={200} invalid={!!shown('subject')} />
      </Field>
      <Field id="c-message" label="How can we help?" error={shown('message')} hint="Include your order number if it's about an order.">
        <Textarea id="c-message" rows={6} value={message} onChange={(e) => setMessage(e.target.value)} maxLength={5000} invalid={!!shown('message')} />
      </Field>
      {/* Honeypot: hidden from people and screen readers; bots fill it in */}
      <div aria-hidden="true" className="absolute left-[-9999px] h-px w-px overflow-hidden">
        <label htmlFor="c-website">Website</label>
        <input id="c-website" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
      </div>
      {send.isError && <ErrorNotice error={error} />}
      <Button type="submit" variant="primary" className="w-full sm:w-auto" loading={send.isPending}>
        Send message
      </Button>
      <p className="text-tiny text-ink-3">
        Your message and contact details go to {businessName}, who use RAPT to answer support requests. They're used only to reply to you.
      </p>
    </form>
  )
}
