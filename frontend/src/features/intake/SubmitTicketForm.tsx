import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { createCustomer, customerKeys, getCustomerOrders } from '../../api/customers'
import { createTicket, ticketKeys } from '../../api/tickets'
import { ORDER_STATUS_LABELS, calendarDate, money } from '../../lib/format'
import type { CustomerResponse } from '../../types'
import { Button, ErrorNotice, Field, Input, Segmented, Select, Sheet, Textarea } from '../../ui'
import { CustomerPicker } from './CustomerPicker'

/**
 * The customer side: who is writing, which order it's about, and their message. On
 * submit the ticket page opens and shows the agents working.
 */
export function SubmitTicketForm() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [customer, setCustomer] = useState<CustomerResponse | null>(null)
  // A new business has no customers yet: add one while filing their first ticket
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [newName, setNewName] = useState('')
  const [newEmail, setNewEmail] = useState('')
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
    mutationFn: async (ticket: { subject: string; body: string; order_id: string | null }) => {
      const customerId = customer
        ? customer.id
        : (await createCustomer({ name: newName.trim(), email: newEmail.trim() })).id
      return createTicket({ customer_id: customerId, ...ticket })
    },
    onSuccess: (ticket) => {
      void queryClient.invalidateQueries({ queryKey: ticketKeys.all })
      navigate(`/tickets/${ticket.id}`)
    },
  })

  const newCustomerValid = newName.trim() !== '' && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(newEmail.trim())
  const errors = {
    customer: customer || (customerMode === 'new' && newCustomerValid) ? null : customerMode === 'new' ? 'Add the customer’s name and a valid email.' : 'Choose who this ticket is from.',
    subject: subject.trim() ? null : 'Add a subject.',
    body: body.trim() ? null : 'Write the customer’s message.',
  }
  const shown = (key: keyof typeof errors) => (attempted ? errors[key] : null)

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setAttempted(true)
    if (errors.customer || errors.subject || errors.body) return
    submit.mutate({ subject: subject.trim(), body: body.trim(), order_id: orderId || null })
  }

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-2xl space-y-6">
      <Sheet
        title="From"
        aside={
          !customer && (
            <Segmented
              label="Customer"
              value={customerMode}
              onChange={setCustomerMode}
              options={[
                { value: 'existing', label: 'Existing customer' },
                { value: 'new', label: 'New customer' },
              ]}
            />
          )
        }
      >
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
        ) : customerMode === 'new' ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="new-name" label="Name" error={attempted && !newName.trim() ? 'Add a name.' : null}>
              <Input id="new-name" value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={200} />
            </Field>
            <Field id="new-email" label="Email" error={attempted && !newCustomerValid && newName.trim() ? 'Add a valid email.' : null}>
              <Input id="new-email" type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
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
