"""A model call that got no answer reaches the caller's `cost.faults()` wherever the reader ran:
on `beside()`'s thread (the demo config's Carbon readers all do), in the composite, in rooms and
in Decisions. Only calls with no reply count: a paid empty reply does not, a refused budget does
(the reading is partial and is asked again once the budget is back)."""

import io
import json
import urllib.error
import urllib.request
from email.message import Message

import pytest
from PIL import Image

from app.adapters import gemini_http
from app.adapters.beside import beside
from app.adapters.carbon import CarbonChecked, CarbonThings
from app.adapters.carbon.reader import CarbonClient, CarbonExtractor, CarbonReader
from app.adapters.printed_scale.carbon import CarbonPrinted
from app.core import cost
from app.core.drawing.model import Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.spend import SpendGuard

PNG_BYTES = io.BytesIO()
Image.new("L", (64, 64), 255).save(PNG_BYTES, "PNG")
FILE = DrawingFile(path="a.png", size=1, sha256="a", kind="png")
SHEET = Sheet(file=FILE, pages=())


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://g.example", code, "x", Message(), io.BytesIO(b"{}"))


class Files:
    def read(self, path: str) -> bytes:
        return PNG_BYTES.getvalue()


class Local:
    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return Extracted(method="other", scale=Scale(status="no_scale"))


class Answering:
    """urlopen that answers every Gemini call with `code`, or with an empty 200 reply."""

    def __init__(self, code: int | None) -> None:
        self.code = code

    def __call__(self, request: object, timeout: float) -> object:
        if self.code is None:
            return Reply(json.dumps({"candidates": [{"finishReason": "MAX_TOKENS"}]}).encode())
        raise http_error(self.code)


class Reply(io.BytesIO):
    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


@pytest.fixture
def down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", Answering(503))
    monkeypatch.setattr(gemini_http.time, "sleep", lambda _: None)


def carbon(budget: SpendGuard | None = None) -> CarbonExtractor:
    return CarbonExtractor(Files(), CarbonReader(CarbonClient("key", 5, budget=budget), None))


def failed_calls(run: object) -> int:
    before = cost.faults()
    run()  # type: ignore[operator]
    return cost.faults_since(before)


def test_beside_carries_the_faults_of_its_thread_back_like_the_dollars() -> None:
    assert failed_calls(lambda: beside(lambda: None, cost.fail)) == 1
    assert failed_calls(lambda: beside(lambda: None, lambda: (cost.fail(), cost.fail()))) == 2


def test_a_failing_here_still_carries_the_faults_of_there_that_ended() -> None:
    def here() -> None:
        raise ValueError("here failed")

    def run() -> None:
        with pytest.raises(ValueError):
            beside(here, cost.fail)

    assert failed_calls(run) in (0, 1)  # there may not have started; never more than it did


@pytest.mark.parametrize("wrap", ["alone", "things", "checked", "both"])
def test_carbon_503s_reach_the_caller_through_the_demo_configs_wrappers(
    down: None, wrap: str
) -> None:
    base = carbon()
    extractor = {
        "alone": base,
        "things": CarbonThings(Local(), base, lambda p: True),
        "checked": CarbonChecked(Local(), base),
        "both": CarbonChecked(CarbonThings(Local(), base, lambda p: True), base),
    }[wrap]
    assert failed_calls(lambda: extractor.extract(FILE, SHEET)) >= 2  # the page and the tile call


def test_the_printed_scale_reader_counts_its_page_and_bars_calls_on_both_threads(
    down: None,
) -> None:
    reader = CarbonPrinted(
        CarbonClient("key", 5), Files(), None
    )  # its bars call is on beside's thread
    assert failed_calls(lambda: reader.read(FILE, SHEET)) == 2


def test_a_paid_empty_reply_is_not_a_call_without_an_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", Answering(None))
    assert failed_calls(lambda: carbon().extract(FILE, SHEET)) == 0


def test_a_refused_budget_counts_so_the_partial_reading_is_not_kept() -> None:
    assert failed_calls(lambda: carbon(SpendGuard(0)).extract(FILE, SHEET)) >= 2


def test_the_composite_carries_its_sources_faults_to_the_caller() -> None:
    from app.adapters.raster import Component, CompositeRasterExtractor

    class Failing:
        def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
            cost.fail()
            return Extracted(method="other", scale=Scale(status="no_scale"))

    composite = CompositeRasterExtractor(
        elements={},
        rooms=Component("rooms", Failing()),
        plans=Component("plans", Local()),
        scale=Component("scale", Failing()),
    )
    assert failed_calls(lambda: composite.extract(FILE, SHEET)) == 2


def test_the_gemini_rooms_extractor_counts_a_call_with_no_answer(down: None) -> None:
    from app.adapters.raster_ocr.gemini import GeminiClient, GeminiRoomExtractor, GeminiRoomReader

    rooms = GeminiRoomExtractor(Files(), GeminiRoomReader(GeminiClient("key", "m", 5), None))
    assert failed_calls(lambda: rooms.extract(FILE, SHEET)) == 1


def test_the_gemini_rooms_extractor_does_not_count_a_paid_empty_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.adapters.raster_ocr.gemini import GeminiClient, GeminiRoomExtractor, GeminiRoomReader

    monkeypatch.setattr(urllib.request, "urlopen", Answering(None))
    rooms = GeminiRoomExtractor(Files(), GeminiRoomReader(GeminiClient("key", "m", 5), None))
    assert failed_calls(lambda: rooms.extract(FILE, SHEET)) == 0


def test_decisions_counts_a_failed_call_and_a_refused_budget() -> None:
    from app.adapters.decisions.client import DecisionsClient, DecisionsError

    down = DecisionsClient("key", 5, transport=lambda body, key, timeout: (503, b"{}"),
                           sleep=lambda _: None)  # fmt: skip
    refused = DecisionsClient("key", 5, budget=SpendGuard(0))
    for client in (down, refused):
        before = cost.faults()
        with pytest.raises(DecisionsError):
            client.decide({})
        assert cost.faults_since(before) == 1


@pytest.mark.parametrize("which", ["rooms", "sheet_kind", "describer", "resolver"])
def test_each_gemini_client_rides_out_one_503(monkeypatch: pytest.MonkeyPatch, which: str) -> None:
    from app.adapters.raster_ocr.gemini import GeminiClient
    from app.adapters.resolver.carbon import CarbonClient as ResolverClient
    from app.adapters.triage.gemini_describer import GeminiDescribeClient
    from app.adapters.triage.sheet_kind import GeminiSheetKindClient

    ok = {"candidates": [{"content": {"parts": [{"text": "{}"}]}}], "usageMetadata": {}}

    class Once:
        calls = 0

        def __call__(self, request: object, timeout: float) -> object:
            Once.calls += 1
            if Once.calls == 1:
                raise http_error(503)
            return Reply(json.dumps(ok).encode())

    monkeypatch.setattr(urllib.request, "urlopen", Once())
    monkeypatch.setattr(gemini_http.time, "sleep", lambda _: None)
    call = {
        "rooms": lambda: GeminiClient("key", "m", 5).ask(b"png", "prompt"),
        "sheet_kind": lambda: GeminiSheetKindClient("key", 5).ask(b"jpeg"),
        "describer": lambda: GeminiDescribeClient("key", 5).ask(b"jpeg"),
        "resolver": lambda: ResolverClient("key", 5).ask([{"text": "q"}]),
    }[which]
    call()
    assert Once.calls == 2


def test_carry_hands_a_threads_dollars_and_failed_calls_to_the_caller() -> None:
    import threading

    carried = cost.Carry()

    def work() -> str:
        cost.charge(0.25)
        cost.fail(2)
        return "done"

    before, faulted = cost.mark(), cost.faults()
    thread = threading.Thread(target=lambda: carried.run(work))
    thread.start()
    thread.join()
    assert (cost.since(before), cost.faults_since(faulted)) == (0.0, 0)  # still on its own thread
    carried.hand_back()
    assert (cost.since(before), cost.faults_since(faulted)) == (0.25, 2)
