import { useQuery } from '@tanstack/react-query'
import { useEffect, useId, useState } from 'react'
import { customerKeys, getCustomer, getOrder, searchCustomers } from '../../api/customers'
import { ORDER_STATUS_LABELS } from '../../lib/format'
import type { CustomerResponse, OrderResponse } from '../../types'
import { Input, Spinner } from '../../ui'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(timer)
  }, [value, ms])
  return debounced
}

type Option = { kind: 'customer'; customer: CustomerResponse } | { kind: 'order'; order: OrderResponse }

/**
 * Find the customer by name or email, or paste an order ID to pick that order's customer
 * and link the order in one step.
 */
export function CustomerPicker({ invalid, onSelect }: {
  invalid?: boolean
  onSelect: (customer: CustomerResponse, orderId?: string) => void
}) {
  const listId = useId()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [picking, setPicking] = useState(false)
  const [pickError, setPickError] = useState<string | null>(null)
  const term = useDebounced(query.trim(), 200)
  const isOrderId = UUID_RE.test(term)

  const customers = useQuery({
    queryKey: customerKeys.search(term),
    queryFn: () => searchCustomers(term),
    enabled: open && !isOrderId,
    placeholderData: (prev) => prev,
  })
  const order = useQuery({
    queryKey: customerKeys.order(term),
    queryFn: () => getOrder(term),
    enabled: open && isOrderId,
  })

  const options: Option[] = isOrderId
    ? order.data
      ? [{ kind: 'order', order: order.data }]
      : []
    : (customers.data ?? []).map((customer) => ({ kind: 'customer', customer }))
  const loading = isOrderId ? order.isFetching : customers.isFetching

  async function choose(option: Option) {
    setPickError(null)
    if (option.kind === 'customer') {
      onSelect(option.customer)
      return
    }
    setPicking(true)
    try {
      onSelect(await getCustomer(option.order.customer_id), option.order.id)
    } catch {
      setPickError("Couldn't load that order's customer. Try again.")
    } finally {
      setPicking(false)
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((i) => Math.min(i + 1, options.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && open && options[active]) {
      e.preventDefault()
      void choose(options[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="relative">
      <Input
        id="customer"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open && options[active] ? `${listId}-${active}` : undefined}
        invalid={invalid}
        autoComplete="off"
        placeholder="Name, email or order ID"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setActive(0)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKeyDown}
      />
      {(loading || picking) && <Spinner className="absolute top-3 right-3 text-ink-3" />}
      {pickError && <p className="mt-1.5 text-tiny font-medium text-danger-ink">{pickError}</p>}
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-label border border-ink bg-paper py-1"
        >
          {options.length === 0 && !loading && (
            <li className="px-3 py-2 text-small text-ink-2">
              {isOrderId ? 'No order with that ID.' : 'No matching customers.'}
            </li>
          )}
          {options.map((option, i) => (
            <li
              key={option.kind === 'customer' ? option.customer.id : option.order.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => void choose(option)}
              onMouseEnter={() => setActive(i)}
              className={`cursor-pointer px-3 py-2 text-small ${i === active ? 'bg-accent-wash' : ''}`}
            >
              {option.kind === 'customer' ? (
                <>
                  <span className="font-semibold">{option.customer.name}</span>
                  <span className="ml-2 text-ink-2">{option.customer.email}</span>
                </>
              ) : (
                <>
                  <span className="font-semibold">Order: {option.order.item_name}</span>
                  <span className="ml-2 text-ink-2">
                    {ORDER_STATUS_LABELS[option.order.status]} · selects its customer and links the order
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
