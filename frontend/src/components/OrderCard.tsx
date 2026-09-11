import { ORDER_STATUS_LABELS, calendarDate, money } from '../lib/format'
import type { OrderResponse } from '../types'
import { Card } from './ui'

const STATUS_STYLES: Record<OrderResponse['status'], string> = {
  processing: 'bg-slate-100 text-slate-700',
  shipped: 'bg-sky-50 text-sky-800',
  delivered: 'bg-emerald-50 text-emerald-800',
  delayed: 'bg-amber-50 text-amber-800',
  cancelled: 'bg-slate-100 text-slate-500',
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-900">{children}</dd>
    </div>
  )
}

export function OrderCard({ order }: { order: OrderResponse }) {
  return (
    <Card
      title="Linked order"
      action={
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[order.status]}`}>
          {ORDER_STATUS_LABELS[order.status]}
        </span>
      }
    >
      <dl className="divide-y divide-slate-100">
        <Row label="Item">{order.item_name}</Row>
        <Row label="Amount">{money(order.amount)}</Row>
        <Row label="Ordered">{calendarDate(order.order_date)}</Row>
        <Row label="Expected delivery">{order.expected_delivery ? calendarDate(order.expected_delivery) : '–'}</Row>
        <Row label="Tracking">
          <span className="font-mono text-xs">{order.tracking_number ?? '–'}</span>
        </Row>
      </dl>
    </Card>
  )
}
