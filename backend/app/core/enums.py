"""Allowed values for enum-like TEXT columns.

Single source of truth: the ORM models turn these into CHECK constraints and the
Pydantic schemas use them for request/response validation.
"""

from enum import StrEnum


class OrderStatus(StrEnum):
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


class TicketCategory(StrEnum):
    ORDER_STATUS = "order_status"
    REFUND_REQUEST = "refund_request"
    DAMAGED_ITEM = "damaged_item"
    DELIVERY_DELAY = "delivery_delay"
    PRODUCT_QUESTION = "product_question"
    CANCELLATION = "cancellation"


class TicketUrgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    RESOLVED = "resolved"


class AgentName(StrEnum):
    TRIAGE = "triage"
    KNOWLEDGE = "knowledge"
    ORDER_LOOKUP = "order_lookup"
    DRAFT = "draft"
    ESCALATION = "escalation"


class ModelName(StrEnum):
    CATEGORY_CLASSIFIER = "category_classifier"
    URGENCY_CLASSIFIER = "urgency_classifier"


class UserRole(StrEnum):
    ADMIN = "admin"  # also manages the tenant (reviewers, knowledge base)
    REVIEWER = "reviewer"


class DocumentStatus(StrEnum):
    PROCESSING = "processing"  # being split into sections and embedded
    READY = "ready"
    FAILED = "failed"


class DocumentSource(StrEnum):
    UPLOAD = "upload"
    PASTE = "paste"
