import type { MetricsSummary } from '../types'
import { request } from './client'

export const metricsKeys = {
  all: ['metrics'] as const,
  summary: (days: number) => ['metrics', 'summary', days] as const,
}

export const getMetricsSummary = (days: number) => request<MetricsSummary>('/metrics/summary', { query: { days } })
