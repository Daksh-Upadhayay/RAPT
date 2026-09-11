"""Escalation Agent rules: plain Python, deterministic and explainable (no LLM).

Escalation never skips human review (every draft is reviewed); it flags the ticket for
higher-priority, more careful attention. Every rule that fires is reported, so the
reviewer sees all the reasons, not just the first.
"""

from dataclasses import dataclass

from app.core.config import settings
from app.core.enums import TicketCategory, TicketUrgency
from app.ml.weak_labels import strong_signals
from app.schemas.agents import EscalationDecision


@dataclass(frozen=True)
class EscalationInput:
    text: str
    category: str | None
    category_confidence: float | None
    urgency: str | None
    urgency_confidence: float | None
    order_amount: float | None  # None when no order is linked


def escalation_rules(data: EscalationInput) -> list[str]:
    """Human-readable reason for each rule that fires, in rule order."""
    min_conf = settings.escalation_min_confidence
    reasons = []
    if data.urgency == TicketUrgency.HIGH:
        reasons.append(f"Urgency classified high (confidence {data.urgency_confidence:.2f})")
    if data.category_confidence is not None and data.category_confidence < min_conf:
        reasons.append(f"Low category confidence ({data.category_confidence:.2f} < {min_conf})")
    if data.urgency_confidence is not None and data.urgency_confidence < min_conf:
        reasons.append(f"Low urgency confidence ({data.urgency_confidence:.2f} < {min_conf})")
    threshold = settings.refund_escalation_threshold
    if data.category == TicketCategory.REFUND_REQUEST and data.order_amount is not None and data.order_amount > threshold:
        reasons.append(f"Refund request on a ${data.order_amount:.2f} order (over ${threshold:.0f})")
    # Safety net for urgency-model misses: a strong urgency signal (safety risk, fraud,
    # threat, repeat contact, ...) escalates even when the model didn't say high
    if data.urgency != TicketUrgency.HIGH and (signals := strong_signals(data.text)):
        reasons.append(f"Strong urgency signal in the text: {', '.join(signals)}")
    return reasons


def to_decision(reasons: list[str]) -> EscalationDecision:
    return EscalationDecision(needs_escalation=bool(reasons), reason="; ".join(reasons) or None)


def decide_escalation(data: EscalationInput) -> EscalationDecision:
    return to_decision(escalation_rules(data))
