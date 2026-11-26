"""The model call behind a Protocol: the service never imports the SDK (SEC-044..046).

`AnthropicLlm` imports `anthropic` inside `complete`, with `max_retries=0` so the retry policy is
the service's. SDK failures become three adapter-level errors. `FakeLlm` replays a script;
`HashLlm` answers deterministically from the message (FAKE_LLM).
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from saveclock.domain.keywords_fallback import TABLE


class LlmError(Exception):
    """The call failed for a reason the service treats as 'no answer' (the table takes over)."""


class LlmTimeout(LlmError):
    pass


class LlmRateLimited(LlmError):
    pass


class LlmRefusal(LlmError):
    pass


@dataclass(frozen=True)
class LlmReply:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None = "end_turn"


class LlmClient(Protocol):
    def complete(
        self, system: str, user: str, *, max_tokens: int, timeout_s: float
    ) -> LlmReply: ...


class AnthropicLlm:
    def __init__(self, api_key: str, model: str, *, http_client: Any = None) -> None:  # noqa: ANN401
        # http_client: tests inject an in-process transport (the SDK uses httpx2, not httpx)
        self._api_key, self.model, self._http = api_key, model, http_client

    def complete(self, system: str, user: str, *, max_tokens: int, timeout_s: float) -> LlmReply:
        import anthropic

        client = anthropic.Anthropic(
            api_key=self._api_key, max_retries=0, timeout=timeout_s, http_client=self._http
        )
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APITimeoutError as exc:
            raise LlmTimeout from exc
        except anthropic.RateLimitError as exc:
            raise LlmRateLimited from exc
        except anthropic.APIError as exc:
            raise LlmError(type(exc).__name__) from exc  # the class name only, never the body
        if msg.stop_reason == "refusal":
            raise LlmRefusal
        text = "".join(b.text for b in msg.content if b.type == "text")
        return LlmReply(text, msg.usage.input_tokens, msg.usage.output_tokens, msg.stop_reason)


@dataclass
class FakeLlm:
    """Replays scripted replies or raises scripted errors, one per call; records every call."""

    script: Sequence[LlmReply | Exception]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def complete(self, system: str, user: str, *, max_tokens: int, timeout_s: float) -> LlmReply:
        self.calls.append(
            {"system": system, "user": user, "max_tokens": max_tokens, "timeout_s": timeout_s}
        )
        item = self.script[len(self.calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item


class HashLlm:
    """FAKE_LLM: keywords picked from the offline table by a hash of the message. No network."""

    def complete(self, system: str, user: str, *, max_tokens: int, timeout_s: float) -> LlmReply:
        digest = int(hashlib.sha256(user.encode()).hexdigest(), 16)
        rows = sorted(TABLE.values())
        row = rows[digest % len(rows)]
        start = digest % 3
        text = json.dumps({"keywords": list(row[start : start + 6])})
        return LlmReply(text, len(user) // 4, len(text) // 4)
