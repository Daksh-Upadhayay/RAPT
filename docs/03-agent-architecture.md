# Agent Architecture (LangGraph)

## Overview
A LangGraph state machine with 5 nodes (agents/tools). Each node reads from and
writes to a shared state object, and every node's input/output gets logged to
`agent_logs` (see `01-database-schema.md`) for the frontend's agent trace view.

## Shared state shape (Pydantic model)
```python
class TicketState(BaseModel):
    ticket_id: str
    subject: str
    body: str
    order_id: str | None = None
    category: str | None = None
    category_confidence: float | None = None
    urgency: str | None = None
    urgency_confidence: float | None = None
    retrieved_docs: list[RetrievedDoc] = []   # as built: full docs, not just text (see DECISIONS.md Phase 4)
    order_data: dict | None = None
    draft_text: str | None = None
    needs_escalation: bool | None = None
    escalation_reason: str | None = None
```

## Node 1: Triage Agent
- **Input:** `subject`, `body`
- **Action:** calls `predict_category()` and `predict_urgency()` (the trained
  models from `02-ml-models.md`) as tools — NOT an LLM call
- **Output:** updates `category`, `category_confidence`, `urgency`,
  `urgency_confidence`
- **Logs:** input text, model outputs + confidences, model_version used

## Node 2: Knowledge Agent
- **Input:** `category`, `body`
- **Action:** embeds the ticket body, performs a pgvector similarity search
  against `knowledge_base`, retrieves top-k (k=3) relevant docs
- **Output:** updates `retrieved_docs`
- **Logs:** query embedding metadata, retrieved doc IDs + similarity scores

## Node 3: Order Lookup Tool
- **Input:** `order_id` (if present — this node is skipped if the ticket has
  no associated order)
- **Action:** queries the `orders` table for status/tracking/amount
- **Output:** updates `order_data`
- **Logs:** query params, result (or "no order linked")
- **Conditional edge:** if `order_id` is None, skip straight to Draft Agent

## Node 4: Draft Agent
- **Input:** `body`, `retrieved_docs`, `order_data`
- **Action:** LLM call, prompted to draft a response ONLY using the retrieved
  knowledge and order data provided — explicitly instruct the model not to
  invent policy details or order info not present in the context
- **Output:** updates `draft_text`
- **Logs:** full prompt sent, raw LLM output

## Node 5: Escalation Agent
- **Input:** `urgency`, `category_confidence`, `urgency_confidence`,
  `order_data` (specifically refund amount if `category == refund_request`)
- **Action:** rule-based decision (not an LLM call — keep this deterministic
  and explainable):
  - escalate if `urgency == "high"`
  - escalate if `category_confidence < 0.6` OR `urgency_confidence < 0.6`
  - escalate if category is `refund_request` AND `order_data.amount > 100`
    (threshold configurable)
  - as built, also: escalate if a strong urgency rule (safety, fraud, threat,
    repeat contact, hardship, deadline) fires on the text while the model did not
    say `high` — a deterministic safety net for urgency-model misses
  - otherwise: proceed to human review queue as normal (NOT auto-send — see
    note below)
- **Output:** updates `needs_escalation`, `escalation_reason`
- **Logs:** the decision and which rule triggered it

## Important design note: human-in-the-loop is ALWAYS on
Every draft goes to the `draft_responses` table with `approved = null` and
appears in the React review queue — the system never auto-sends a response
without a human clicking approve. "Escalation" specifically means flagging a
ticket as higher-priority / needing more careful human attention, not the
difference between automated-send vs. human-review. This keeps the demo
safe and realistic (real support automation tools work this way at first,
before trust is established).

## Graph structure
```
START -> Triage -> Knowledge -> [conditional: order_id present?]
                                    -> yes: Order Lookup -> Draft
                                    -> no: Draft
Draft -> Escalation -> END
```

## Tool definitions (Pydantic schemas for each tool the agents call)
Define these explicitly as Pydantic models so FastAPI/LangGraph tool-calling
has strict typed contracts:
- `CategoryPrediction(label: str, confidence: float, model_version: str)`
- `UrgencyPrediction(label: str, confidence: float, model_version: str)`
- `RetrievedDoc(id: str, title: str, content: str, similarity: float)`
- `OrderLookupResult(order_id: str, status: str, tracking_number: str | None, amount: float, expected_delivery: str | None)`
  — as built, also `item_name` and `order_date` so the draft can name the item (DECISIONS.md Phase 4)
- `EscalationDecision(needs_escalation: bool, reason: str | None)`

## What to tell Claude Code for this phase
- Build the LangGraph graph with these 5 nodes and the conditional edge exactly
  as described
- Each node function should: (1) do its work, (2) write a row to `agent_logs`,
  (3) return the updated state
- Keep the Escalation Agent's logic as plain Python rules, not an LLM call —
  this needs to be deterministic and explainable
- Reference `01-database-schema.md` for exact table/column names when writing
  logging code
