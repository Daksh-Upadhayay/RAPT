from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.agents.drafter import (
    ClaudeDrafter,
    DraftError,
    GeminiDrafter,
    build_user_prompt,
)
from app.agents.escalation import EscalationInput, decide_escalation
from app.schemas.knowledge_base import RetrievedDoc

CALM = EscalationInput(
    text="Does the lamp come in white?",
    category="product_question",
    category_confidence=0.95,
    urgency="low",
    urgency_confidence=0.9,
    order_amount=None,
)


def with_(**changes) -> EscalationInput:
    return EscalationInput(**{**CALM.__dict__, **changes})


def test_no_rule_fires_for_a_calm_confident_ticket() -> None:
    decision = decide_escalation(CALM)
    assert decision.needs_escalation is False
    assert decision.reason is None


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (with_(urgency="high", urgency_confidence=0.93), "Urgency classified high (confidence 0.93)"),
        (with_(category_confidence=0.45), "Low category confidence (0.45 < 0.6)"),
        (with_(urgency_confidence=0.5), "Low urgency confidence (0.50 < 0.6)"),
        (with_(category="refund_request", order_amount=149.99), "Refund request on a $149.99 order (over $100)"),
        (with_(text="The charger started smoking last night."), "Strong urgency signal in the text: safety"),
    ],
)
def test_each_rule_escalates_with_its_reason(data: EscalationInput, expected: str) -> None:
    decision = decide_escalation(data)
    assert decision.needs_escalation is True
    assert expected in decision.reason


def test_refund_at_or_under_threshold_is_not_escalated() -> None:
    assert decide_escalation(with_(category="refund_request", order_amount=100.0)).needs_escalation is False


def test_all_fired_rules_are_reported() -> None:
    decision = decide_escalation(with_(urgency="high", urgency_confidence=0.55, category_confidence=0.4))
    assert decision.reason.count(";") == 2


def test_user_prompt_contains_order_and_entries() -> None:
    doc = RetrievedDoc(id="1", title="Refund timelines", content="5-10 business days.", similarity=0.71)
    prompt = build_user_prompt("Refund", "Where is my refund?", {"status": "delivered"}, [doc])
    assert "status: delivered" in prompt
    assert '<entry title="Refund timelines" similarity="0.71">' in prompt
    assert "No order is linked" in build_user_prompt("Hi", "Hello", None, [])


class StubMessages:
    """Records the request and returns a canned response in the SDK's shape."""

    def __init__(self, stop_reason: str = "end_turn", text: str = "Hello from Claude") -> None:
        self.kwargs: dict | None = None
        self.response = SimpleNamespace(
            stop_reason=stop_reason,
            stop_details=None,
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
            model="claude-opus-5",
            usage=SimpleNamespace(input_tokens=900, output_tokens=120),
            _request_id="req_123",
            to_dict=lambda: {"id": "msg_1"},
        )

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def claude_drafter(messages: StubMessages) -> ClaudeDrafter:
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return ClaudeDrafter(client, model="claude-opus-5", effort="medium")


async def test_claude_drafter_request_and_result() -> None:
    messages = StubMessages()

    result = await claude_drafter(messages).draft("SYSTEM", "USER")

    assert result.text == "Hello from Claude"
    assert result.mode == "claude"
    assert result.details["usage"] == {"input_tokens": 900, "output_tokens": 120}
    kw = messages.kwargs
    assert kw["model"] == "claude-opus-5"
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["system"] == "SYSTEM"
    assert kw["messages"] == [{"role": "user", "content": "USER"}]
    assert kw["output_config"] == {"effort": "medium"}


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
async def test_claude_drafter_rejects_unusable_responses(stop_reason: str) -> None:
    with pytest.raises(DraftError):
        await claude_drafter(StubMessages(stop_reason=stop_reason)).draft("SYSTEM", "USER")


def gemini_response(finish=genai_types.FinishReason.STOP, text="Hello from Gemini", blocked=None):
    return genai_types.GenerateContentResponse(
        candidates=[
            genai_types.Candidate(
                content=genai_types.Content(role="model", parts=[genai_types.Part(text=text)]), finish_reason=finish
            )
        ],
        prompt_feedback=genai_types.GenerateContentResponsePromptFeedback(block_reason=blocked) if blocked else None,
        usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=800, candidates_token_count=110, thoughts_token_count=40
        ),
        model_version="gemini-3.8-flash",
    )


class StubGeminiModels:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response, self.error, self.kwargs = response, error, None

    async def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def gemini_drafter(models: StubGeminiModels) -> GeminiDrafter:
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return GeminiDrafter(client, model="gemini-3.8-flash", thinking_level="low")


async def test_gemini_drafter_request_and_result() -> None:
    models = StubGeminiModels(gemini_response())

    result = await gemini_drafter(models).draft("SYSTEM", "USER")

    assert result.text == "Hello from Gemini"
    assert result.mode == "gemini" and result.model == "gemini-3.8-flash"
    assert result.details["usage"] == {"input_tokens": 800, "output_tokens": 110, "thinking_tokens": 40}
    assert models.kwargs["model"] == "gemini-3.8-flash"
    assert models.kwargs["contents"] == "USER"
    assert models.kwargs["config"].system_instruction == "SYSTEM"


@pytest.mark.parametrize(
    "models",
    [
        StubGeminiModels(gemini_response(finish=genai_types.FinishReason.MAX_TOKENS)),
        StubGeminiModels(gemini_response(finish=genai_types.FinishReason.SAFETY)),
        StubGeminiModels(gemini_response(blocked=genai_types.BlockedReason.SAFETY)),
        StubGeminiModels(gemini_response(text="  ")),
        StubGeminiModels(error=genai_errors.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded"}})),
    ],
    ids=["max_tokens", "safety_stop", "prompt_blocked", "empty", "quota_429"],
)
async def test_gemini_drafter_rejects_unusable_responses(models: StubGeminiModels) -> None:
    with pytest.raises(DraftError):
        await gemini_drafter(models).draft("SYSTEM", "USER")
