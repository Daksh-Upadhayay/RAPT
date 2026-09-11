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

## Layout

```
src/
  types/index.ts   TypeScript mirrors of the backend's Pydantic schemas
  api/             fetch wrapper (client.ts) + one module per resource
  lib/             formatting, agent-trace parsing, reviewer identity, chart ink
  components/      badges, ticket card, draft editor, agent step card, charts, ...
  pages/           ReviewQueue, TicketDetail, SubmitTicket, AgentTrace, Dashboard
```

## Keeping the types in sync

`src/types/index.ts` is written by hand. `backend/tests/test_frontend_types.py` compares
it with the backend's OpenAPI schema: field names, optional request fields and enum
values. So a schema change without the matching TypeScript change fails the backend
tests.
