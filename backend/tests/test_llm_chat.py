"""The agent's OpenAI-compatible model over a scripted transport (spec AC-10). No live call."""

import json
from typing import Any

import pytest

from app.adapters.llm_chat import OpenAiChatModel
from app.core.agent.loop import run_turn
from app.core.agent.model import Caps, Chat
from app.core.agent.ports import ChatModelError
from app.core.plan_edit.model import Selection
from app.core.spend import SpendGuard

KEY = "test-key-not-real"
BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
SIGNED = {
    "role": "assistant",
    "content": None,
    "tool_calls": [{
        "id": "c1", "type": "function",
        "function": {"name": "list_drawings", "arguments": "{}"},
        "extra_content": {"google": {"thought_signature": "c2lnbmF0dXJl"}},
    }],
}  # fmt: skip
FINAL = {
    "role": "assistant",
    "tool_calls": [{"id": "c2", "type": "function", "function": {
        "name": "final_answer", "arguments": json.dumps({"kind": "dont_know", "text": "No."})}}],
}  # fmt: skip


class Transport:
    def __init__(self, *replies: tuple[int, Any]) -> None:
        self.replies = list(replies)
        self.sent: list[tuple[str, dict[str, Any], str]] = []

    def __call__(self, url: str, body: bytes, key: str, timeout: float) -> tuple[int, bytes]:
        self.sent.append((url, json.loads(body), key))
        status, payload = self.replies.pop(0)
        return status, json.dumps(payload).encode()


def reply(message: dict[str, Any], prompt: int = 1000, total: int = 1500) -> dict[str, Any]:
    usage = {"prompt_tokens": prompt, "completion_tokens": 100, "total_tokens": total}
    return {"choices": [{"message": message, "finish_reason": "tool_calls"}], "usage": usage}


def model(transport: Transport) -> OpenAiChatModel:
    return OpenAiChatModel(BASE, KEY, "gemini-4-hydrogen", 1.50, 9.00, 5.0, transport,
                           sleep=lambda _: None)  # fmt: skip


class Tools:
    @property
    def tools(self) -> list[dict[str, Any]]:
        return [{"type": "function", "function": {"name": "list_drawings"}}]

    def run(self, name: str, arguments: str) -> str:
        return "[]"

    def describe(self, selection: Selection) -> str:
        return ""


def test_ac10_posts_tools_and_sends_the_assistant_message_back_verbatim() -> None:
    transport = Transport((200, reply(SIGNED)), (200, reply(FINAL)))
    got = run_turn(Chat("c3f9a1b2c4d5"), "hi", (), model(transport), Tools(), Caps(), SpendGuard())
    assert got.kind == "dont_know" and got.model == "gemini-4-hydrogen"
    url, first, key = transport.sent[0]
    assert url == BASE + "/chat/completions" and key == KEY
    assert first["model"] == "gemini-4-hydrogen" and first["tool_choice"] == "auto"
    assert first["reasoning_effort"] == "low"
    assert [t["function"]["name"] for t in first["tools"]] == ["list_drawings", "final_answer"]
    second = transport.sent[1][1]["messages"]
    assert second[2] == SIGNED  # extra_content (the thought signature) round-trips unchanged


def test_ac7_ac10_cost_from_usage_and_charged() -> None:
    transport = Transport((200, reply(SIGNED)), (200, reply(FINAL, 2000, 2400)))
    guard = SpendGuard()
    got = run_turn(Chat("c3f9a1b2c4d5"), "hi", (), model(transport), Tools(), Caps(), guard)
    # (1000 x 1.50 + 500 x 9.00) / 1e6 + (2000 x 1.50 + 400 x 9.00) / 1e6
    assert got.cost_usd == pytest.approx(0.006 + 0.0066)
    assert guard.spent_by()["agent chat"] == pytest.approx(0.0126)


def test_ac10_usage_without_total_counts_completion_tokens() -> None:
    usd = model(Transport()).usd({"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})
    assert usd == pytest.approx(10.50)


def test_ac10_an_http_error_is_a_model_error_without_the_key() -> None:
    transport = Transport((400, {"error": {"type": "BadRequestError", "message": KEY}}))
    with pytest.raises(ChatModelError) as raised:
        model(transport).complete([], [])
    assert "400" in str(raised.value) and KEY not in str(raised.value)
    assert KEY not in repr(model(Transport()))
