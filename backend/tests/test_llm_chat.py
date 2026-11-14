"""The agent's OpenAI-compatible model over a scripted transport (spec AC-10). No live call."""

import json
from typing import Any

import pytest

from app.adapters.llm_chat import OpenAiChatModel
from app.core.agent.loop import run_turn
from app.core.agent.model import Caps, Chat
from app.core.agent.ports import ChatModelError
from app.core.plan_edit.model import Proposal, Selection
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

    def proposal(self, proposal_id: str) -> Proposal | None:
        return None

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
    names = [t["function"]["name"] for t in first["tools"]]
    assert names == ["list_drawings", "show_on_plan", "review_answer", "final_answer"]
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
    usd = model(Transport()).usd({"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}, 0)
    assert usd == pytest.approx(10.50)


def test_ac10_an_http_error_is_a_model_error_without_the_key() -> None:
    transport = Transport((400, {"error": {"type": "BadRequestError", "message": KEY}}))
    with pytest.raises(ChatModelError) as raised:
        model(transport).complete([], [])
    assert "400" in str(raised.value) and KEY not in str(raised.value)
    assert KEY not in repr(model(Transport()))


def turn_on(*replies: tuple[int, Any], guard: SpendGuard | None = None) -> Any:
    chat = Chat("c3f9a1b2c4d5")
    return run_turn(
        chat, "hi", (), model(Transport(*replies)), Tools(), Caps(), guard or SpendGuard()
    )


def test_r7_a_filtered_reply_is_charged_from_its_usage() -> None:
    # review-5's probe: 5,000 prompt tokens, no message (content_filter)
    usage = {"prompt_tokens": 5000, "completion_tokens": 0, "total_tokens": 5000}
    filtered = {"choices": [{"finish_reason": "content_filter"}], "usage": usage}
    guard = SpendGuard()
    got = turn_on((200, filtered), guard=guard)
    assert got.kind == "dont_know" and "content_filter" in got.text
    assert got.cost_usd == pytest.approx(0.0075) and guard.spent_by()["agent chat"] == 0.0075


def test_r7_empty_choices_are_still_charged() -> None:
    empty = {"choices": [], "usage": {"prompt_tokens": 5000, "total_tokens": 5000}}
    got = turn_on((200, empty))
    assert got.kind == "dont_know" and got.cost_usd == pytest.approx(0.0075)


@pytest.mark.parametrize(
    "odd",
    [
        {"choices": ["x"], "usage": {"prompt_tokens": 10, "total_tokens": 20}},
        {"choices": [None], "usage": "lots"},
        {"choices": "x"},
        {"choices": [{"message": "x"}]},
        {"choices": [{"message": {"role": "assistant", "tool_calls": ["x"]}}]},
        {"choices": [{"message": {"role": "assistant", "tool_calls": [{"function": 3}]}}]},
        {"choices": [{"message": {"role": "assistant", "tool_calls": "call"}}]},
    ],
)
def test_r7_an_odd_reply_ends_the_turn_as_dont_know_and_charged(odd: dict[str, Any]) -> None:
    got = turn_on((200, odd))
    assert got.kind == "dont_know" and got.text.startswith("The assistant model did not answer")
    assert got.cost_usd > 0  # a reply came back: paid, never free


def test_r7_usage_never_prices_below_zero_or_free() -> None:
    priced = model(Transport())
    # total below prompt: the completion count, not a negative difference
    assert priced.usd({"prompt_tokens": 1000, "total_tokens": 10, "completion_tokens": 100}, 0) == (
        pytest.approx((1000 * 1.50 + 100 * 9.00) / 1e6))  # fmt: skip
    # no usable output count, or none at all: priced as the largest output, over the turn cap
    cap = Caps().turn_usd
    for usage in ({}, {"prompt_tokens": 1000, "total_tokens": 10},
                  {"prompt_tokens": "1000", "completion_tokens": "x"},
                  {"prompt_tokens": -5, "completion_tokens": -5, "total_tokens": -5}):  # fmt: skip
        assert priced.usd(usage, 30_000) > cap, usage
    # a missing prompt count is estimated from the request's size (3 characters a token)
    assert priced.usd({"completion_tokens": 0}, 30_000) == pytest.approx(10_001 * 1.50 / 1e6)


def test_r7_an_http_error_costs_nothing() -> None:
    got = turn_on((400, {"error": {"type": "BadRequestError"}}))
    assert got.kind == "dont_know" and got.cost_usd == 0


@pytest.mark.parametrize(
    ("thinking", "sent"),
    [("low", "low"), ("none", "none"), ("high", "high"), ("default", None)],
)
def test_the_thinking_level_is_sent_as_reasoning_effort(thinking: str, sent: str | None) -> None:
    """AGENT_THINKING (pi-spike borrow 4): "default" leaves the model's own level."""
    transport = Transport((200, reply(FINAL)))
    OpenAiChatModel(BASE, KEY, "gemini-4-hydrogen", 1.50, 9.00, 5.0, transport,
                    sleep=lambda _: None, thinking=thinking).complete([], [])  # fmt: skip
    assert transport.sent[0][1].get("reasoning_effort") == sent


def test_the_thinking_setting_reaches_the_model() -> None:
    from pydantic import SecretStr

    from app.composition import chat_model
    from app.settings import Settings

    settings = Settings(chat_model="gemini", gemini_api_key=SecretStr(KEY), agent_thinking="none")
    made, why = chat_model(settings)
    assert why is None and isinstance(made, OpenAiChatModel) and made.thinking == "none"
    assert Settings().agent_thinking == "low"  # unchanged until chat-eval says otherwise


def test_cached_prompt_tokens_are_priced_at_the_cached_rate() -> None:
    """pi-spike borrow 5. The compat endpoint's usage, as a live call gave it (2026-11-14):
    `prompt_tokens_details.cached_tokens` counts the part of `prompt_tokens` read from cache."""
    priced = OpenAiChatModel(BASE, KEY, "gemini-4-hydrogen", 1.50, 9.00, 5.0, Transport(),
                             sleep=lambda _: None, price_cached=0.375)  # fmt: skip
    usage = {"completion_tokens": 5, "prompt_tokens": 15115, "total_tokens": 15120,
             "prompt_tokens_details": {"cached_tokens": 13061}}  # fmt: skip
    want = (2054 * 1.50 + 13061 * 0.375 + 5 * 9.00) / 1e6
    assert priced.usd(usage, 0) == pytest.approx(want)
    # a cached count that can't be right is ignored: the prompt at the full price, never less
    full = (15115 * 1.50 + 5 * 9.00) / 1e6
    for odd in (-1, "13061", 20_000, None, True):
        given = {**usage, "prompt_tokens_details": {"cached_tokens": odd}}
        assert priced.usd(given, 0) == pytest.approx(full), odd
    assert priced.usd({**usage, "prompt_tokens_details": "x"}, 0) == pytest.approx(full)


def test_the_cached_price_setting_reaches_the_model() -> None:
    from pydantic import SecretStr

    from app.composition import chat_model
    from app.settings import Settings

    given = Settings(
        chat_model="gemini", gemini_api_key=SecretStr(KEY), agent_price_cached_per_m=0.2
    )
    made, _ = chat_model(given)
    assert isinstance(made, OpenAiChatModel) and made.price_cached == 0.2
    assert Settings().agent_price_cached_per_m == pytest.approx(0.375)  # 1/4 of the input price
