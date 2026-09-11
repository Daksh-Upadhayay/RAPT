# RAPT frontend

The reviewer-facing app: review queue, ticket detail (approve or edit the AI draft),
submit ticket, agent trace and metrics dashboard. React 19 + TypeScript + Vite, styled
with Tailwind, data fetching and polling with TanStack Query, charts with Recharts.

## Run

Start the backend first (see `backend/README.md`, it listens on port 8000), then:

```bash
npm install
npm run dev        # http://localhost:5173
```

The app calls `/api/...`; the Vite server forwards those requests to the backend, so the
backend needs no CORS setup. If the backend runs somewhere else, set `API_URL`:

```bash
API_URL=http://localhost:8001 npm run dev
```

## Scripts

```bash
npm run build      # type-check (tsc -b) and build to dist/
npm run preview    # serve the build, with the same /api proxy
npm run lint       # oxlint
```

## Structure

```
src/
  index.css        design tokens (colour, type scale, radius) + the label typeface
  ui/              the UI kit: Button, Tag, Sheet, Field/Input/Select/Textarea, Segmented,
                   Meter, PageHeader, Loading/ErrorNotice/EmptyState, icons. No data
                   fetching, no business rules; import from '../ui'
  features/        one folder per area; each owns its data hooks and components and
                   exports its public pieces from index.ts
    tickets/       useTicket, useAgentTrace, tags, TicketStrip (queue row), TicketLabel (header)
    review/        useReviewQueue, useApproveDraft, useCorrectTriage, DraftEditor,
                   TriageCard, OrderSlip, GroundingList, ReviewPanel
    trace/         run grouping + log parsing (model.ts), TraceTimeline
    intake/        SubmitTicketForm, CustomerPicker
    metrics/       MetricsOverview, charts, ChartCard, chart theme
    auth/          useSession, useLogin, useLogout, LoginForm, RequireSession (route guard), UserMenu
  pages/           thin: compose features into a screen, handle the URL
  app/             AppShell (header + nav), queryClient
  api/             fetch wrapper (client.ts) + one module per backend resource
  lib/format.ts    labels, colours, number/date formatting
  types/index.ts   TypeScript mirrors of the backend's Pydantic schemas
```

Rules of thumb: pages import from `features/*` and `ui`; features import from `ui`,
`api`, `lib` and other features' `index.ts`; `ui` imports nothing app-specific.
Components use token classes (`bg-paper`, `text-ink-2`, `border-line`, `bg-accent`),
never raw hex or Tailwind's stock palette.

## Design

"Dispatch desk": the look of parcel logistics. White label stock (`paper`) on a
depot-grey page (`ground`), black print (`ink`), postal yellow (`accent`) for the
primary action and anything needing attention, stop red (`danger`) for escalation only.
One typeface, Archivo, whose width axis gives the signature treatment: ticket subjects
and page titles in heavy expanded type (`type-label`). The agent trace reads like a
carrier's tracking history.

## Signing in

Every page except `/login` sits behind `RequireSession`. The session is an httpOnly
cookie set by `POST /auth/login`, so the app never sees the token; `useSession` reads
`GET /auth/me`. Any 401 (expired, signed out elsewhere, password reset) marks the user
signed out and sends them back to `/login?next=…`. Requests that change something carry
the `X-RAPT-CSRF` header (api/client.ts). Accounts come from the operator CLI
(`backend/scripts/tenants.py`).

## Keeping the types in sync

`src/types/index.ts` is written by hand. `backend/tests/test_frontend_types.py` compares
it with the backend's OpenAPI schema: field names, optional request fields and enum
values. So a schema change without the matching TypeScript change fails the backend
tests.
