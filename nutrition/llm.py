"""LLM providers behind OpenAI-compatible chat endpoints, with fallback."""

import json
import time
from typing import Callable, Protocol

import httpx


class LLMUnavailable(Exception):
    """Every provider failed, or none is configured."""


class LLMBudgetExhausted(LLMUnavailable):
    """The per-session cap on LLM calls was reached."""


class ProviderError(Exception):
    """A provider failed in a way that should move the chain to the next one."""


class RateLimited(ProviderError):
    pass


class ProviderTimeout(ProviderError):
    pass


class InvalidJSON(ProviderError):
    pass


class LLMProvider(Protocol):
    name: str

    def complete_json(self, system: str, user: str) -> str:
        """Return the assistant message content, expected to be a JSON document."""
        ...


class OpenAICompatibleProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 20.0,
        extra_headers: dict[str, str] | None = None,
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self.extra_headers = extra_headers or {}

    def complete_json(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", **self.extra_headers}
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"{self.name}: timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name}: {exc}") from exc
        if response.status_code == 429:
            raise RateLimited(f"{self.name}: rate limited")
        if response.status_code != 200:
            raise ProviderError(f"{self.name}: HTTP {response.status_code}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{self.name}: malformed response") from exc
        return content or ""


def extract_json(text: str) -> str:
    """Return the JSON object in `text` (tolerating ``` fences) or raise InvalidJSON."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        stripped = "\n".join(lines[1:]).rstrip("`").strip()
    try:
        parsed = json.loads(stripped)
    except ValueError as exc:
        raise InvalidJSON(f"invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise InvalidJSON("invalid JSON: expected an object")
    return stripped


class ProviderChain:
    """Try providers in order; skip rate-limited ones for a cooldown period.

    `cooldowns` maps provider name -> timestamp until which it is skipped. The
    app passes a dict living in st.session_state so cooldowns persist across
    reruns. `budget` caps the number of complete_json calls; `calls` counts
    them so the caller can charge them to the session.
    """

    def __init__(
        self,
        providers: list[LLMProvider],
        cooldowns: dict[str, float],
        cooldown_s: float = 60.0,
        budget: int | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.providers = providers
        self.cooldowns = cooldowns
        self.cooldown_s = cooldown_s
        self.budget = budget
        self.clock = clock
        self.calls = 0

    def complete_json(self, system: str, user: str) -> str:
        if not self.providers:
            raise LLMUnavailable("no LLM provider configured")
        if self.budget is not None and self.calls >= self.budget:
            raise LLMBudgetExhausted("LLM call cap reached")
        self.calls += 1

        now = self.clock()
        errors = []
        for provider in self.providers:
            if self.cooldowns.get(provider.name, 0) > now:
                errors.append(f"{provider.name}: cooling down")
                continue
            try:
                return extract_json(provider.complete_json(system, user))
            except RateLimited as exc:
                self.cooldowns[provider.name] = now + self.cooldown_s
                errors.append(str(exc))
            except ProviderError as exc:
                errors.append(str(exc))
        raise LLMUnavailable("; ".join(errors))
