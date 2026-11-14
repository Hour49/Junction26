"""The agent chat's model over an OpenAI-compatible endpoint (spec AC-10): Gemini by default
(AGENT_BASE_URL, GEMINI_API_KEY, AGENT_MODEL). The urllib transport, retries and key handling are
openvlm/client.py's. The assistant message is returned as sent, `extra_content` (Gemini's thought
signatures) included, because the next step must send it back unchanged."""

import json
import time
from collections.abc import Callable
from typing import Any

from app.adapters.openvlm.client import OpenVlmClient, OpenVlmError, Transport, urllib_transport
from app.core.agent.ports import ChatModelError, Reply

Json = dict[str, Any]
M = 1_000_000
BODY = {"tool_choice": "auto"}
CHARS_PER_TOKEN = 3  # fewer than the usual ~4: an estimated prompt errs high
# A reply whose output count can't be read is priced as Gemini's largest output (65,536 tokens):
# never free, and over the turn's cap, so a garbled usage ends the turn instead of slipping past
UNKNOWN_OUT = 65_536


class OpenAiChatModel:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        price_in: float,
        price_out: float,
        timeout_s: float = 60.0,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        thinking: str = "low",
        price_cached: float | None = None,
    ) -> None:
        self.name = model
        # sent as reasoning_effort (Gemini's compat endpoint takes it); "default": not sent, the
        # model's own level. low: fewer thinking tokens, a faster turn
        self.thinking = thinking
        self._paid: bytes | None = None  # the last 200 reply's body, for what it cost

        def watched(url: str, body: bytes, key: str, timeout: float) -> tuple[int, bytes]:
            status, data = transport(url, body, key, timeout)
            self._paid = data if status == 200 else None
            return status, data

        self._client = OpenVlmClient(base_url, api_key, model, timeout_s, watched, sleep)
        self._price_in = price_in
        self._price_out = price_out
        # USD per million prompt tokens read from the provider's cache; None: the input price
        self.price_cached = price_in if price_cached is None else price_cached

    def __repr__(self) -> str:
        return f"OpenAiChatModel({self.name})"

    def complete(self, messages: list[Json], tools: list[Json]) -> Reply:
        effort = {} if self.thinking == "default" else {"reasoning_effort": self.thinking}
        body = {**BODY, **effort, "messages": messages, "tools": tools}
        sent = len(json.dumps(body))
        self._paid = None
        try:
            reply = self._client.chat(body)
        except OpenVlmError as error:  # a 200 the client refused (no choices, not JSON) is paid
            raise ChatModelError(str(error), self._cost_of_paid(sent)) from None
        except (
            AttributeError,
            TypeError,
            ValueError,
        ):  # openvlm's log line reads `usage` as a dict
            raise ChatModelError("the answer is malformed", self._cost_of_paid(sent)) from None
        usage: Any = reply.get("usage")
        usd = self.usd(usage if isinstance(usage, dict) else {}, sent)  # pyright: ignore[reportUnknownArgumentType]
        choices: Any = reply.get("choices")
        first: Any = choices[0] if isinstance(choices, list) and choices else None
        message: Any = first.get("message") if isinstance(first, dict) else None  # pyright: ignore[reportUnknownMemberType]
        if not isinstance(message, dict):
            finish: Any = first.get("finish_reason") if isinstance(first, dict) else None  # pyright: ignore[reportUnknownMemberType]
            why = finish if isinstance(finish, str) and finish.isidentifier() else "no message"
            raise ChatModelError(f"the answer has no message: {why}", usd)
        if not _calls_ok(message.get("tool_calls")):  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            raise ChatModelError("the answer's tool calls are malformed", usd)
        return Reply(message, usd)  # pyright: ignore[reportUnknownArgumentType]

    def _cost_of_paid(self, sent: int) -> float:
        """What the last call cost when a 200 came back that the client could not use; 0 if not."""
        return 0.0 if self._paid is None else self.usd(_usage(self._paid), sent)

    def usd(self, usage: Json, sent_chars: int) -> float:
        """Prompt tokens at the input price, those of them read from cache
        (`prompt_tokens_details.cached_tokens`) at the cached price; the rest of `total_tokens`
        (answer and thinking, whichever way the endpoint splits them), or `completion_tokens` if
        larger, at the output price. A count that is missing, negative or not a number is priced
        high, never as free: the prompt from the request's size (with no cached part), the output
        as UNKNOWN_OUT, a cached count as none."""
        given = _count(usage.get("prompt_tokens"))
        total = _count(usage.get("total_tokens"))
        done = _count(usage.get("completion_tokens"))
        counted = given is not None  # an estimated prompt gets no cached discount
        if given is None:
            given = sent_chars // CHARS_PER_TOKEN + 1
        outs = [n for n in (None if total is None else total - given, done) if n is not None]
        out = max(outs) if outs and max(outs) >= 0 else UNKNOWN_OUT
        details: Any = usage.get("prompt_tokens_details")
        cached = _count(details.get("cached_tokens")) if isinstance(details, dict) else None  # pyright: ignore[reportUnknownMemberType]
        cached = cached if counted and cached is not None and cached <= given else 0
        paid = (given - cached) * self._price_in + cached * self.price_cached
        return (paid + out * self._price_out) / M


def _usage(data: bytes) -> Json:
    """The `usage` of a reply body, {} when it has none that can be read."""
    try:
        found: Any = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return {}
    usage: Any = found.get("usage") if isinstance(found, dict) else None  # pyright: ignore[reportUnknownMemberType]
    return usage if isinstance(usage, dict) else {}  # pyright: ignore[reportUnknownVariableType]


def _count(value: Any) -> int | None:
    """A token count as the reply gives it, or None when it is not a count >= 0."""
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        return None
    return int(value)


def _calls_ok(calls: Any) -> bool:
    """Tool calls the loop can run: none, or a list of {"function": {"name": str, ...}, ...}."""
    if calls is None:
        return True
    if not isinstance(calls, list):
        return False
    return all(
        isinstance(call, dict)
        and isinstance(call.get("function"), dict)  # pyright: ignore[reportUnknownMemberType]
        and isinstance(call["function"].get("name"), str)  # pyright: ignore[reportUnknownMemberType]
        for call in calls  # pyright: ignore[reportUnknownVariableType]
    )
