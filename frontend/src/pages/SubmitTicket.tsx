import { SubmitTicketForm } from '../features/intake'
import { PageHeader } from '../ui'

export function SubmitTicket() {
  return (
    <>
      <PageHeader
        title="Submit a ticket"
        intro="Write in as a customer. The agents classify the ticket, look up the order and the knowledge base, and draft a reply for review."
      />
      <SubmitTicketForm />
    </>
  )
}
