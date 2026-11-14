"""Brief r8 BS: the independent reads of a raster sheet run at the same time, not one after the
other (44 s on a photo, 45 s on a scanned PDF on main a7903b2): the printed-scale reader beside
the raster reader, its page and bars calls beside each other, Carbon beside the shipped reader
(CARBON_READER=large, CARBON_LEVELS=demote). The page call both Carbon readers ask is paid for
once. Each "at the same time" test meets at a two-party barrier: run one after the other, the
first waits alone and the barrier breaks. Fakes stand in for every reader and model. Synthetic."""

import io
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.adapters.beside import beside
from app.adapters.carbon import CarbonChecked, CarbonThings, contract
from app.adapters.carbon.flight import waiting
from app.adapters.carbon.reader import CarbonReader
from app.adapters.printed_scale import PrintedScale
from app.adapters.printed_scale.carbon import BARS_PROMPT, CarbonPrinted
from app.adapters.raster_ocr.gemini import pixel_digest
from app.core import cost
from app.core.drawing.model import Page, Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.printed import PrintedSheet

PAGE = Page(page=1, width=900, height=700, unit="px")
FILE = DrawingFile(path="sheet.png", size=1, sha256="0" * 64, kind="png")
SHEET = Sheet(file=FILE, pages=(PAGE,))
WAIT_S = 10  # a barrier that waits this long has been left alone: the reads ran in turn
NOTHING = Extracted(method="detector", scale=Scale(status="no_scale"), notes=("shipped",))
PAGE_FORM = {
    "seen": "a flat", "title_block": {}, "printed_scale": "1:100",
    "plans": [{"name": None, "box_2d": [0, 0, 1000, 1000]}], "rooms": [], "rooms_listed": "all",
    "printed_facts": [], "tables": [],
}  # fmt: skip
TILE_FORM = {"elements": [], "rooms_seen": [], "unreadable": []}
BARS_FORM = {"printed_scale": None, "scale_bars": []}


def envelope(form: object) -> dict[str, Any]:
    text = json.dumps(form)
    return {"candidates": [{"content": {"parts": [{"text": text}]}}], "usageMetadata": {}}


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (900, 700), "white").save(out, "PNG")
    return out.getvalue()


class Files:
    def read(self, path: str) -> bytes:
        return png()


class Meets:
    """An extractor (or printed reader) that meets the other read at `barrier`, charging `usd`
    on its own thread as a model call does."""

    def __init__(self, barrier: threading.Barrier, found: Any, usd: float = 0.0) -> None:
        self.barrier, self.found, self.usd = barrier, found, usd

    def extract(self, source: DrawingFile, sheet: Sheet) -> Any:
        self.barrier.wait()
        cost.charge(self.usd)
        return self.found

    read = extract


def test_beside_returns_both_in_order_and_charges_the_other_threads_cost() -> None:
    def here() -> str:
        cost.charge(0.01)
        return "here"

    def there() -> str:
        cost.charge(0.02)
        return "there"

    before = cost.mark()
    assert beside(here, there) == ("here", "there")
    assert cost.since(before) == pytest.approx(0.03)


def test_when_this_read_fails_the_other_is_not_waited_for() -> None:
    """review-306 S1: the shipped reader failed, so the Carbon read is not waited for (it may be
    in flight; one not started yet is cancelled)."""
    release, finished = threading.Event(), threading.Event()

    def here() -> None:
        raise ValueError("the reader failed")

    def there() -> None:
        release.wait(WAIT_S)
        finished.set()

    with pytest.raises(ValueError, match="the reader failed"):
        beside(here, there)
    assert not finished.is_set()  # the error came back while the other read still ran
    release.set()
    assert finished.wait(WAIT_S)


def test_the_other_reads_error_is_logged_when_this_one_failed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """review-306 S2: nobody reads the other read's result after this one failed, so its error
    is logged instead of lost."""
    started, release = threading.Event(), threading.Event()

    def here() -> None:
        assert started.wait(WAIT_S)  # the other read is running, so it is not cancelled
        raise ValueError("the reader failed")

    def there() -> None:
        started.set()
        release.wait(WAIT_S)
        raise RuntimeError("the Carbon call failed")

    with caplog.at_level(logging.WARNING, logger="app.adapters.beside"):
        with pytest.raises(ValueError, match="the reader failed"):
            beside(here, there)
        release.set()
        deadline = time.monotonic() + WAIT_S
        while not any(r.exc_info and "Carbon call failed" in str(r.exc_info[1])
                      for r in caplog.records):  # fmt: skip
            assert time.monotonic() < deadline, "the other read's error was not logged"
            time.sleep(0.01)


def test_an_error_of_the_other_read_reaches_the_caller_when_this_one_succeeded() -> None:
    def there() -> None:
        raise RuntimeError("the Carbon call failed")

    with pytest.raises(RuntimeError, match="the Carbon call failed"):
        beside(lambda: "here", there)


def test_the_printed_scale_is_read_at_the_same_time_as_the_raster_reader() -> None:
    meet = threading.Barrier(2, timeout=WAIT_S)
    printed = PrintedSheet(printed_scale=None)
    reader = PrintedScale(Meets(meet, NOTHING, 0.01), Meets(meet, printed, 0.02), Files())
    before = cost.mark()
    found = reader.extract(FILE, SHEET)
    assert "shipped" in found.notes
    assert cost.since(before) == pytest.approx(0.03)  # both reads land in the trace


def test_carbon_things_reads_carbon_at_the_same_time_as_the_shipped_reader() -> None:
    meet = threading.Barrier(2, timeout=WAIT_S)
    carbon = NOTHING.model_copy(update={"notes": ("carbon read",)})
    found = CarbonThings(Meets(meet, NOTHING), Meets(meet, carbon), lambda _: True).extract(
        FILE, SHEET
    )
    assert "carbon read" in found.notes


def test_the_carbon_check_runs_at_the_same_time_as_the_shipped_reader() -> None:
    meet = threading.Barrier(2, timeout=WAIT_S)
    carbon = NOTHING.model_copy(update={"read": ("door",), "notes": ()})
    found = CarbonChecked(Meets(meet, NOTHING), Meets(meet, carbon)).extract(FILE, SHEET)
    assert found.carbon_check is not None and found.carbon_check.read == ("door",)


class PrintedModel:
    """The page and bars calls meet at a barrier; every call is recorded."""

    def __init__(self, meet: threading.Barrier | None = None) -> None:
        self.meet = meet
        self.calls: list[str] = []

    def generate(
        self, jpeg: bytes, prompt: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        kind = "bars" if prompt == BARS_PROMPT else "page"
        self.calls.append(kind)
        if self.meet is not None:
            self.meet.wait()
        return envelope(BARS_FORM if kind == "bars" else PAGE_FORM)


def test_the_page_and_bars_calls_are_asked_at_the_same_time(tmp_path: Path) -> None:
    model = PrintedModel(threading.Barrier(2, timeout=WAIT_S))
    printed = CarbonPrinted(model, Files(), tmp_path).read(FILE, SHEET)
    assert sorted(model.calls) == ["bars", "page"]
    assert printed.printed_scale == "1:100"


class HeldPage:
    """The Carbon reader's model: its page call is held until the test lets it go."""

    def __init__(self) -> None:
        self.inside, self.release = threading.Event(), threading.Event()

    def generate(
        self, jpeg: bytes, prompt: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        if prompt == contract.PAGE_PROMPT:
            self.inside.set()
            assert self.release.wait(WAIT_S)
            return envelope(PAGE_FORM)
        return envelope(TILE_FORM)


def test_the_page_call_both_carbon_readers_ask_is_paid_for_once(tmp_path: Path) -> None:
    held = HeldPage()
    with Image.open(io.BytesIO(png())) as image:
        page = image.convert("RGB")
    cached = tmp_path / contract.cache_name("page", pixel_digest(page))
    carbon = threading.Thread(target=CarbonReader(held, tmp_path).read, args=(page,))
    carbon.start()
    assert held.inside.wait(WAIT_S)  # the Carbon reader is paying for the page call
    printed_model = PrintedModel()
    got: list[PrintedSheet] = []
    printed = threading.Thread(
        target=lambda: got.append(CarbonPrinted(printed_model, Files(), tmp_path).read(FILE, SHEET))
    )
    printed.start()
    deadline = time.monotonic() + WAIT_S
    while waiting(cached) != 1:  # the printed reader waits for that call, not paying again
        assert time.monotonic() < deadline, "the printed reader did not wait for the page call"
        time.sleep(0.01)
    held.release.set()
    carbon.join(WAIT_S)
    printed.join(WAIT_S)
    assert printed_model.calls == ["bars"]  # its page reply came from the Carbon reader's call
    assert got[0].printed_scale == "1:100"
