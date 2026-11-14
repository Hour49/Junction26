"""RESOLVER=carbon (app/adapters/resolver/carbon.py) with a fake transport: what is sent, the
price charged, the cache, and every way a call gives no reply."""

import base64
import io
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from pydantic import SecretStr

from app import composition
from app.adapters.resolver import carbon
from app.adapters.resolver.carbon import RENDER_WIDTH, CarbonClient, CarbonResolver, crop, price
from app.core import cost
from app.core.pipeline.model import ValueMark
from app.core.review.model import Candidate, Resolved, ResolveRequest, ResolverUnavailable, Spot
from app.core.spend import SpendGuard
from app.settings import Settings

AT = "2026-11-14T18:00:00+00:00"
USAGE = {"promptTokenCount": 100_000, "candidatesTokenCount": 1_000, "thoughtsTokenCount": 4_000}
USD = (100_000 * 4 + 5_000 * 20) / 1e6  # 0.5


def door_request(kind: str = "conflict") -> ResolveRequest:
    box = (0.40, 0.40, 0.45, 0.45)
    return ResolveRequest(
        drawing_id="d1",
        quantity="door",
        question="Door count: 2 or 3?",
        unit="count",
        kind=kind,  # type: ignore[arg-type]
        candidates=(
            Candidate(
                value=2,
                source="the drawn plan",
                marks=(ValueMark(page=1, box=box, label="door 1"),),
            ),
            Candidate(value=3, source="the building model"),
        ),
        spots=(Spot(page=1, box=box, why="the drawn plan counts door 1 here"),),
    )


def page_png(number: int, width: int = 800) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(out, format="PNG")
    return out.getvalue()


def answer(form: object, usage: dict[str, int] = USAGE) -> dict[str, Any]:
    text = form if isinstance(form, str) else json.dumps(form)
    return {"candidates": [{"content": {"parts": [{"text": text}]}}], "usageMetadata": usage}


class Transport:
    """Answers with each reply in turn (an exception is raised) and keeps the requests."""

    def __init__(self, *replies: object) -> None:
        self.replies = list(replies)
        self.sent: list[dict[str, Any]] = []
        self.urls: list[str] = []
        self.timeouts: list[float] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> dict[str, Any]:
        assert isinstance(request.data, bytes)
        self.sent.append(json.loads(request.data))
        self.urls.append(request.full_url)
        self.timeouts.append(timeout)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply  # type: ignore[return-value]  # odd envelopes too


def resolver(
    tmp_path: Path, transport: Transport, budget: SpendGuard | None = None
) -> CarbonResolver:
    client = CarbonClient("key", 5.0, budget=budget, transport=transport)
    return CarbonResolver(client, tmp_path / "cache", clock=lambda: AT)


PICK = {"reason": "Three door leaves are drawn.", "verdict": "picked", "value": 3}


def test_a_pick_is_asked_with_the_question_values_and_images_and_is_paid_once(
    tmp_path: Path,
) -> None:
    transport = Transport(answer(PICK))
    budget = SpendGuard()
    pages: list[int] = []

    def page(number: int, width: int) -> bytes:
        pages.append(number)
        return page_png(number)

    before = cost.mark()
    found = resolver(tmp_path, transport, budget).resolve(door_request(), page)
    assert found == Resolved(
        verdict="picked",
        value=3,
        reason="Three door leaves are drawn.",
        marks=(
            ValueMark(
                page=1, box=(0.40, 0.40, 0.45, 0.45), label="the drawn plan counts door 1 here"
            ),
        ),
        by="carbon:gemini-4-carbon",
        at=AT,
    )
    (sent,) = transport.sent
    assert transport.urls == [
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-4-carbon:generateContent"
    ]
    parts = sent["contents"][0]["parts"]
    prompt = parts[0]["text"]
    assert "Door count: 2 or 3?" in prompt and "- 2, read by the drawn plan" in prompt
    assert "- 3, read by the building model" in prompt
    images = [part["inlineData"] for part in parts if "inlineData" in part]
    assert len(images) == 2 and {image["mimeType"] for image in images} == {"image/jpeg"}
    assert sent["generationConfig"]["responseMimeType"] == "application/json"
    assert pages == [1]  # rendered once for the page and its crop
    assert cost.since(before) == pytest.approx(USD) and budget.spent_usd == pytest.approx(USD)
    again = resolver(tmp_path, Transport(), budget).resolve(door_request(), page)
    assert again == found and pages == [1] and budget.spent_usd == pytest.approx(USD)


def test_cannot_tell_has_no_value(tmp_path: Path) -> None:
    form = {"reason": "The label is cut off.", "verdict": "cannot_tell", "value": 2}
    found = resolver(tmp_path, Transport(answer(form))).resolve(door_request(), page_png)
    assert isinstance(found, Resolved) and (found.verdict, found.value) == ("cannot_tell", None)


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        (answer("not json"), "the reply is not the form"),
        (answer({"verdict": "picked", "value": None, "reason": "x"}), "the reply is not the form"),
        (answer({"verdict": "maybe", "value": 2, "reason": "x"}), "the reply is not the form"),
        ({"candidates": []}, "empty answer"),
        (urllib.error.URLError("down"), "no answer: URLError"),
        (TimeoutError(), "no answer: TimeoutError"),
    ],
)
def test_a_reply_that_is_not_the_form_is_no_reply_and_is_not_cached(
    tmp_path: Path, reply: object, said: str
) -> None:
    transport = Transport(reply, answer(PICK))
    carbon = resolver(tmp_path, transport)
    found = carbon.resolve(door_request(), page_png)
    assert isinstance(found, ResolverUnavailable) and said in found.note
    assert isinstance(carbon.resolve(door_request(), page_png), Resolved)  # asked again
    assert len(transport.sent) == 2


def test_an_unusable_reply_is_still_paid_for(tmp_path: Path) -> None:
    budget = SpendGuard()
    resolver(tmp_path, Transport(answer("not json")), budget).resolve(door_request(), page_png)
    assert budget.spent_usd == pytest.approx(USD)


def test_a_used_up_budget_sends_nothing(tmp_path: Path) -> None:
    transport = Transport()
    found = resolver(tmp_path, transport, SpendGuard(total_usd=0)).resolve(door_request(), page_png)
    assert isinstance(found, ResolverUnavailable) and "budget used up" in found.note
    assert transport.sent == []


def test_a_page_that_cannot_be_rendered_is_no_reply(tmp_path: Path) -> None:
    def broken(number: int, width: int) -> bytes:
        return b"not a png"

    transport = Transport()
    found = resolver(tmp_path, transport).resolve(door_request(), broken)
    assert isinstance(found, ResolverUnavailable) and "page could not be shown" in found.note
    assert transport.sent == []


def test_with_no_spot_or_mark_the_first_page_is_shown(tmp_path: Path) -> None:
    from app.adapters.resolver.carbon import request_parts

    bare = door_request().model_copy(
        update={"spots": (), "candidates": (Candidate(value=2, source="the answer"),)}
    )
    pages: list[int] = []

    def page(number: int, width: int) -> bytes:
        pages.append(number)
        return page_png(number)

    parts = request_parts(bare, page)
    assert pages == [1] and sum("inlineData" in part for part in parts) == 1


def test_thinking_is_low(tmp_path: Path) -> None:
    transport = Transport(answer(PICK))
    resolver(tmp_path, transport).resolve(door_request(), page_png)
    assert transport.sent[0]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


def test_an_answer_check_says_so_in_the_prompt(tmp_path: Path) -> None:
    transport = Transport(answer(PICK))
    resolver(tmp_path, transport).resolve(door_request("answer"), page_png)
    assert "The reader is not sure of it" in transport.sent[0]["contents"][0]["parts"][0]["text"]


def test_a_crop_keeps_context_and_draws_the_box_in_red() -> None:
    image = Image.new("RGB", (1000, 1000), "white")
    shown = crop(image, Spot(page=1, box=(0.5, 0.5, 0.52, 0.52), why="x"))
    assert shown.size == (140, 140)  # 0.06 of the page on each side of a 0.02 box
    red = shown.convert("RGB").getpixel((60, 60))
    assert isinstance(red, tuple) and red[0] > 200 and red[1] < 50
    assert shown.convert("RGB").getpixel((70, 70)) == (255, 255, 255)


def test_price_is_four_in_twenty_out_per_million() -> None:
    assert price({"usageMetadata": USAGE}) == pytest.approx(USD)
    assert price({}) == 0


def test_resolver_carbon_builds_the_adapter_and_needs_a_key(tmp_path: Path) -> None:
    settings = Settings(projects_dir=tmp_path, resolver="carbon", gemini_api_key="k")  # type: ignore[arg-type]
    assert isinstance(composition._resolver(settings), CarbonResolver)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(Exception, match="GEMINI_API_KEY is empty"):
        composition._resolver(settings.model_copy(update={"gemini_api_key": SecretStr("")}))  # pyright: ignore[reportPrivateUsage]


def test_images_are_jpegs_that_open() -> None:
    from app.adapters.resolver.carbon import request_parts

    parts = request_parts(door_request(), page_png)
    for part in parts:
        if "inlineData" in part:
            Image.open(io.BytesIO(base64.b64decode(part["inlineData"]["data"]))).verify()


def test_the_timeout_reaches_the_transport_and_is_30_s_by_default(tmp_path: Path) -> None:
    transport = Transport(answer(PICK))
    resolver(tmp_path, transport).resolve(door_request(), page_png)
    assert transport.timeouts == [5.0]
    assert Settings(projects_dir=tmp_path).resolver_timeout_s == 30


def test_the_page_is_rendered_at_the_adapter_s_width(tmp_path: Path) -> None:
    widths: list[int] = []

    def page(number: int, width: int) -> bytes:
        widths.append(width)
        return page_png(number)

    resolver(tmp_path, Transport(answer(PICK))).resolve(door_request(), page)
    assert widths == [RENDER_WIDTH]


def test_another_model_or_call_setting_is_another_cache_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache key holds the model and everything that shapes the call (no version by hand)."""
    transport = Transport(answer(PICK), answer(PICK), answer(PICK), answer(PICK))
    resolver(tmp_path, transport).resolve(door_request(), page_png)
    other = CarbonClient("key", 5.0, model="gemini-4-argon", transport=transport)
    CarbonResolver(other, tmp_path / "cache", clock=lambda: AT).resolve(door_request(), page_png)
    assert len(transport.sent) == 2
    for name, value in (("TEMPERATURE", 1.0), ("CROP_SIDE", 512)):
        with monkeypatch.context() as patched:
            patched.setattr(carbon, name, value)
            resolver(tmp_path, transport).resolve(door_request(), page_png)
    assert len(transport.sent) == 4
    resolver(tmp_path, transport).resolve(door_request(), page_png)  # all as before: cached
    assert len(transport.sent) == 4


class Blocking(Transport):
    """Holds the call until the test lets it go."""

    def __init__(self, *replies: object) -> None:
        super().__init__(*replies)
        self.entered = threading.Event()
        self.go = threading.Event()

    def __call__(self, request: urllib.request.Request, timeout: float) -> dict[str, Any]:
        self.entered.set()
        assert self.go.wait(10)
        return super().__call__(request, timeout)


def test_two_callers_of_one_request_share_one_call(tmp_path: Path) -> None:
    """The upload's resolve thread and a person's POST at once: one call, one charge."""
    transport = Blocking(answer(PICK))
    budget = SpendGuard()
    carbon_resolver = resolver(tmp_path, transport, budget)
    replies: list[object] = []

    def call() -> None:
        replies.append(carbon_resolver.resolve(door_request(), page_png))

    first = threading.Thread(target=call)
    first.start()
    assert transport.entered.wait(10)
    second = threading.Thread(target=call)
    second.start()
    flights = carbon_resolver._flights  # pyright: ignore[reportPrivateUsage]
    deadline = time.monotonic() + 10
    while not any(flight.joined for flight in list(flights.values())):
        assert time.monotonic() < deadline, "the second caller never joined the call"
        time.sleep(0.001)
    transport.go.set()
    first.join(10)
    second.join(10)
    assert len(transport.sent) == 1 and budget.spent_usd == pytest.approx(USD)
    assert len(replies) == 2 and replies[0] == replies[1] and isinstance(replies[0], Resolved)
    assert flights == {}


@pytest.mark.parametrize(
    "envelope",
    [
        {"candidates": [{"content": {"parts": ["x"]}}]},
        ["x"],
        {"usageMetadata": {"promptTokenCount": "lots"}},
    ],
)
def test_an_odd_reply_envelope_is_no_reply_not_an_error(tmp_path: Path, envelope: object) -> None:
    found = resolver(tmp_path, Transport(envelope)).resolve(door_request(), page_png)
    assert isinstance(found, ResolverUnavailable)
