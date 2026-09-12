import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router'
import { ApiError } from '../api/client'
import { contactKeys, getContactForm } from '../api/public'
import { ContactForm } from '../features/contact'
import { ErrorNotice, Loading, Sheet } from '../ui'

/** Public: a business's customers write in here. No account, no app chrome. */
export function Contact() {
  const { slug = '' } = useParams()
  const form = useQuery({ queryKey: contactKeys.form(slug), queryFn: () => getContactForm(slug), retry: false })

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col px-4 py-12 sm:py-20">
      {form.isPending ? (
        <Loading label="Loading…" />
      ) : form.isError ? (
        form.error instanceof ApiError && form.error.status === 404 ? (
          <Sheet>
            <p className="type-heading text-heading">This contact form isn't available</p>
            <p className="mt-2 text-small text-ink-2">Check the link, or contact the business another way.</p>
          </Sheet>
        ) : (
          <ErrorNotice error={form.error} onRetry={() => void form.refetch()} />
        )
      ) : (
        <>
          <p className="text-small text-ink-2">Contact</p>
          <h1 className="type-label mt-1 border-b-2 border-ink pb-3 text-display text-balance">{form.data.business_name}</h1>
          <p className="mt-3 mb-8 text-body text-ink-2">Send us a message and we'll reply by email.</p>
          <Sheet>
            <ContactForm slug={slug} businessName={form.data.business_name} />
          </Sheet>
        </>
      )}
      <p className="mt-auto pt-10 text-center text-tiny text-ink-3">Support by RAPT</p>
    </main>
  )
}
