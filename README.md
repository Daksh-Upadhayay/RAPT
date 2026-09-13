# RAPT

An AI support copilot for e-commerce customer service. A 5-agent pipeline classifies
incoming tickets, retrieves relevant knowledge, looks up order data, drafts a response,
and decides when to escalate — every AI draft goes through human review before it's
sent, and reviewer edits feed back into retraining the models.

Live: a multi-tenant deployment for small businesses, hosted on Azure.

## How it works

1. **Triage Agent** — classifies ticket category (6 classes) and urgency (low/medium/high)
   using trained ML models, not LLM prompting
2. **Knowledge Agent** — RAG retrieval over a pgvector knowledge base
3. **Order Lookup Tool** — pulls order-specific data for the ticket
4. **Draft Agent** — writes a response grounded in the retrieved knowledge and order data
5. **Escalation Agent** — decides whether the draft needs priority human review, based on
   urgency, model confidence, and refund amount

A human reviewer approves or edits every draft before it goes out. Corrections are
exported, checked for eval leakage, and used to retrain and version-gate the classifiers
against held-out test sets before a new version is promoted.

## Results

- **Category classifier** (6-class, TF-IDF + XGBoost): 0.86 macro-F1 on a 120-ticket
  hand-written test set never used in training or tuning
- **Urgency classifier** (3-class, weak-supervision bootstrapped): 0.92 recall on
  high-urgency tickets at 0.85 precision, 0.80 accuracy, on a 55-ticket blind eval set
  written after the model was frozen
- **Knowledge retrieval** (bge-small-en-v1.5 embeddings over pgvector): 0.88 hit@1,
  1.00 hit@3, 0.94 MRR

See [docs/DECISIONS.md](docs/DECISIONS.md) for the full evaluation history, including
baselines and caveats.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, Pydantic, async SQLAlchemy |
| Agent orchestration | LangGraph |
| Database | PostgreSQL + pgvector, row-level security for multi-tenancy |
| ML | scikit-learn / XGBoost classifiers, sentence-transformers embeddings |
| Frontend | React 19, TypeScript, Vite, Tailwind, TanStack Query, Recharts |
| Auth | JWT (httpOnly cookie), DB-enforced tenant isolation via `SECURITY DEFINER` |
| Deployment | Docker Compose, Caddy (HTTPS), hosted on Azure |

## Multi-tenancy and security

Every table carries `tenant_id`, and Postgres row-level security — not application
code — keeps one tenant's data from leaking into another's. The API connects as a
restricted role (`rapt_app`) with no superuser or `BYPASSRLS`; the only cross-tenant
lookups (login, the public contact form) go through narrowly-scoped
`SECURITY DEFINER` functions.

## Getting started

- Backend setup: [backend/README.md](backend/README.md)
- Frontend setup: [frontend/README.md](frontend/README.md)
- Production deployment: [deploy/README.md](deploy/README.md)
- Architecture docs: [docs/](docs/)

## Project docs

- [docs/00-overview.md](docs/00-overview.md) — what this is and why
- [docs/01-database-schema.md](docs/01-database-schema.md) — schema reference
- [docs/02-ml-models.md](docs/02-ml-models.md) — classifier design
- [docs/03-agent-architecture.md](docs/03-agent-architecture.md) — the agent graph
- [docs/04-backend-api.md](docs/04-backend-api.md) — API reference
- [docs/05-frontend.md](docs/05-frontend.md) — frontend structure
- [docs/DECISIONS.md](docs/DECISIONS.md) — full build log and evaluation results
