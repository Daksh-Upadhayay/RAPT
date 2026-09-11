"""The five graph nodes. Each does its work, writes one agent_logs row, and returns only
the state fields it changed (03-agent-architecture.md)."""

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi.concurrency import run_in_threadpool
from langgraph.runtime import Runtime
from pydantic_core import to_jsonable_python
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.drafter import SYSTEM_PROMPT, Drafter, build_user_prompt
from app.agents.escalation import EscalationInput, escalation_rules, to_decision
from app.agents.state import TicketState
from app.core.config import EMBEDDING_DIM, settings
from app.core.enums import AgentName, ModelName
from app.ml.category_model import predict_category
from app.ml.urgency_model import predict_urgency
from app.models import AgentLog, DraftResponse, ModelPrediction, Order, Ticket
from app.schemas.agents import OrderLookupResult
from app.services.knowledge_base import search

TOP_K = 3


@dataclass
class AgentContext:
    """Per-run dependencies, passed to nodes through LangGraph's runtime context."""

    session: AsyncSession
    drafter: Drafter


@dataclass
class NodeResult:
    update: dict[str, Any]  # state changes returned to the graph
    output: dict[str, Any]  # what the node produced, for agent_logs.output
    tool_calls: list[dict[str, Any]] | None = None
    input: dict[str, Any] | None = None  # overrides the default input log (the state fields read)


NodeFn = Callable[[TicketState, AgentContext], Awaitable[NodeResult]]


def logged(agent: AgentName, reads: tuple[str, ...]) -> Callable[[NodeFn], Callable]:
    """Wrap a node so every run, successful or not, leaves an agent_logs row."""

    def decorator(fn: NodeFn) -> Callable:
        # No functools.wraps: LangGraph reads the node's signature to decide whether to
        # pass `runtime`, and wraps would make it see fn's (state, ctx) signature instead
        async def node(state: TicketState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
            session = runtime.context.session
            default_input = {field: getattr(state, field) for field in reads}
            started = time.perf_counter()
            try:
                result = await fn(state, runtime.context)
            except Exception as exc:
                await session.rollback()  # the failed node's own writes are discarded
                session.add(
                    AgentLog(
                        ticket_id=uuid.UUID(state.ticket_id),
                        agent_name=agent,
                        input=to_jsonable_python(default_input),
                        output={"error": f"{type(exc).__name__}: {exc}"},
                        duration_ms=round((time.perf_counter() - started) * 1000),
                    )
                )
                await session.commit()
                raise
            session.add(
                AgentLog(
                    ticket_id=uuid.UUID(state.ticket_id),
                    agent_name=agent,
                    input=to_jsonable_python(result.input or default_input),
                    output=to_jsonable_python(result.output),
                    tool_calls=to_jsonable_python(result.tool_calls),
                    duration_ms=round((time.perf_counter() - started) * 1000),
                )
            )
            # Commit per node: the node's writes land together with its log, and the
            # trace view can show progress while the run is still going
            await session.commit()
            return result.update

        node.__name__, node.__doc__ = fn.__name__, fn.__doc__
        return node

    return decorator


async def _ticket(session: AsyncSession, state: TicketState) -> Ticket:
    return await session.get_one(Ticket, uuid.UUID(state.ticket_id))


@logged(AgentName.TRIAGE, reads=("subject", "body"))
async def triage(state: TicketState, ctx: AgentContext) -> NodeResult:
    """Category + urgency from the trained classifiers (tools, not an LLM)."""
    # Model inference is CPU-bound: keep it off the event loop
    category = await run_in_threadpool(predict_category, state.text)
    urgency = await run_in_threadpool(predict_urgency, state.text)

    ticket = await _ticket(ctx.session, state)
    ticket.category, ticket.urgency = category.label, urgency.label
    ctx.session.add_all(
        ModelPrediction(
            ticket_id=ticket.id,
            model_name=name,
            model_version=p.model_version,
            prediction=p.label,
            confidence=p.confidence,
        )
        for name, p in ((ModelName.CATEGORY_CLASSIFIER, category), (ModelName.URGENCY_CLASSIFIER, urgency))
    )
    return NodeResult(
        update={
            "category": category.label,
            "category_confidence": category.confidence,
            "urgency": urgency.label,
            "urgency_confidence": urgency.confidence,
        },
        output={"category": category, "urgency": urgency},
        tool_calls=[
            {"tool": "predict_category", "input": {"text": state.text}, "output": category},
            {"tool": "predict_urgency", "input": {"text": state.text}, "output": urgency},
        ],
    )


@logged(AgentName.KNOWLEDGE, reads=("category", "subject", "body"))
async def knowledge(state: TicketState, ctx: AgentContext) -> NodeResult:
    """Top-k knowledge-base entries by embedding similarity (pgvector)."""
    docs = await search(ctx.session, state.text, k=TOP_K)
    hits = [{"id": d.id, "title": d.title, "similarity": d.similarity} for d in docs]
    return NodeResult(
        update={"retrieved_docs": docs},
        output={
            "query_embedding": {"model": settings.embedding_model, "dimensions": EMBEDDING_DIM},
            "retrieved": hits,
        },
        tool_calls=[{"tool": "knowledge_base_search", "input": {"query": state.text, "k": TOP_K}, "output": hits}],
    )


@logged(AgentName.ORDER_LOOKUP, reads=("order_id",))
async def order_lookup(state: TicketState, ctx: AgentContext) -> NodeResult:
    """Status, tracking and amount of the linked order (only runs when there is one)."""
    order = await ctx.session.get(Order, uuid.UUID(state.order_id))
    if order is None:
        result, output = None, {"result": "no order found"}
    else:
        result = OrderLookupResult(
            order_id=str(order.id),
            status=order.status,
            tracking_number=order.tracking_number,
            amount=float(order.amount),
            expected_delivery=order.expected_delivery.isoformat() if order.expected_delivery else None,
            item_name=order.item_name,
            order_date=order.order_date.isoformat(),
        )
        output = {"result": result}
    order_data = result.model_dump() if result else None
    return NodeResult(
        update={"order_data": order_data},
        output=output,
        tool_calls=[{"tool": "order_lookup", "input": {"order_id": state.order_id}, "output": order_data}],
    )


@logged(AgentName.DRAFT, reads=("body", "retrieved_docs", "order_data"))
async def draft(state: TicketState, ctx: AgentContext) -> NodeResult:
    """LLM draft grounded in the retrieved entries and the order record."""
    user_prompt = build_user_prompt(state.subject, state.body, state.order_data, state.retrieved_docs)
    result = await ctx.drafter.draft(SYSTEM_PROMPT, user_prompt)
    ctx.session.add(DraftResponse(ticket_id=uuid.UUID(state.ticket_id), draft_text=result.text))
    return NodeResult(
        update={"draft_text": result.text},
        input={"system_prompt": SYSTEM_PROMPT, "user_prompt": user_prompt},
        output={"draft_text": result.text, "mode": result.mode, "model": result.model, **result.details},
    )


@logged(AgentName.ESCALATION, reads=("urgency", "category", "category_confidence", "urgency_confidence", "order_data"))
async def escalation(state: TicketState, ctx: AgentContext) -> NodeResult:
    """Rule-based: flag the ticket for priority human attention (never auto-sends)."""
    data = EscalationInput(
        text=state.text,
        category=state.category,
        category_confidence=state.category_confidence,
        urgency=state.urgency,
        urgency_confidence=state.urgency_confidence,
        order_amount=state.order_data["amount"] if state.order_data else None,
    )
    rules_fired = escalation_rules(data)
    decision = to_decision(rules_fired)
    ticket = await _ticket(ctx.session, state)
    ticket.needs_escalation, ticket.escalation_reason = decision.needs_escalation, decision.reason
    return NodeResult(
        update={"needs_escalation": decision.needs_escalation, "escalation_reason": decision.reason},
        output={"decision": decision, "rules_fired": rules_fired},
    )
