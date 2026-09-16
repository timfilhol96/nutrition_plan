import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from conftest import FakeProvider
from nutrition.llm import (
    InvalidJSON,
    LLMBudgetExhausted,
    LLMUnavailable,
    OpenAICompatibleProvider,
    ProviderChain,
    ProviderError,
    ProviderTimeout,
    RateLimited,
    extract_json,
)

GOOD = json.dumps({"items": []})


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


def test_fallback_on_rate_limit_sets_cooldown():
    groq = FakeProvider("groq", [RateLimited("groq: rate limited"), GOOD])
    openrouter = FakeProvider("openrouter", [GOOD, GOOD])
    clock = Clock()
    cooldowns = {}
    chain = ProviderChain([groq, openrouter], cooldowns, cooldown_s=60, clock=clock)

    assert chain.complete_json("s", "u") == GOOD
    assert len(groq.calls) == 1 and len(openrouter.calls) == 1
    assert cooldowns["groq"] == pytest.approx(1060.0)

    # While cooling down, groq is skipped entirely.
    chain.complete_json("s", "u")
    assert len(groq.calls) == 1 and len(openrouter.calls) == 2

    # After the cooldown, groq is tried again.
    clock.now = 1061.0
    chain.complete_json("s", "u")
    assert len(groq.calls) == 2


def test_fallback_on_timeout_and_invalid_json():
    groq = FakeProvider("groq", [ProviderTimeout("groq: timeout"), "not json at all"])
    openrouter = FakeProvider("openrouter", [GOOD, GOOD])
    chain = ProviderChain([groq, openrouter], {})
    assert chain.complete_json("s", "u") == GOOD  # timeout -> fallback
    assert chain.complete_json("s", "u") == GOOD  # invalid JSON -> fallback
    assert len(openrouter.calls) == 2


def test_all_providers_failing_raises_llm_unavailable():
    chain = ProviderChain(
        [FakeProvider("a", [ProviderError("a: HTTP 500")]), FakeProvider("b", ["[]"])],
        {},
    )
    with pytest.raises(LLMUnavailable) as exc:
        chain.complete_json("s", "u")
    assert "a: HTTP 500" in str(exc.value)


def test_no_provider_raises_llm_unavailable():
    with pytest.raises(LLMUnavailable):
        ProviderChain([], {}).complete_json("s", "u")


def test_budget_caps_calls():
    provider = FakeProvider("groq", [GOOD, GOOD, GOOD])
    chain = ProviderChain([provider], {}, budget=2)
    chain.complete_json("s", "u")
    chain.complete_json("s", "u")
    with pytest.raises(LLMBudgetExhausted):
        chain.complete_json("s", "u")
    assert chain.calls == 2 and len(provider.calls) == 2


def test_extract_json_tolerates_code_fences():
    assert json.loads(extract_json('```json\n{"items": []}\n```')) == {"items": []}
    with pytest.raises(InvalidJSON):
        extract_json("Sure! Here is the JSON: {")
    with pytest.raises(InvalidJSON):
        extract_json("[1, 2]")


def _response(status, payload):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    return response


def test_openai_compatible_provider_request_and_status_mapping():
    provider = OpenAICompatibleProvider(
        "groq", "https://x/v1/", "KEY", "model-a", timeout_s=7
    )
    payload = {"choices": [{"message": {"content": GOOD}}]}
    with patch(
        "nutrition.llm.httpx.post", return_value=_response(200, payload)
    ) as post:
        assert provider.complete_json("sys", "usr") == GOOD
    assert post.call_args.args[0] == "https://x/v1/chat/completions"
    body = post.call_args.kwargs["json"]
    assert body["model"] == "model-a"
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert post.call_args.kwargs["timeout"] == 7
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer KEY"

    with patch("nutrition.llm.httpx.post", return_value=_response(429, {})):
        with pytest.raises(RateLimited):
            provider.complete_json("s", "u")
    with patch("nutrition.llm.httpx.post", return_value=_response(503, {})):
        with pytest.raises(ProviderError):
            provider.complete_json("s", "u")
    with patch("nutrition.llm.httpx.post", side_effect=httpx.ReadTimeout("slow")):
        with pytest.raises(ProviderTimeout):
            provider.complete_json("s", "u")


def test_provider_errors_include_the_response_message():
    provider = OpenAICompatibleProvider("groq", "https://x/v1", "KEY", "gone-model")
    body = {
        "error": {
            "message": "The model `gone-model` does not exist",
            "code": "model_not_found",
        }
    }
    with patch("nutrition.llm.httpx.post", return_value=_response(404, body)):
        with pytest.raises(ProviderError) as exc:
            provider.complete_json("s", "u")
    assert "HTTP 404 (The model `gone-model` does not exist)" in str(exc.value)

    with patch(
        "nutrition.llm.httpx.post", return_value=_response(429, {"error": "slow down"})
    ):
        with pytest.raises(RateLimited) as exc:
            provider.complete_json("s", "u")
    assert "slow down" in str(exc.value)


def test_list_models():
    provider = OpenAICompatibleProvider("groq", "https://x/v1", "KEY", "m")
    payload = {"data": [{"id": "b-model"}, {"id": "a-model"}]}
    with patch("nutrition.llm.httpx.get", return_value=_response(200, payload)) as get:
        assert provider.list_models() == ["a-model", "b-model"]
    assert get.call_args.args[0] == "https://x/v1/models"
    with patch(
        "nutrition.llm.httpx.get", return_value=_response(401, {"error": "bad key"})
    ):
        with pytest.raises(ProviderError):
            provider.list_models()
