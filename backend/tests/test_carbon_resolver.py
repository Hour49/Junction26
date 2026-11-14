"""RESOLVER=carbon (app/adapters/resolver/carbon.py) with a fake transport: what is sent, the
price charged, the cache, and every way a call gives no reply."""

import base64
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from pydantic import SecretStr

from app import composition
from app.adapters.resolver.carbon import CarbonClient, CarbonResolver, crop, price
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


def page_png(number: int) -> bytes:
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

    def __call__(self, request: urllib.request.Request, timeout: float) -> dict[str, Any]:
        assert isinstance(request.data, bytes)
        self.sent.append(json.loads(request.data))
        self.urls.append(request.full_url)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        assert isinstance(reply, dict)
        return reply  # type: ignore[return-value]


@pytest.fixture(autouse=True)
def own_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    """The calls here charge the thread's cost (app/core/cost.py) from 0, put back after."""
    monkeypatch.setattr(cost._local, "usd", 0.0, raising=False)  # pyright: ignore[reportPrivateUsage]


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

    def page(number: int) -> bytes:
        pages.append(number)
        return page_png(number)

    before = cost.spent()
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
    assert cost.spent() - before == pytest.approx(USD) and budget.spent_usd == pytest.approx(USD)
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
    def broken(number: int) -> bytes:
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

    def page(number: int) -> bytes:
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
