import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { reviewKeys } from '../../api/reviews'
import { getAgentTrace, getTicket, listTickets, rerunAgents, ticketKeys } from '../../api/tickets'
import { isRunning } from '../../lib/format'
import type { TicketDetailResponse, TicketStatus } from '../../types'

/** One ticket with its order, drafts and trace. Polls while the agents are running. */
export function useTicket(id: string) {
  return useQuery({
    queryKey: ticketKeys.detail(id),
    queryFn: () => getTicket(id),
    refetchInterval: (q) => (q.state.data && isRunning(q.state.data.status) ? 1500 : false),
  })
}

/** The agent_logs rows for a ticket; polls quickly while a run is live. */
export function useAgentTrace(id: string, live: boolean) {
  return useQuery({
    queryKey: ticketKeys.trace(id),
    queryFn: () => getAgentTrace(id),
    refetchInterval: live ? 1000 : false,
  })
}

export function useTicketsWithStatus(status: TicketStatus, pollMs = 3000) {
  return useQuery({
    queryKey: ticketKeys.list({ status }),
    queryFn: () => listTickets({ status }),
    refetchInterval: pollMs,
  })
}

export function useRerunAgents(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => rerunAgents(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ticketKeys.detail(id) })
      void queryClient.invalidateQueries({ queryKey: reviewKeys.queue })
    },
  })
}

/** After a mutation returns the updated ticket: show it now, refresh the lists around it. */
export function useApplyTicketUpdate() {
  const queryClient = useQueryClient()
  return (ticket: TicketDetailResponse) => {
    queryClient.setQueryData(ticketKeys.detail(ticket.id), ticket)
    void queryClient.invalidateQueries({ queryKey: reviewKeys.queue })
    void queryClient.invalidateQueries({ queryKey: ticketKeys.all })
    void queryClient.invalidateQueries({ queryKey: ['metrics'] })
  }
}
