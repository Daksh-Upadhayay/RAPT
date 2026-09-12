"""The frontend's hand-written API types (frontend/src/types/index.ts) must match the
backend's Pydantic schemas. Compared through the OpenAPI schema: every TypeScript
interface named after a schema has exactly its fields, and the enum lists match."""

import re
from pathlib import Path

import pytest

from app.main import app

TYPES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "index.ts"

# Schemas the frontend consumes; each needs a TypeScript interface of the same name
EXPECTED = {
    "CustomerResponse",
    "OrderResponse",
    "TicketCreate",
    "TicketResponse",
    "TicketDetailResponse",
    "AgentLogResponse",
    "DraftResponseRead",
    "LoginRequest",
    "MeResponse",
    "ReviewEditRequest",
    "TriageCorrectionRequest",
    "KnowledgeBaseResponse",
    "KnowledgeBaseUpdate",
    "KnowledgePasteRequest",
    "KnowledgeDocumentResponse",
    "KnowledgeDocumentDetail",
    "KnowledgeUploadResult",
    "KnowledgeSearchRequest",
    "CustomerCreate",
    "TeamMember",
    "InviteRequest",
    "MemberUpdate",
    "PasswordIssued",
    "ContactFormInfo",
    "ContactRequest",
    "ContactReceipt",
    "TenantSettings",
    "TenantSettingsUpdate",
    "MetricsSummary",
    "CategoryCount",
    "DailyEscalation",
    "ReviewOutcome",
    "CategoryResolution",
}

ENUM_CONSTANTS = {
    "TicketCategory": "TICKET_CATEGORIES",
    "TicketUrgency": "TICKET_URGENCIES",
    "TicketStatus": "TICKET_STATUSES",
    "AgentName": "AGENT_NAMES",
    "UserRole": "USER_ROLES",
    "DocumentStatus": "DOCUMENT_STATUSES",
    "DocumentSource": "DOCUMENT_SOURCES",
    "TicketChannel": "TICKET_CHANNELS",
}


def interfaces(source: str) -> dict[str, tuple[set[str], set[str]]]:
    """Interface name -> (all fields, optional fields), with `extends` merged in."""
    raw = {}
    for name, parent, body in re.findall(r"export interface (\w+)(?: extends (\w+))? \{\n(.*?)\n\}", source, re.DOTALL):
        fields = re.findall(r"^  (\w+)(\??):", body, re.MULTILINE)
        raw[name] = (parent, {f for f, _ in fields}, {f for f, opt in fields if opt})
    merged = {}
    for name, (parent, fields, optional) in raw.items():
        if parent:
            fields, optional = fields | raw[parent][1], optional | raw[parent][2]
        merged[name] = (fields, optional)
    return merged


@pytest.fixture(scope="module")
def source() -> str:
    return TYPES_TS.read_text()


@pytest.fixture(scope="module")
def schemas() -> dict:
    return app.openapi()["components"]["schemas"]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_interface_matches_schema(name: str, source: str, schemas: dict) -> None:
    ts = interfaces(source)
    assert name in ts, f"frontend/src/types/index.ts has no interface {name}"
    fields, optional = ts[name]
    schema = schemas[name]
    assert fields == set(schema["properties"]), f"{name}: field names differ from the Pydantic schema"
    # A field the API may omit from a request must be optional in TypeScript, and vice versa
    if name.endswith(("Create", "Request")):
        assert optional == set(schema["properties"]) - set(schema.get("required", [])), f"{name}: optional fields differ"


@pytest.mark.parametrize(("enum", "constant"), sorted(ENUM_CONSTANTS.items()))
def test_enum_values_match(enum: str, constant: str, source: str, schemas: dict) -> None:
    match = re.search(rf"export const {constant} = \[(.*?)\] as const", source, re.DOTALL)
    assert match, f"{constant} not found"
    assert re.findall(r"'(\w+)'", match.group(1)) == schemas[enum]["enum"]


def test_order_status_union_matches(source: str, schemas: dict) -> None:
    match = re.search(r"export type OrderStatus = (.*)", source)
    assert match
    assert re.findall(r"'(\w+)'", match.group(1)) == schemas["OrderStatus"]["enum"]
