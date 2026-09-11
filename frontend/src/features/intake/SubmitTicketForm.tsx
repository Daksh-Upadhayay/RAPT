import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { customerKeys, getCustomerOrders } from '../../api/customers'
import { createTicket, ticketKeys } from '../../api/tickets'
import { ORDER_STATUS_LABELS, calendarDate, money } from '../../lib/format'
import type { CustomerResponse } from '../../types'
import { Button, ErrorNotice, Field, Input, Select, Sheet, Textarea } from '../../ui'
import { CustomerPicker } from './CustomerPicker'

/**
 * The customer side: who is writing, which order it's about, and their message. On
 * submit the ticket page opens and shows the agents working.
 */
export function SubmitTicketForm() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [customer, setCustomer] = useState<CustomerResponse | null>(null)
  const [orderId, setOrderId] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [attempted, setAttempted] = useState(false)

  const orders = useQuery({
    queryKey: customerKeys.orders(customer?.id ?? ''),
    queryFn: () => getCustomerOrders(customer!.id),
    enabled: customer !== null,
  })
  const submit = useMutation({
    mutationFn: createTicket,
    onSuccess: (ticket) => {
      void queryClient.invalidateQueries({ queryKey: ticketKeys.all })
      navigate(`/tickets/${ticket.id}`)
    },
  })

  const errors = {
    customer: customer ? null : 'Choose who this ticket is from.',
    subject: subject.trim() ? null : 'Add a subject.',
    body: body.trim() ? null : 'Write the customer’s message.',
  }
  const shown = (key: keyof typeof errors) => (attempted ? errors[key] : null)

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setAttempted(true)
    if (!customer || errors.subject || errors.body) return
    submit.mutate({ customer_id: customer.id, subject: subject.trim(), body: body.trim(), order_id: orderId || null })
  }

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-2xl space-y-6">
      <Sheet title="From">
        {customer ? (
          <div className="space-y-5">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="truncate font-semibold">{customer.name}</p>
                <p className="truncate text-small text-ink-2">{customer.email}</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setCustomer(null)
                  setOrderId('')
                }}
              >
                Change customer
              </Button>
            </div>
            <Field
              id="order"
              label="Order"
              optional
              error={orders.isError ? 'This customer’s orders couldn’t be loaded. Try again.' : null}
              hint={orders.data?.length === 0 ? 'This customer has no orders.' : 'Linking an order lets the agents look it up.'}
            >
              <Select id="order" value={orderId} onChange={(e) => setOrderId(e.target.value)} disabled={orders.isPending}>
                <option value="">Not about a specific order</option>
                {orders.data?.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.item_name}, {ORDER_STATUS_LABELS[o.status].toLowerCase()}, {calendarDate(o.order_date)}, {money(o.amount)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        ) : (
          <Field id="customer" label="Customer" error={shown('customer')} hint="Pasting an order ID picks its customer and links the order.">
            <CustomerPicker
              invalid={!!shown('customer')}
              onSelect={(c, order) => {
                setCustomer(c)
                setOrderId(order ?? '')
              }}
            />
          </Field>
        )}
      </Sheet>

      <Sheet title="Message">
        <div className="space-y-5">
          <Field id="subject" label="Subject" error={shown('subject')}>
            <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={200} invalid={!!shown('subject')} />
          </Field>
          <Field id="body" label="Message" error={shown('body')}>
            <Textarea id="body" rows={7} value={body} onChange={(e) => setBody(e.target.value)} invalid={!!shown('body')} />
          </Field>
        </div>
      </Sheet>

      {submit.isError && <ErrorNotice error={submit.error} />}
      <Button type="submit" variant="primary" loading={submit.isPending}>
        Submit ticket
      </Button>
    </form>
  )
}
