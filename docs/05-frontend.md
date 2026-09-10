# Frontend (React)

## Pages

### 1. Submit Ticket (`/submit`)
- Simple form: subject, body, optional order lookup (dropdown/search by
  order ID or customer email) — simulates the customer-facing side
- On submit, redirect to a "ticket status" view showing live status
  (poll `GET /tickets/{id}` every few seconds while agents run)

### 2. Review Queue (`/reviews`)
- The core screen. Lists tickets with `status = awaiting_review`
- Each row: subject, category badge, urgency badge, escalation flag if any
- Click into a ticket to see:
  - Original customer message
  - Retrieved knowledge snippets (so the reviewer can sanity-check grounding)
  - Order data if applicable
  - The AI draft response, editable inline
  - Approve / Edit & Approve buttons

### 3. Agent Trace View (`/tickets/{id}/trace`)
- Visual timeline of the 5 agent steps for a given ticket
- Each step shows: agent name, input summary, output summary, duration
- This is a strong interview demo piece — show it explicitly when discussing
  the project

### 4. Metrics Dashboard (`/dashboard`)
- Charts (Recharts):
  - Tickets by category (bar chart)
  - Escalation rate over time (line chart)
  - Draft approval rate: approved-as-is vs. edited vs. escalated (pie/bar)
  - Avg resolution time by category
- Pulls from `GET /metrics/summary`

## Component structure (rough)
```
src/
  pages/
    SubmitTicket.tsx
    ReviewQueue.tsx
    TicketDetail.tsx
    AgentTrace.tsx
    Dashboard.tsx
  components/
    TicketCard.tsx
    CategoryBadge.tsx
    UrgencyBadge.tsx
    DraftEditor.tsx
    AgentStepCard.tsx
    MetricChart.tsx
  api/
    client.ts          # fetch wrapper / axios instance
    tickets.ts
    reviews.ts
    metrics.ts
  types/
    index.ts            # TS types mirroring the backend Pydantic schemas
```

## Notes
- Keep API types in `types/index.ts` mirroring the Pydantic schemas exactly —
  this is worth doing carefully so the frontend/backend contract stays in
  sync, and it's a good thing to point to in an interview as "type safety
  across the stack"
- Polling is fine for ticket status updates given the scope of this project —
  no need for websockets unless you want the extra complexity as a stretch
  goal later
- Use badges/color-coding for category and urgency consistently across all
  pages (reviewers should be able to scan quickly)

## What to tell Claude Code for this phase
- Build pages in this order: Review Queue first (it's the core product),
  then Submit Ticket, then Agent Trace, then Dashboard
- Mirror backend Pydantic schemas into TypeScript types before building
  components that consume them
- Keep styling simple/clean (a component library like shadcn/ui or basic
  Tailwind is fine) — the point is functional clarity, not visual polish
