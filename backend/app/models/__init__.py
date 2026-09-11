# Importing every model here registers it on Base.metadata (needed by Alembic autogenerate).
from app.models.agent_log import AgentLog
from app.models.base import Base
from app.models.customer import Customer
from app.models.draft_response import DraftResponse
from app.models.knowledge_base import KnowledgeBaseEntry
from app.models.knowledge_document import KnowledgeDocument
from app.models.model_prediction import ModelPrediction
from app.models.order import Order
from app.models.tenant import Tenant, User
from app.models.ticket import Ticket

__all__ = ["AgentLog", "Base", "Customer", "DraftResponse", "KnowledgeBaseEntry", "KnowledgeDocument", "ModelPrediction", "Order", "Tenant", "Ticket", "User"]
