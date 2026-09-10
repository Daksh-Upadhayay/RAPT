# Build Phases — Instructions for Claude Code

Feed these one at a time, in order. Wait until each phase actually works
(run it, click through it, check the DB) before starting the next one.
At the start of every new Claude Code session/chat, paste `00-overview.md`
first for context, then the relevant phase doc(s) below.

---

## Phase 1: Postgres schema + FastAPI skeleton
**Docs to give Claude Code:** `00-overview.md`, `01-database-schema.md`,
`04-backend-api.md`

**Prompt:**
"Set up the backend project structure exactly as described in the backend
API doc. Create the Postgres schema from the database schema doc using
Alembic migrations (async SQLAlchemy models + Alembic setup). Implement the
`tickets` and `orders` routers with basic CRUD as described. Use
pydantic-settings for config. Do not implement agents, ML, or knowledge base
yet — just the schema, DB connection, and these two routers. Write pytest
tests for the endpoints you create."

**Done when:** you can POST a ticket and GET it back, orders table exists
and can be queried, migrations run cleanly from scratch.

---

## Phase 2: Seed data + train ML models
**Docs to give Claude Code:** `00-overview.md`, `01-database-schema.md`,
`02-ml-models.md`

**Prompt:**
"Write a Faker-based seeding script (`scripts/seed_orders.py`) that
populates the `customers` and `orders` tables with realistic e-commerce
data, per the schema doc. Then, per the ML models doc: help me find/prepare
a suitable public support-ticket dataset, write a training script for the
category classifier (TF-IDF + XGBoost baseline), and a training script for
the urgency classifier using the weak-supervision bootstrapping approach
described. Include train/val/test evaluation with precision/recall/F1 per
class. Save trained model artifacts and write simple `predict_category()`
and `predict_urgency()` inference functions."

**Done when:** you have trained model files, an evaluation report you
understand and can explain, and working inference functions.

---

## Phase 3: Knowledge base + pgvector RAG
**Docs to give Claude Code:** `00-overview.md`, `01-database-schema.md`,
`02-ml-models.md`, `04-backend-api.md`

**Prompt:**
"Implement the `knowledge_base` router and embedding pipeline as described.
Choose and confirm the embedding model dimension before finalizing the
pgvector column. Write ~20-30 knowledge base entries yourself (e-commerce
policy/FAQ content — order status explanations, refund policy, delivery
delay policy, cancellation policy, damaged item process) and a script to
embed and insert them. Implement a similarity search function that takes
ticket text and returns top-k relevant docs."

**Done when:** you can query the knowledge base with sample ticket text and
get back sensible matching docs.

---

## Phase 4: LangGraph agent flow
**Docs to give Claude Code:** `00-overview.md`, `03-agent-architecture.md`,
`01-database-schema.md`, `04-backend-api.md`

**Prompt:**
"Implement the LangGraph agent graph exactly as described in the agent
architecture doc — 5 nodes, the conditional edge for order lookup, and
logging every node's input/output to `agent_logs`. Wire ticket creation
(`POST /tickets`) to trigger this graph as a background task. Implement the
`agents.py` and `reviews.py` routers. Use the Pydantic tool schemas exactly
as specified."

**Done when:** creating a ticket via the API results in a full agent run,
visible in `agent_logs`, ending with a row in `draft_responses` awaiting
review.

---

## Phase 5: React frontend
**Docs to give Claude Code:** `00-overview.md`, `05-frontend.md`,
`04-backend-api.md`

**Prompt:**
"Build the React frontend per the frontend doc. Start with the Review Queue
page and Ticket Detail view (approve/edit draft), since that's the core
product. Then add Submit Ticket, Agent Trace view, and the Metrics
Dashboard in that order. Mirror the backend Pydantic schemas into TypeScript
types first."

**Done when:** you can submit a ticket through the UI, watch it get
processed, review/approve/edit the draft, and see it reflected on the
dashboard.

---

## Phase 6: Feedback loop
**Docs to give Claude Code:** `00-overview.md`, `02-ml-models.md`,
`01-database-schema.md`

**Prompt:**
"Add a `corrected_category` and `corrected_urgency` nullable field to
tickets, settable from the review screen if a reviewer disagrees with the
AI's triage. Write a script that pulls all corrected examples and appends
them to the training dataset, and document (in DECISIONS.md) how this would
feed a retraining cycle — an actual automated retrain loop is out of scope,
but the data pipeline for it should be real."

**Done when:** corrections are captured and there's a script that could
plausibly be run periodically to retrain with improved data.

---

## General tips while working through phases
- If Claude Code suggests deviating from a doc (e.g., a different library),
  decide deliberately and update the relevant doc + `DECISIONS.md` — don't
  let silent drift happen between what the docs say and what's built
- Ask Claude Code to explain non-obvious choices as it makes them, and log
  the good ones in `DECISIONS.md`
- Run and manually test after every phase — don't stack unverified phases
