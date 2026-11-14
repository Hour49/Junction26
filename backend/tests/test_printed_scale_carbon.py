"""RASTER_PRINTED_SCALE=carbon: the printed scale and facts read by gemini-4-carbon through the
merged Carbon client. A fake model stands in for the API: the Carbon reader's page call, the
scale-bar call, one full-resolution ticks call per bar; replies cached, failures noted."""

import io
import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.adapters.carbon import contract
from app.adapters.printed_scale.carbon import (
    BARS_PROMPT,
    TICKS_PROMPT,
    CarbonPrinted,
)
from app.adapters.raster_ocr.gemini import GeminiError, pixel_digest
from app.composition import build_pipeline
from app.core.drawing.model import Page
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.printed import printed_scale
from app.settings import Settings

PAGE = Page(page=1, width=2000, height=1000, unit="px")
FILE = DrawingFile(path="sheet.png", size=1, sha256="0" * 64, kind="png")
SHEET = Sheet(file=FILE, pages=(PAGE,))
PAGE_FORM = {
    "seen": "a dormitory floor plan",
    "title_block": {},
    "printed_scale": "1:200",
    "plans": [],
    "rooms": [],
    "rooms_listed": "none",
    "printed_facts": [
        {"text": "SECOND FLOOR = 48 DORMS", "subject": "room:bedroom", "value": 48,
         "unit": "count", "box_2d": [900, 600, 950, 800]},
        {"text": "TOTAL 1,000 SF", "subject": "floor_area", "value": 1000, "unit": "ft2",
         "box_2d": [950, 600, 980, 800]},
        {"text": "?", "subject": "nonsense", "value": 3, "unit": "count", "box_2d": None},
        {"text": "?", "subject": "door", "value": float("inf"), "unit": "count", "box_2d": None},
        {"text": "?", "subject": "door", "value": float("nan"), "unit": "count", "box_2d": None},
    ],
    "tables": [],
}  # fmt: skip
BARS_FORM = {
    "printed_scale": None,
    "scale_bars": [{"box_2d": [900, 100, 920, 300], "labels": "0 5 m"}],
}
# The crop around that box: x 0.065-0.335, y 0.875-0.945 (PAD_X 15% + 0.005, PAD_Y 100% + 0.005)
TICKS_FORM = {"ticks": [
    {"label": "0", "metres": 0, "point": [500, 129.63]},
    {"label": "5 m", "metres": 5, "point": [500, 870.37]},
]}  # fmt: skip


def envelope(form: object) -> dict[str, Any]:
    text = json.dumps(form)
    return {"candidates": [{"content": {"parts": [{"text": text}]}}], "usageMetadata": {}}


class Model:
    """The Carbon client's port: a fixed reply per prompt, every call recorded."""

    def __init__(self, fail: str | None = None) -> None:
        self.calls: list[tuple[str, tuple[int, int]]] = []
        self.fail = fail

    def generate(
        self, jpeg: bytes, prompt: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        kind = {contract.PAGE_PROMPT: "page", BARS_PROMPT: "bars", TICKS_PROMPT: "ticks"}[prompt]
        with Image.open(io.BytesIO(jpeg)) as image:
            self.calls.append((kind, image.size))
        if kind == self.fail:
            raise GeminiError("budget used up")
        return envelope({"page": PAGE_FORM, "bars": BARS_FORM, "ticks": TICKS_FORM}[kind])


class Files:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self, path: str) -> bytes:
        return self.data


def png(size: tuple[int, int] = (2000, 1000)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, "white").save(out, "PNG")
    return out.getvalue()


def test_the_page_bars_and_ticks_calls_give_the_printed_sheet(tmp_path: Path) -> None:
    model = Model()
    printed = CarbonPrinted(model, Files(png()), tmp_path).read(FILE, SHEET)
    kinds = [kind for kind, _ in model.calls]  # page and bars at the same time, then the bar's
    assert sorted(kinds[:2]) == ["bars", "page"] and kinds[2:] == ["ticks"]
    assert printed.printed_scale == "1:200"
    (bar,) = printed.bars
    assert bar.length_m == 5 and bar.text == "0 5 m"
    assert bar.start == pytest.approx((0.1, 0.91), abs=1e-3)
    assert bar.end == pytest.approx((0.3, 0.91), abs=1e-3)
    scale = printed_scale(printed, [PAGE], dpi=None)
    assert scale is not None and scale.m_per_unit == pytest.approx(5 / 400, rel=1e-3)
    dorms, area = printed.printed_facts  # the unknown subject, Infinity and NaN are left out
    assert (dorms.subject, dorms.value, dorms.unit) == ("room:bedroom", 48, "count")
    assert dorms.box == pytest.approx((0.6, 0.9, 0.8, 0.95))
    assert (area.value, area.unit) == (92.9, "m2")  # ft² as m², as the contract converts it
    assert printed.notes == ()


def test_the_bar_crop_is_sent_at_full_resolution_on_a_big_sheet(tmp_path: Path) -> None:
    model = Model()
    CarbonPrinted(model, Files(png((14000, 7000))), tmp_path).read(FILE, SHEET)
    sizes = dict(model.calls)
    assert max(sizes["page"]) == contract.MAX_SIDE  # the page is reduced
    # the crop is 27% x 7% of the page: 3780 x 490 px, sent at MAX_SIDE, nearly its own pixels
    assert sizes["ticks"] == contract.sent_size(3780, 490)


def test_replies_are_cached_and_the_page_reply_is_the_carbon_readers(tmp_path: Path) -> None:
    data = png()
    first = Model()
    CarbonPrinted(first, Files(data), tmp_path).read(FILE, SHEET)
    again = Model()
    CarbonPrinted(again, Files(data), tmp_path).read(FILE, SHEET)
    assert again.calls == []  # all three from the cache
    with Image.open(io.BytesIO(data)) as image:
        name = contract.cache_name("page", pixel_digest(image.convert("RGB")))
    assert (tmp_path / name).is_file()  # where CarbonReader looks for its page reply


def test_a_failed_call_is_a_note_not_an_error_and_is_not_cached(tmp_path: Path) -> None:
    model = Model(fail="page")
    printed = CarbonPrinted(model, Files(png()), tmp_path).read(FILE, SHEET)
    assert printed.printed_facts == () and len(printed.bars) == 1  # the bar is still read
    assert printed.notes == ("printed scale: the page call failed: budget used up",)
    retry = Model()
    CarbonPrinted(retry, Files(png()), tmp_path).read(FILE, SHEET)
    assert [kind for kind, _ in retry.calls] == ["page"]  # only the failed one is asked again


def test_a_bar_with_one_readable_tick_is_left_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(TICKS_FORM, "ticks", TICKS_FORM["ticks"][:1])
    printed = CarbonPrinted(Model(), Files(png()), tmp_path).read(FILE, SHEET)
    assert printed.bars == ()
    assert printed.printed_scale == "1:200"


def test_carbon_is_wired_with_a_key_and_refused_without_one(tmp_path: Path) -> None:
    on = {"raster_printed_scale": "carbon"}  # wraps whichever raster reader is set
    with pytest.raises(InvalidInputError, match="GEMINI_API_KEY is empty"):
        build_pipeline(Settings(_env_file=None, **on), tmp_path)  # pyright: ignore[reportCallIssue]
    keyed = Settings(_env_file=None, gemini_api_key="k", **on)  # pyright: ignore[reportCallIssue]
    build_pipeline(keyed, tmp_path)  # builds; no call is made until a sheet is read
