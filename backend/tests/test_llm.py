"""Phase 8: the LLM provider chain, retries, tenant limits, contact masking, and resuming
interrupted runs. No network: providers are faked with httpx.MockTransport."""

import json

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import drafter as drafter_module
from app.agents.drafter import (
    ChainDrafter,
    ChainLink,
    DraftError,
    DraftResult,
    OfflineDrafter,
    OpenAICompatibleDrafter,
    build_user_prompt,
    mask_contact_details,
)
from app.agents.recovery import resume_unfinished_runs
from app.models import Customer, Ticket
from tests.conftest import FakeDrafter


def completion(text: str = "Hello from the model", finish: str = "stop", model: str = "openai/gpt-oss-120b") -> dict:
    return {
        "id": "chatcmpl-1",
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 700, "completion_tokens": 90},
    }


def provider(*responses, attempts: int = 2):
    """An OpenAICompatibleDrafter whose HTTP calls return `responses` in order."""
    calls: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAICompatibleDrafter("groq", client, "https://llm.test/v1", "key", "openai/gpt-oss-120b", "low", attempts=attempts), calls


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(drafter_module.asyncio, "sleep", instant)


async def test_request_shape_and_result() -> None:
    drafter, calls = provider(httpx.Response(200, json=completion()))

    result = await drafter.draft("SYSTEM", "USER")

    body = json.loads(calls[0].content)
    assert calls[0].url == "https://llm.test/v1/chat/completions"
    assert calls[0].headers["authorization"] == "Bearer key"
    assert body["messages"] == [{"role": "system", "content": "SYSTEM"}, {"role": "user", "content": "USER"}]
    assert body["reasoning_effort"] == "low" and body["max_completion_tokens"] == 4096
    assert (result.text, result.mode, result.model) == ("Hello from the model", "groq", "openai/gpt-oss-120b")
    assert result.details["usage"] == {"input_tokens": 700, "output_tokens": 90}


async def test_rate_limit_and_server_errors_are_retried() -> None:
    drafter, calls = provider(httpx.Response(429, headers={"retry-after": "1"}), httpx.Response(200, json=completion()))
    assert (await drafter.draft("S", "U")).text == "Hello from the model"
    assert len(calls) == 2

    drafter, calls = provider(httpx.TimeoutException("slow"), httpx.Response(200, json=completion()))
    assert (await drafter.draft("S", "U")).text == "Hello from the model"


async def test_long_retry_after_gives_up_for_the_next_provider() -> None:
    drafter, calls = provider(httpx.Response(429, headers={"retry-after": "120"}, json={"error": {"message": "slow down"}}))

    with pytest.raises(DraftError, match="429"):
        await drafter.draft("S", "U")
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("response", "match"),
    [
        (httpx.Response(401, json={"error": {"message": "Invalid API Key"}}), "401: Invalid API Key"),
        (httpx.Response(402, json={"error": {"message": "Payment required"}}), "402"),
        (httpx.Response(200, json=completion(finish="length")), "cut off"),
        (httpx.Response(200, json=completion(text="  ")), "no text"),
        (httpx.Response(200, json=completion(finish="content_filter")), "stopped early"),
    ],
)
async def test_unusable_responses_fail_without_retrying(response: httpx.Response, match: str) -> None:
    drafter, calls = provider(response, httpx.Response(200, json=completion()))

    with pytest.raises(DraftError, match=match):
        await drafter.draft("S", "U")
    assert len(calls) == 1


class Stub:
    def __init__(self, result: str | None = None, error: str | None = None):
        self.result, self.error, self.calls = result, error, 0

    async def draft(self, system: str, user: str, tenant: str | None = None) -> DraftResult:
        self.calls += 1
        if self.error:
            raise DraftError(self.error)
        return DraftResult(text=self.result, mode="stub", model="m")


async def test_chain_falls_through_to_the_first_working_provider() -> None:
    first, second = Stub(error="groq API error 503: overloaded"), Stub(result="Drafted by the second")
    chain = ChainDrafter([ChainLink("groq/a", first), ChainLink("groq/b", second)])

    result = await chain.draft("S", "U", "acme")

    assert result.text == "Drafted by the second"
    assert result.details["attempts"] == [
        {"provider": "groq/a", "error": "groq API error 503: overloaded"},
        {"provider": "groq/b", "ok": "drafted"},
    ]


async def test_provider_that_may_train_is_only_used_for_allowed_tenants() -> None:
    gemini = Stub(result="from gemini")
    chain = ChainDrafter([ChainLink("groq/a", Stub(error="down")), ChainLink("gemini/x", gemini, allowed_tenants=frozenset({"dev"}))])

    with pytest.raises(DraftError, match="gemini/x: not allowed for this tenant"):
        await chain.draft("S", "U", "acme")
    assert gemini.calls == 0
    assert (await chain.draft("S", "U", "dev")).text == "from gemini"


async def test_chain_reports_every_failure() -> None:
    chain = ChainDrafter([ChainLink("groq/a", Stub(error="429")), ChainLink("cerebras/b", Stub(error="402"))])

    with pytest.raises(DraftError, match=r"groq/a: 429; cerebras/b: 402"):
        await chain.draft("S", "U", "acme")


@pytest.fixture
def keys(monkeypatch):
    def set_keys(provider: str = "auto", **keys):
        monkeypatch.setattr(drafter_module.settings, "draft_provider", provider)
        for name in ("groq", "cerebras", "gemini", "anthropic"):
            value = keys.get(name)
            monkeypatch.setattr(drafter_module.settings, f"{name}_api_key", SecretStr(value) if value else None)
        drafter_module._default_drafter.cache_clear()
        return drafter_module.get_drafter()

    yield set_keys
    drafter_module._default_drafter.cache_clear()


def test_chain_order_follows_the_configured_keys(keys) -> None:
    drafter = keys(groq="g", cerebras="c", gemini="m", anthropic="a")

    assert [link.name for link in drafter.links] == [
        "groq/openai/gpt-oss-120b",
        "groq/qwen/qwen3.8-27b",
        "cerebras/gpt-oss-120b",
        "gemini/gemini-3.8-flash",
        "claude/claude-opus-5",
    ]
    gemini = drafter.links[3]
    assert gemini.allowed_tenants == frozenset({"dev"})
    assert all(link.allowed_tenants is None for link in drafter.links if link is not gemini)


def test_no_keys_or_offline_gives_the_placeholder(keys) -> None:
    assert isinstance(keys(), OfflineDrafter)
    assert isinstance(keys("offline", groq="g"), OfflineDrafter)


def test_pinning_one_provider(keys) -> None:
    assert [link.name for link in keys("cerebras", groq="g", cerebras="c").links] == ["cerebras/gpt-oss-120b"]
    with pytest.raises(RuntimeError, match="needs that provider's API key"):
        keys("claude", groq="g")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("write to ada.l+x@mail.co.uk please", "write to [email] please"),
        ("call +1 415 555 0100 today", "call [phone] today"),
        ("or (415) 555-0100", "or [phone]"),
        ("or 020 7946 0958", "or [phone]"),
        ("order 30019 and tracking 1Z999AA10123456784", "order 30019 and tracking 1Z999AA10123456784"),
        ("ref 4155550100 stays", "ref 4155550100 stays"),  # unbroken digit runs are usually order numbers
        ("delivered on 2026-09-11", "delivered on 2026-09-11"),
    ],
)
def test_mask_contact_details(text: str, expected: str) -> None:
    assert mask_contact_details(text) == expected


def test_prompt_masks_the_customer_message_only() -> None:
    prompt = build_user_prompt("Call me: +1 415 555 0100", "Email ada@x.io", {"tracking_number": "1Z999"}, [])
    assert "[phone]" in prompt and "[email]" in prompt and "1Z999" in prompt
    assert "ada@x.io" not in prompt


async def test_draft_step_passes_the_tenant(client, customer, drafter: FakeDrafter) -> None:
    await client.post("/tickets", json={"customer_id": str(customer.id), "subject": "Hi", "body": "Hello"})

    assert drafter.tenants == ["acme"]


async def test_interrupted_runs_are_resumed(session: AsyncSession, session_factory, customer: Customer, drafter: FakeDrafter) -> None:
    stuck = [Ticket(customer_id=customer.id, subject="Hi", body="Where is it?", status=s) for s in ("new", "in_progress")]
    done = Ticket(customer_id=customer.id, subject="Hi", body="Done", status="resolved")
    session.add_all([*stuck, done])
    await session.commit()

    resumed = await resume_unfinished_runs(session_factory, drafter)

    assert resumed == 2
    for ticket in stuck:
        await session.refresh(ticket)
        assert ticket.status == "awaiting_review"
    await session.refresh(done)
    assert done.status == "resolved"
