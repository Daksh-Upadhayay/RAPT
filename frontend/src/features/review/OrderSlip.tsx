import type { ReactNode } from 'react'
import { ORDER_STATUS_LABELS, calendarDate, money } from '../../lib/format'
import type { OrderResponse } from '../../types'
import { Sheet, Tag, type TagTone } from '../../ui'

const STATUS_TONE: Record<OrderResponse['status'], TagTone> = {
  processing: 'neutral',
  shipped: 'neutral',
  delivered: 'ok',
  delayed: 'accent',
  cancelled: 'muted',
}

function Line({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-dashed border-line py-2 text-small last:border-0">
      <dt className="text-ink-2">{label}</dt>
      <dd className="text-right font-semibold">{children}</dd>
    </div>
  )
}

/** The linked order, laid out like a packing slip. */
export function OrderSlip({ order }: { order: OrderResponse }) {
  return (
    <Sheet title="Linked order" aside={<Tag tone={STATUS_TONE[order.status]}>{ORDER_STATUS_LABELS[order.status]}</Tag>}>
      <dl>
        <Line label="Item">{order.item_name}</Line>
        <Line label="Amount">{money(order.amount)}</Line>
        <Line label="Ordered">{calendarDate(order.order_date)}</Line>
        <Line label="Expected">{order.expected_delivery ? calendarDate(order.expected_delivery) : 'Not set'}</Line>
        <Line label="Tracking">
          {order.tracking_number ? <span className="font-mono text-tiny font-normal">{order.tracking_number}</span> : 'Not shipped yet'}
        </Line>
      </dl>
    </Sheet>
  )
}
