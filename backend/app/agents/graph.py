"""LangGraph definition (03-agent-architecture.md):

    START -> triage -> knowledge -> [order_id present?] -> yes: order_lookup -> draft
                                                        -> no: draft
    draft -> escalation -> END
"""

from langgraph.graph import END, START, StateGraph

from app.agents import nodes
from app.agents.nodes import AgentContext
from app.agents.state import TicketState


def route_after_knowledge(state: TicketState) -> str:
    return "order_lookup" if state.order_id else "draft"


def build_graph():
    graph = StateGraph(TicketState, context_schema=AgentContext)
    graph.add_node("triage", nodes.triage)
    graph.add_node("knowledge", nodes.knowledge)
    graph.add_node("order_lookup", nodes.order_lookup)
    graph.add_node("draft", nodes.draft)
    graph.add_node("escalation", nodes.escalation)

    graph.add_edge(START, "triage")
    graph.add_edge("triage", "knowledge")
    graph.add_conditional_edges("knowledge", route_after_knowledge, {"order_lookup": "order_lookup", "draft": "draft"})
    graph.add_edge("order_lookup", "draft")
    graph.add_edge("draft", "escalation")
    graph.add_edge("escalation", END)
    return graph.compile()


agent_graph = build_graph()
