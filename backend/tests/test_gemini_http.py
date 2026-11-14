"""The Gemini adapters' one way to open a request: 429 and 503 are tried again a bounded number
of times, nothing else is, and a call that got no answer is counted (`cost.fail`)."""

import io
import json
import urllib.error
import urllib.request

import pytest
from PIL import Image

from app.adapters import gemini_http
from app.adapters.carbon.reader import CarbonClient, CarbonReader
from app.adapters.raster_ocr.gemini import GeminiError
from app.core import cost


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://g.example", code, "x", {}, io.BytesIO(b"{}"))  # type: ignore[arg-type]


class Replies:
    """urlopen that raises or returns the next of `script`, and counts the calls."""

    def __init__(self, *script: object) -> None:
        self.script, self.calls = list(script), 0

    def __call__(self, request: object, timeout: float) -> object:
        self.calls += 1
        step = self.script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


def patched(monkeypatch: pytest.MonkeyPatch, *script: object) -> Replies:
    replies = Replies(*script)
    monkeypatch.setattr(urllib.request, "urlopen", replies)
    return replies


REQUEST = urllib.request.Request("https://g.example")


@pytest.mark.parametrize("code", [429, 503])
def test_a_transient_answer_is_tried_again_and_the_third_try_can_succeed(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    replies = patched(monkeypatch, http_error(code), http_error(code), "ok")
    waits: list[float] = []
    assert gemini_http.urlopen(REQUEST, 5, sleep=waits.append) == "ok"
    assert (replies.calls, waits) == (3, [1.0, 2.0])


def test_a_persistent_503_is_raised_after_the_bounded_tries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replies = patched(monkeypatch, *[http_error(503)] * 3)
    with pytest.raises(urllib.error.HTTPError):
        gemini_http.urlopen(REQUEST, 5, sleep=lambda _: None)
    assert replies.calls == 3


@pytest.mark.parametrize(
    "failure", [http_error(402), http_error(400), http_error(500), TimeoutError(), OSError()]
)
def test_anything_else_is_raised_at_once(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    replies = patched(monkeypatch, failure, "never")
    with pytest.raises(type(failure)):
        gemini_http.urlopen(REQUEST, 5, sleep=lambda _: None)
    assert replies.calls == 1


def test_the_carbon_client_rides_out_one_503(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(io.BytesIO):
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    replies = patched(
        monkeypatch, http_error(503), Response(json.dumps({"candidates": []}).encode())
    )
    monkeypatch.setattr(gemini_http.time, "sleep", lambda _: None)
    assert CarbonClient("key", 5).generate(b"jpeg", "p", {}, 10) == {"candidates": []}
    assert replies.calls == 2


class Down:
    def generate(
        self, jpeg: bytes, prompt: str, schema: dict[str, object], max_tokens: int
    ) -> dict:
        raise GeminiError("HTTP 503 UNAVAILABLE")


def test_a_carbon_read_whose_calls_got_no_answer_counts_the_failures() -> None:
    before = cost.faults()
    CarbonReader(Down(), None).read(Image.new("L", (64, 64), 255))
    assert cost.faults_since(before) == 2  # the page call and the tile call


class NotTheForm:
    def generate(
        self, jpeg: bytes, prompt: str, schema: dict[str, object], max_tokens: int
    ) -> dict:
        return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}


def test_a_reply_that_is_not_the_form_is_not_a_failed_call() -> None:
    before = cost.faults()
    CarbonReader(NotTheForm(), None).read(Image.new("L", (64, 64), 255))
    assert cost.faults_since(before) == 0
