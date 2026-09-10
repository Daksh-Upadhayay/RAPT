# Database Schema (PostgreSQL + pgvector)

## Extension required
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Tables

### `customers`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT | |
| email | TEXT | unique |
| created_at | TIMESTAMPTZ | default now() |

### `orders`
Mock e-commerce order data, seeded with Faker.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| customer_id | UUID FK -> customers.id | |
| item_name | TEXT | |
| status | TEXT | enum-like: `processing`, `shipped`, `delivered`, `delayed`, `cancelled` |
| tracking_number | TEXT | nullable |
| amount | NUMERIC(10,2) | |
| order_date | DATE | |
| expected_delivery | DATE | nullable |

### `tickets`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| customer_id | UUID FK -> customers.id | |
| order_id | UUID FK -> orders.id | nullable — not all tickets are order-specific |
| subject | TEXT | |
| body | TEXT | the raw customer message |
| category | TEXT | nullable until triaged: `order_status`, `refund_request`, `damaged_item`, `delivery_delay`, `product_question`, `cancellation` |
| urgency | TEXT | nullable until triaged: `low`, `medium`, `high` |
| status | TEXT | `new`, `in_progress`, `awaiting_review`, `resolved` (no `escalated` — escalated tickets stay `awaiting_review`, see `needs_escalation`) |
| needs_escalation | BOOLEAN | nullable until the Escalation Agent runs |
| escalation_reason | TEXT | nullable — which escalation rule fired |
| created_at | TIMESTAMPTZ | default now() |
| updated_at | TIMESTAMPTZ | |

### `knowledge_base`
**Deferred to Phase 3** — created in its own migration (together with
`CREATE EXTENSION vector`) once the embedding model, and therefore the vector
dimension, is chosen. Not part of the Phase 1 migration.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| title | TEXT | |
| content | TEXT | policy/FAQ text |
| embedding | VECTOR(1536) | dimension depends on embedding model chosen |
| created_at | TIMESTAMPTZ | default now() |

### `agent_logs`
Tracks every agent step for the "agent trace view" in the frontend.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| ticket_id | UUID FK -> tickets.id | |
| agent_name | TEXT | `triage`, `knowledge`, `order_lookup`, `draft`, `escalation` |
| input | JSONB | what the agent received |
| output | JSONB | what the agent produced |
| tool_calls | JSONB | nullable — any tool/function calls made |
| duration_ms | INTEGER | nullable |
| created_at | TIMESTAMPTZ | default now() |

### `draft_responses`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| ticket_id | UUID FK -> tickets.id | |
| draft_text | TEXT | AI-generated draft |
| approved | BOOLEAN | nullable until reviewed |
| edited_text | TEXT | nullable — filled if reviewer edits before sending |
| reviewer_id | TEXT | nullable — who reviewed it (can be a placeholder for now, no auth system needed) |
| reviewed_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | default now() |

### `model_predictions`
Logs every ML model prediction for traceability + future retraining.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| ticket_id | UUID FK -> tickets.id | |
| model_name | TEXT | `category_classifier`, `urgency_classifier` |
| model_version | TEXT | e.g. `v1`, `v2` — bump when retrained |
| prediction | TEXT | |
| confidence | FLOAT | |
| created_at | TIMESTAMPTZ | default now() |

## Relationships summary
- `customers` 1—N `orders`
- `customers` 1—N `tickets`
- `orders` 1—N `tickets` (nullable FK)
- `tickets` 1—N `agent_logs`
- `tickets` 1—N `draft_responses`
- `tickets` 1—N `model_predictions`

## Notes for Claude Code
- Use Alembic for migrations from the start — don't hand-write raw SQL migrations
- Use UUID primary keys (not serial ints) — generate with `uuid4()` at the app layer or `gen_random_uuid()` at the DB layer
- `embedding` column dimension must match whatever embedding model gets chosen in `02-ml-models.md` — confirm before creating the migration
