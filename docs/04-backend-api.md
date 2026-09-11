# Backend API (FastAPI + Pydantic)

## Structure
```
backend/
  app/
    main.py
    core/
      config.py        # env vars, settings via pydantic-settings
      db.py             # async SQLAlchemy engine/session setup
      enums.py          # allowed values for enum-like columns (shared by ORM + schemas)
    models/             # SQLAlchemy ORM models (mirrors 01-database-schema.md)
    schemas/            # Pydantic request/response models (separate from ORM models)
    routers/
      tickets.py
      orders.py
      knowledge_base.py
      agents.py         # trigger agent run, get agent trace
      reviews.py        # approve/edit draft responses
      metrics.py        # dashboard aggregate stats
    ml/
      category_model.py
      urgency_model.py
      embeddings.py
    agents/
      graph.py          # LangGraph definition (see 03-agent-architecture.md)
    services/           # business logic layer between routers and models/ml/agents
  alembic/               # migrations
  scripts/
    seed_orders.py       # Faker-based seeding script
    train_category_model.py
    train_urgency_model.py
  tests/                 # pytest, runs against a real Postgres test DB
  pyproject.toml         # dependencies, managed with uv (no requirements.txt)
  uv.lock
```

## Key principle: Pydantic schemas != ORM models
Keep SQLAlchemy models (`models/`) and Pydantic API schemas (`schemas/`) as
separate files/classes, even though they'll look similar. This is standard
FastAPI practice and worth doing correctly for the resume story ("understands
the separation between persistence layer and API contract layer").

## Core endpoints

### Tickets
- `POST /tickets` — create a new ticket (customer submits) — triggers the
  agent graph asynchronously after creation
- `GET /tickets` — list tickets, filterable by `status`, `category`, `urgency`
- `GET /tickets/{id}` — full ticket detail including linked order, draft,
  agent logs

### Agents
- `GET /tickets/{id}/agent-trace` — returns all `agent_logs` rows for a
  ticket, in order — powers the frontend's agent trace view
- `POST /tickets/{id}/rerun` — manually re-trigger the agent graph (useful
  for demos and debugging); 202, or 409 while a run is in progress. Reruns append
  new predictions, trace rows and a new draft; the newest draft is the one reviewed

### Reviews
- `GET /reviews/queue` — list tickets with `status = awaiting_review`
- `POST /reviews/{ticket_id}/approve` — mark draft approved, ticket resolved
  (body: `{"reviewer_id": str}`; 409 if the ticket isn't awaiting review or has no pending draft)
- `POST /reviews/{ticket_id}/edit` — submit edited text, mark approved with
  edits, ticket resolved

### Knowledge base
- `GET /knowledge-base` — list entries
- `POST /knowledge-base` — add entry (triggers embedding generation)

### Orders (read-only, seeded data)
- `GET /orders/{id}` — order lookup (used by the Order Lookup Tool internally,
  but also useful for the frontend to display order context)

### Customers (added in Phase 5, for the Submit Ticket form)
- `GET /customers?search=&limit=` — customers whose name or email contains `search`
  (case-insensitive), by name; the first `limit` (default 10, max 50) without it
- `GET /customers/{id}` — one customer
- `GET /customers/{id}/orders` — the customer's orders, newest first

### Metrics
- `GET /metrics/summary?days=30` — aggregate stats for the dashboard: avg resolution
  time (overall and per category), escalation rate (overall and per day for the
  last `days` days), approval rate (approved-as-is vs. edited, split by escalation),
  tickets per category and per status. Definitions are in `app/services/metrics.py`.

## Pydantic schema examples
```python
class TicketCreate(BaseModel):
    customer_id: UUID
    subject: str
    body: str
    order_id: UUID | None = None

class TicketResponse(BaseModel):
    id: UUID
    subject: str
    body: str
    category: str | None
    urgency: str | None
    status: str
    created_at: datetime

class ReviewEditRequest(BaseModel):
    edited_text: str
    reviewer_id: str
```

## Async considerations
- Use async SQLAlchemy (`asyncpg` driver) throughout — this is the actual
  reason to use FastAPI over Flask, so don't skip it
- Ticket creation should return immediately (ticket saved, status = `new`)
  and kick off the agent graph as a background task
  (`BackgroundTasks` in FastAPI is sufficient for this project's scale — no
  need for Celery/queues)

## What to tell Claude Code for this phase
- Set up the FastAPI app structure exactly as above
- Use pydantic-settings for config (DB URL, embedding model choice, API keys)
- Use async SQLAlchemy + asyncpg
- Build routers incrementally — tickets + orders first (Phase 1), knowledge
  base + agents endpoints later (Phase 3-4)
