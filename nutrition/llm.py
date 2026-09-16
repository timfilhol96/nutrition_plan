"""LLM providers behind OpenAI-compatible chat endpoints, with fallback."""

import json
import re
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
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after  # seconds, when the provider said how long


class ProviderTimeout(ProviderError):
    pass


class InvalidJSON(ProviderError):
    pass


class LLMProvider(Protocol):
    name: str

    def complete_json(self, system: str, user: str) -> str:
        """Return the assistant message content, expected to be a JSON document."""
        ...


def error_message(response: httpx.Response) -> str:
    try:
        error = response.json().get("error")
        message = error.get("message") if isinstance(error, dict) else error
    except (ValueError, AttributeError):
        message = response.text
    return " ".join(str(message or "").split())


def error_detail(response: httpx.Response) -> str:
    """Short human-readable reason from an error response body."""
    message = error_message(response)
    return f"HTTP {response.status_code}" + (f" ({message[:300]})" if message else "")


def retry_after_seconds(response: httpx.Response) -> float | None:
    """How long the provider asked us to wait: Retry-After header, else the message."""
    try:
        header = response.headers.get("retry-after")
        if header:
            return float(header)
    except (TypeError, ValueError, AttributeError):
        pass
    # Groq: "Please try again in 7.66s" / "in 2m59.5s" / "in 350ms"
    match = re.search(
        r"try again in (?:(\d+)m)?([\d.]+)(ms|s)", error_message(response)
    )
    if not match:
        return None
    minutes, amount, unit = match.groups()
    seconds = float(amount) / (1000 if unit == "ms" else 1)
    return seconds + 60 * int(minutes or 0)


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
            raise RateLimited(
                f"{self.name}: rate limited, {error_detail(response)}",
                retry_after=retry_after_seconds(response),
            )
        if response.status_code != 200:
            raise ProviderError(f"{self.name}: {error_detail(response)}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{self.name}: malformed response") from exc
        return content or ""

    def list_models(self) -> list[str]:
        """IDs of the models this key can use (GET /models). Used by the eval probe."""
        response = httpx.get(
            f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout_s,
        )
        if response.status_code != 200:
            raise ProviderError(f"{self.name}: {error_detail(response)}")
        return sorted(model["id"] for model in response.json().get("data", []))


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

    A 429 that asks for a short wait (<= max_wait_s) is honoured in place:
    the chain sleeps and retries the same provider once. Longer waits put the
    provider on cooldown for the requested time (or cooldown_s when unknown).

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
        max_wait_s: float = 10.0,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.providers = providers
        self.cooldowns = cooldowns
        self.cooldown_s = cooldown_s
        self.budget = budget
        self.max_wait_s = max_wait_s
        self.clock = clock
        self.sleep = sleep
        self.calls = 0

    def complete_json(self, system: str, user: str) -> str:
        if not self.providers:
            raise LLMUnavailable("no LLM provider configured")
        if self.budget is not None and self.calls >= self.budget:
            raise LLMBudgetExhausted("LLM call cap reached")
        self.calls += 1

        errors = []
        for provider in self.providers:
            if self.cooldowns.get(provider.name, 0) > self.clock():
                errors.append(f"{provider.name}: cooling down")
                continue
            for attempt in (1, 2):
                try:
                    return extract_json(provider.complete_json(system, user))
                except RateLimited as exc:
                    wait = exc.retry_after
                    if attempt == 1 and wait is not None and wait <= self.max_wait_s:
                        self.sleep(wait)
                        continue
                    self.cooldowns[provider.name] = self.clock() + (
                        wait if wait is not None else self.cooldown_s
                    )
                    errors.append(str(exc))
                    break
                except ProviderError as exc:
                    errors.append(str(exc))
                    break
        raise LLMUnavailable("; ".join(errors))
