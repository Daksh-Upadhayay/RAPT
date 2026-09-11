import type { CustomerCreate, CustomerResponse, OrderResponse } from '../types'
import { request } from './client'

export const customerKeys = {
  search: (search: string) => ['customers', 'search', search] as const,
  orders: (customerId: string) => ['customers', 'orders', customerId] as const,
  order: (orderId: string) => ['orders', orderId] as const,
}

export const searchCustomers = (search: string, limit = 8) =>
  request<CustomerResponse[]>('/customers', { query: { search, limit } })

export const getCustomer = (customerId: string) => request<CustomerResponse>(`/customers/${customerId}`)

export const getCustomerOrders = (customerId: string) => request<OrderResponse[]>(`/customers/${customerId}/orders`)

export const getOrder = (orderId: string) => request<OrderResponse>(`/orders/${orderId}`)

export const createCustomer = (data: CustomerCreate) => request<CustomerResponse>('/customers', { method: 'POST', body: data })
