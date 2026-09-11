from pydantic import BaseModel

from app.schemas.knowledge_base import RetrievedDoc


def ticket_text(subject: str, body: str) -> str:
    """What the classifiers and the knowledge search read. Training rows built from real
    tickets (scripts/export_feedback.py) use the same format."""
    return f"{subject}\n{body}"


class TicketState(BaseModel):
    """Shared LangGraph state (03-agent-architecture.md). Each node returns only the
    fields it changes."""

    ticket_id: str
    subject: str
    body: str
    order_id: str | None = None
    category: str | None = None
    category_confidence: float | None = None
    urgency: str | None = None
    urgency_confidence: float | None = None
    # Full documents, not just text as in the spec: the draft needs the content and the
    # trace needs ids + similarity scores
    retrieved_docs: list[RetrievedDoc] = []
    order_data: dict | None = None
    draft_text: str | None = None
    needs_escalation: bool | None = None
    escalation_reason: str | None = None

    @property
    def text(self) -> str:
        return ticket_text(self.subject, self.body)
