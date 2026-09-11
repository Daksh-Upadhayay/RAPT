import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { customerKeys, getCustomerOrders } from '../api/customers'
import { createTicket, ticketKeys } from '../api/tickets'
import { CustomerPicker } from '../components/CustomerPicker'
import { Spinner } from '../components/icons'
import { Card, ErrorMessage, PageHeader } from '../components/ui'
import { ORDER_STATUS_LABELS, calendarDate, money } from '../lib/format'
import type { CustomerResponse } from '../types'

export function SubmitTicket() {
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
    customer: !customer ? 'Choose the customer this ticket is from.' : null,
    subject: !subject.trim() ? 'Add a subject.' : null,
    body: !body.trim() ? 'Describe the problem.' : null,
  }
  const show = (key: keyof typeof errors) => (attempted ? errors[key] : null)

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setAttempted(true)
    if (!customer || errors.subject || errors.body) return
    submit.mutate({ customer_id: customer.id, subject: subject.trim(), body: body.trim(), order_id: orderId || null })
  }

  return (
    <>
      <PageHeader
        title="Submit a ticket"
        subtitle="Simulates the customer side. The agents classify it, look up knowledge and the order, and draft a reply for review."
      />
      <form onSubmit={onSubmit} noValidate className="max-w-3xl space-y-6">
        <Card title="Customer">
          {customer ? (
            <div className="flex items-center justify-between gap-4 rounded-lg bg-slate-50 px-3 py-2.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">{customer.name}</p>
                <p className="truncate text-sm text-slate-500">{customer.email}</p>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  setCustomer(null)
                  setOrderId('')
                }}
              >
                Change
              </button>
            </div>
          ) : (
            <>
              <label htmlFor="customer" className="label">
                Find customer
              </label>
              <CustomerPicker
                invalid={!!show('customer')}
                onSelect={(c, order) => {
                  setCustomer(c)
                  setOrderId(order ?? '')
                }}
              />
              {show('customer') && <p className="mt-1 text-xs text-red-700">{show('customer')}</p>}
            </>
          )}

          {customer && (
            <div className="mt-4">
              <label htmlFor="order" className="label">
                Order <span className="font-normal text-slate-500">(optional)</span>
              </label>
              <select
                id="order"
                className="input"
                value={orderId}
                onChange={(e) => setOrderId(e.target.value)}
                disabled={orders.isPending}
              >
                <option value="">No order: a general question</option>
                {orders.data?.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.item_name} · {ORDER_STATUS_LABELS[o.status]} · {calendarDate(o.order_date)} · {money(o.amount)}
                  </option>
                ))}
              </select>
              {orders.isError && <p className="mt-1 text-xs text-red-700">Couldn't load this customer's orders.</p>}
              {orders.data?.length === 0 && <p className="mt-1 text-xs text-slate-500">This customer has no orders.</p>}
            </div>
          )}
        </Card>

        <Card title="Message">
          <div className="space-y-4">
            <div>
              <label htmlFor="subject" className="label">
                Subject
              </label>
              <input
                id="subject"
                className={`input ${show('subject') ? 'border-red-400' : ''}`}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                maxLength={200}
                aria-invalid={!!show('subject')}
              />
              {show('subject') && <p className="mt-1 text-xs text-red-700">{show('subject')}</p>}
            </div>
            <div>
              <label htmlFor="body" className="label">
                Message
              </label>
              <textarea
                id="body"
                rows={7}
                className={`input resize-y ${show('body') ? 'border-red-400' : ''}`}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                aria-invalid={!!show('body')}
              />
              {show('body') && <p className="mt-1 text-xs text-red-700">{show('body')}</p>}
            </div>
          </div>
        </Card>

        {submit.isError && <ErrorMessage error={submit.error} />}
        <button type="submit" className="btn-primary" disabled={submit.isPending}>
          {submit.isPending && <Spinner />}
          Submit ticket
        </button>
      </form>
    </>
  )
}
