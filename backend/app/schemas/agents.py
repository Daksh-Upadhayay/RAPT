"""Agent tool schemas from 03-agent-architecture.md that don't live elsewhere.

CategoryPrediction / UrgencyPrediction are in app/schemas/prediction.py and RetrievedDoc
is in app/schemas/knowledge_base.py.
"""

from pydantic import BaseModel


class OrderLookupResult(BaseModel):
    order_id: str
    status: str
    tracking_number: str | None
    # float per the tool spec; the database and the orders API keep exact Decimals
    amount: float
    expected_delivery: str | None
    # Beyond the spec: lets the draft name the item and the order date
    item_name: str
    order_date: str


class EscalationDecision(BaseModel):
    needs_escalation: bool
    reason: str | None
