# Database Schema (PostgreSQL + pgvector)

## Extension required
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Tables

Every table except `tenants` has `tenant_id UUID NOT NULL -> tenants.id` (Phase 7). Its
default is the current transaction's tenant (`app.tenant_id`), and row-level security
limits the API's database role to that tenant's rows. References between tenant tables
are composite, `(tenant_id, x_id) -> x(tenant_id, id)`, so no row can point at another
tenant's row. Customer email is unique per tenant. See DECISIONS.md, Phase 7.

### `tenants`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT | the business's name |
| slug | TEXT | unique; used by the operator CLI and scripts (`--tenant acme`) |
| created_at | TIMESTAMPTZ | default now() |

### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| tenant_id | UUID FK -> tenants.id | one tenant per user |
| email | TEXT | unique across tenants (the login form has no tenant field); stored lowercase |
| name | TEXT | |
| password_hash | TEXT | argon2id |
| role | TEXT | `admin`, `reviewer` |
| is_active | BOOLEAN | default true |
| password_changed_at | TIMESTAMPTZ | tokens issued before this are rejected |
| last_login_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | default now() |

### `customers`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT | |
| email | TEXT | unique per tenant |
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
| corrected_category | TEXT | nullable — reviewer's category when it differs from the model's (Phase 6); same allowed values as `category` |
| corrected_urgency | TEXT | nullable — reviewer's urgency when it differs from the model's (Phase 6) |
| corrected_by | TEXT | nullable — reviewer who made the correction |
| corrected_at | TIMESTAMPTZ | nullable — when the correction was made |
| created_at | TIMESTAMPTZ | default now() |
| updated_at | TIMESTAMPTZ | |

### `knowledge_base`
Created in Phase 3 by its own migration (`a3f9c1d27e45`, which also runs
`CREATE EXTENSION vector`). Embeddings come from `BAAI/bge-small-en-v1.5`
(384 dimensions; `all-MiniLM-L6-v2` until Phase 4); see DECISIONS.md, Phases 3 and 4.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| title | TEXT | |
| content | TEXT | policy/FAQ text |
| embedding | VECTOR(384) | embedding of "title. content", unit length; HNSW index with cosine distance |
| created_at | TIMESTAMPTZ | default now() |

### `kb_documents` (Phase 9)
Help documents a tenant uploaded or pasted; their sections are `knowledge_base` rows.
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| tenant_id | UUID FK -> tenants.id | |
| title | TEXT | |
| source | TEXT | `upload`, `paste` |
| filename | TEXT | nullable (pasted text) |
| content | TEXT | extracted text, headings as Markdown `#` lines |
| content_hash | TEXT | sha256 of `content`; the same document can't be added twice per tenant |
| status | TEXT | `processing`, `ready`, `failed` |
| error | TEXT | nullable — why processing failed |
| section_count | INTEGER | |
| uploaded_by | TEXT | the admin's email |
| created_at | TIMESTAMPTZ | default now() |

`knowledge_base` also has `document_id` (nullable, same-tenant FK to `kb_documents`,
ON DELETE CASCADE) and `position` (order within the document).

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
| reviewer_id | TEXT | nullable — the signed-in reviewer's email (Phase 7; a free-text placeholder before) |
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
- `embedding` column dimension (384) must match the embedding model (`EMBEDDING_DIM` in `app/core/config.py`); switching to a model with another size needs a new migration and a re-embed
