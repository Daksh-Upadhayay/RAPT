# Project Overview: AI Support Copilot for E-Commerce

## What this is
A multi-agent AI system that handles e-commerce customer support tickets end-to-end:
classifying incoming tickets, retrieving relevant knowledge, looking up order data,
drafting responses, and deciding when to escalate to a human. Every AI draft goes
through a human-in-the-loop review screen before being sent. Human edits/approvals
are logged and feed back into future model improvements.

## The wedge
Not a generic "AI support platform" — this is scoped specifically to **e-commerce
order support**: order status, refunds, damaged items, delivery delays, cancellations,
and general product questions. The narrow scope is intentional — it makes the demo
believable and the ML/agent design concrete instead of hand-wavy.

## Why this project (for interviews / resume framing)
- Combines trained ML models (not just LLM prompting) with agentic orchestration
- Uses a real production pattern: human-in-the-loop review + feedback loop for
  continuous improvement
- Full stack: Postgres (+pgvector), FastAPI + Pydantic, LangGraph, React
- Demoable end-to-end: submit a ticket → watch agents work → review/edit draft →
  see metrics update on a dashboard

## Tech stack
| Layer | Choice | Why |
|---|---|---|
| Backend framework | FastAPI | async support, plays well with Pydantic |
| Validation / schemas | Pydantic | used for API contracts AND agent tool schemas |
| Agent orchestration | LangGraph | stateful, branching flows (needed for escalation logic) |
| Database | PostgreSQL + pgvector | relational data + embeddings in one place |
| ML models | scikit-learn / XGBoost (baseline), optional DistilBERT fine-tune | fast to train, real evaluation story |
| Frontend | React + Recharts | ticket review UI + metrics dashboard |
| Experiment tracking | MLflow (optional, nice-to-have) | model versioning story for interviews |

## The five agents (high level — full detail in 03-agent-architecture.md)
1. **Triage Agent** — classifies ticket category + urgency using trained ML models
2. **Knowledge Agent** — RAG retrieval over the knowledge base (pgvector)
3. **Order Lookup Tool** — queries the mock orders table for order-specific tickets
4. **Draft Agent** — generates a response grounded in retrieved knowledge/order data
5. **Escalation Agent** — decides auto-send vs. human review based on urgency/confidence/refund amount

## How to use this documentation set with Claude Code
Feed the docs in this order, one phase at a time, per `06-build-phases.md`. Don't
paste all docs into one prompt — each phase prompt should reference only the docs
relevant to that phase, so Claude Code isn't overloaded with irrelevant context.

Files in this set:
- `00-overview.md` (this file) — give this at the START of every new Claude Code session for context
- `01-database-schema.md` — schema reference, used across most phases
- `02-ml-models.md` — Phase 2
- `03-agent-architecture.md` — Phase 4
- `04-backend-api.md` — Phases 1, 3, 4
- `05-frontend.md` — Phase 5
- `06-build-phases.md` — the actual instructions/prompts to give Claude Code, phase by phase
- `DECISIONS.md` — you and Claude Code update this together as choices get made
