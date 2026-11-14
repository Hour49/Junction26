"""The agent chat's model over an OpenAI-compatible endpoint (spec AC-10): Gemini by default
(AGENT_BASE_URL, GEMINI_API_KEY, AGENT_MODEL). The urllib transport, retries and key handling are
openvlm/client.py's. The assistant message is returned as sent, `extra_content` (Gemini's thought
signatures) included, because the next step must send it back unchanged."""

import time
from collections.abc import Callable
from typing import Any

from app.adapters.openvlm.client import OpenVlmClient, OpenVlmError, Transport, urllib_transport
from app.core.agent.ports import ChatModelError, Reply

Json = dict[str, Any]
M = 1_000_000


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
    ) -> None:
        self.name = model
        self._client = OpenVlmClient(base_url, api_key, model, timeout_s, transport, sleep)
        self._price_in = price_in
        self._price_out = price_out

    def __repr__(self) -> str:
        return f"OpenAiChatModel({self.name})"

    def complete(self, messages: list[Json], tools: list[Json]) -> Reply:
        body = {"messages": messages, "tools": tools, "tool_choice": "auto"}
        try:
            reply = self._client.chat(body)
        except OpenVlmError as error:
            raise ChatModelError(str(error)) from None
        message = (reply["choices"][0] or {}).get("message")
        if not isinstance(message, dict):
            raise ChatModelError("the answer has no message")
        return Reply(message, self.usd(reply.get("usage") or {}))  # pyright: ignore[reportUnknownArgumentType]

    def usd(self, usage: Json) -> float:
        """Prompt tokens at the input price; the rest of `total_tokens` (answer and thinking,
        whichever way the endpoint splits them) at the output price."""
        given = int(usage.get("prompt_tokens") or 0)
        total = int(usage.get("total_tokens") or 0)
        out = total - given if total else int(usage.get("completion_tokens") or 0)
        return (given * self._price_in + out * self._price_out) / M
