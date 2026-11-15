"""PRINTED_OCR_CHECK: an OCR engine reads again the printed digits the Carbon reader gave (the
printed scale text and printed facts), and a value it reads differently is not used silently.
The core rule (app/core/pipeline/printed_ocr.py) is tested on tokens; the tiling adapter
(app/adapters/raster_ocr/tiles.py) with a fake engine. Synthetic."""

import io
import itertools
from collections.abc import Sequence

import numpy as np
import pytest
from PIL import Image

from app.adapters.printed_scale import PrintedScale
from app.adapters.raster_ocr.reader import Quad
from app.adapters.raster_ocr.tiles import PrintedOcr, joined, ruled_out, tile_origins
from app.composition import _printed
from app.core.drawing.model import Box, Page, Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.printed import PrintedFact, PrintedSheet
from app.core.pipeline.printed_ocr import (
    Confirmation,
    OcrToken,
    checked,
    confirm_printed,
    numbers_in,
)
from app.settings import Settings

BOX: Box = (0.5, 0.5, 0.6, 0.52)
INSIDE: Box = (0.51, 0.505, 0.55, 0.515)
FAR: Box = (0.1, 0.1, 0.2, 0.12)


def token(text: str, box: Box = INSIDE) -> OcrToken:
    return OcrToken(text=text, box=box, score=0.9)


def fact(text: str, value: float, unit: str = "count", subject: str = "room:bedroom"):
    return PrintedFact(text=text, subject=subject, value=value, unit=unit, box=BOX)


@pytest.mark.parametrize(
    ("text", "numbers"),
    [
        ("48", [{48.0}]),
        ("6,095", [{6095.0, 6.095}]),
        ("12,45", [{12.45}]),
        ("26 562 SF", [{26562.0}]),
        ("1.240,5", [{1240.5}]),
        ("4O", [{40.0}]),  # O next to a digit is a zero
        ("l2", [{12.0}]),  # l next to a digit is a one
        ("LEVEL", []),
        ("2 = 48 DORMS", [{2.0}, {48.0}]),
    ],
)
def test_numbers_in(text: str, numbers: list[set[float]]) -> None:
    assert [set(n.values) for n in numbers_in(text)] == numbers


@pytest.mark.parametrize(
    ("printed", "tokens", "outcome", "read"),
    [
        (fact("48 DORMS", 48), ["48", "DORMS"], "confirmed", None),
        (fact("48 DORMS", 48), ["46 DORMS"], "disagrees", "46"),
        (fact("48 DORMS", 48), ["4", "DORMS"], "not_found", None),  # 4 is no 2-digit number
        (fact("48 DORMS", 48), [], "not_found", None),
        (fact("914 SF", 914, "m2"), ["4 SF", "914"], "confirmed", None),  # a stray 4 is no reading
        (fact("6,095 SF", 566.2, "m2"), ["6.095"], "confirmed", None),  # converted: text decides
        (fact("1,240 SF", 115.2, "m2"), ["12.40"], "disagrees", "12.40"),  # a decimal slip
        (fact("SECOND FLOOR = 48 DORMS", 48), ["SECOND", "FL00R", "=", "48"], "confirmed", None),
        (fact("LEVEL 2 = 48 DORMS", 48), ["LEVEL 2", "= 43 DORMS"], "disagrees", "43"),
        (fact("FOUR DORMS", 4), ["4"], "not_found", None),  # Carbon printed no digits
    ],
)
def test_a_fact_is_confirmed_disagreed_or_not_found(
    printed: PrintedFact, tokens: list[str], outcome: str, read: str | None
) -> None:
    sheet = PrintedSheet(printed_facts=(printed,))
    [found] = confirm_printed(sheet, [token(t) for t in tokens])
    assert (found.outcome, found.read) == (outcome, read)


def test_a_token_outside_the_facts_box_is_not_read_for_it() -> None:
    sheet = PrintedSheet(printed_facts=(fact("48 DORMS", 48),))
    [found] = confirm_printed(sheet, [token("46", FAR)])
    assert found.outcome == "not_found"


def test_a_fact_without_a_box_is_not_checked() -> None:
    boxless = PrintedFact(text="48 DORMS", subject="room", value=48, unit="count")
    assert confirm_printed(PrintedSheet(printed_facts=(boxless,)), [token("46")]) == []


@pytest.mark.parametrize(
    ("scale", "tokens", "outcome", "read"),
    [
        ('1" = 40\'-0"', ['SCALE: 1" = 40\'-0"'], "confirmed", None),
        ("1:200", ["1 : 200"], "confirmed", None),
        ("1:200", ["1:100"], "disagrees", "1:100"),
        ("1:200", ["1:100", "1:20"], "not_found", None),  # two other scales: a detail's?
        ("1:200", ['1/4" = 1\'-0"'], "not_found", None),  # another family
        ('3/32" = 1\'-0"', ['3/16" = 1\'-0"'], "disagrees", '3/16" = 1\'-0"'),
        ('3/32" = 1\'-0"', ['3⁄32" = 1′0″'], "confirmed", None),  # noqa: RUF001
        ("1:200", [], "not_found", None),
        ("bar", ["1:100"], "not_found", None),  # no ratio to check
    ],
)
def test_the_scale_text_is_looked_for_on_the_whole_sheet(
    scale: str, tokens: list[str], outcome: str, read: str | None
) -> None:
    sheet = PrintedSheet(printed_scale=scale)
    found = confirm_printed(sheet, [token(t, FAR) for t in tokens])
    assert [(c.outcome, c.read) for c in found] == ([(outcome, read)] if found else [])
    assert found or scale == "bar"


def test_nothing_disagreed_leaves_the_printed_sheet_as_it_was() -> None:
    sheet = PrintedSheet(printed_scale="1:200", printed_facts=(fact("48 DORMS", 48),))
    confirmations = confirm_printed(sheet, [token("48"), token("1:200", FAR)])
    assert checked(sheet, confirmations) == (sheet, [])


def test_a_disagreed_count_is_a_second_value_with_ocrs_reading() -> None:
    sheet = PrintedSheet(printed_facts=(fact("48 DORMS", 48),))
    kept, extra = checked(sheet, confirm_printed(sheet, [token("46")]))
    assert kept.printed_facts == sheet.printed_facts  # Carbon's value still stands
    [second] = extra
    assert (second.quantity, second.subject.ref) == ("room_count", "room:bedroom")
    assert (second.value.value, second.value.method, second.value.box) == (46, "annotation", BOX)
    assert kept.notes == ("printed on the sheet: 48 DORMS: OCR reads 46 there",)


def test_a_disagreed_area_is_a_note_only() -> None:
    sheet = PrintedSheet(printed_facts=(fact("1,240 SF", 115.2, "m2", "floor_area"),))
    kept, extra = checked(sheet, confirm_printed(sheet, [token("12.40")]))
    assert extra == []
    assert kept.notes == ("printed on the sheet: 1,240 SF: OCR reads 12.40 there",)


def test_a_disagreed_scale_text_is_withheld() -> None:
    sheet = PrintedSheet(printed_scale="1:200")
    kept, extra = checked(sheet, confirm_printed(sheet, [token("1:100", FAR)]))
    assert (kept.printed_scale, extra) == (None, [])
    assert kept.notes == (
        "printed scale 1:200: OCR reads 1:100 there: not used, left for a person to check",
    )


# -- the adapter: tiles, ruling lines, rotations, edge duplicates (a fake engine) --


def test_tiles_cover_the_region_with_overlap() -> None:
    assert tile_origins(1000, 1600) == [0]
    starts = tile_origins(4000, 1600)
    assert starts[0] == 0 and starts[-1] == 4000 - 1600
    assert all(b - a <= 1600 * 0.95 for a, b in itertools.pairwise(starts))


def test_overlapping_boxes_are_read_as_one() -> None:
    a, b, apart = (0.1, 0.1, 0.2, 0.2), (0.15, 0.15, 0.3, 0.25), (0.6, 0.6, 0.7, 0.7)
    assert sorted(joined([a, apart, b])) == [(0.1, 0.1, 0.3, 0.25), apart]


def test_long_ruling_lines_are_removed_and_text_kept() -> None:
    pixels = np.full((200, 600, 3), 255, np.uint8)
    pixels[100, :, :] = 0  # a ruling line across the whole region
    pixels[40:60, 50:56, :] = 0  # a stroke of a digit
    out = ruled_out(pixels)
    assert out[100, 300].tolist() == [255, 255, 255]
    assert out[50, 52].tolist() == [0, 0, 0]


class FakeEngine:
    """Finds one text box per dark blob row band and reads it as `text` only upright."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.detected: list[tuple[int, int]] = []

    def detect(self, image: np.ndarray) -> list[Quad]:
        self.detected.append(image.shape[:2])
        ys, xs = np.nonzero(image[:, :, 0] < 128)
        if not len(xs):
            return []
        x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        return [[(x1, y1), (x2, y1), (x2, y2), (x1, y2)]]

    def recognise(self, crops: Sequence[np.ndarray]) -> list[tuple[str, float]]:
        # the crop's top-left pixel is marked dark when upright: any other turn reads poorly
        return [(self.text, 0.9) if c[0, 0, 0] < 128 else ("?", 0.2) for c in crops]

    def cut(self, image: np.ndarray, quad: Quad) -> np.ndarray:
        (x1, y1), _, (x2, y2), _ = quad
        return np.ascontiguousarray(image[int(y1) : int(y2), int(x1) : int(x2)])


def png(width: int, height: int, mark: tuple[int, int, int, int]) -> bytes:
    pixels = np.full((height, width, 3), 255, np.uint8)
    x1, y1, x2, y2 = mark
    pixels[y1:y2, x1:x2, :] = 0
    out = io.BytesIO()
    Image.fromarray(pixels).save(out, format="PNG")
    return out.getvalue()


class Files:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self, path: str) -> bytes:
        return self.data


FILE = DrawingFile(path="plan.png", size=1, sha256="0" * 64, kind="png")


def test_the_adapter_reads_the_facts_box_in_page_fractions() -> None:
    data = png(2000, 1000, (1050, 505, 1150, 515))  # inside BOX, which is 1000-1200 x 500-520
    engine = FakeEngine("48")
    sheet = Sheet(file=FILE, pages=(Page(page=1, width=2000, height=1000, unit="px"),))
    printed = PrintedSheet(printed_facts=(fact("48 DORMS", 48),))
    tokens = PrintedOcr(engine, Files(data), whole_sheet_px=0).tokens(FILE, sheet, printed)
    assert [t.text for t in tokens] == ["48"]
    [t] = tokens
    assert BOX[0] <= t.box[0] < t.box[2] <= BOX[2] and BOX[1] <= t.box[1] < t.box[3] <= BOX[3]
    assert engine.detected and max(h for h, _ in engine.detected) >= 48  # small crops enlarged


def test_the_adapter_reads_the_whole_sheet_for_the_scale_only_when_small() -> None:
    data = png(400, 200, (10, 10, 60, 20))
    sheet = Sheet(file=FILE, pages=(Page(page=1, width=400, height=200, unit="px"),))
    printed = PrintedSheet(printed_scale="1:100")
    small = PrintedOcr(FakeEngine("1:100"), Files(data), whole_sheet_px=400 * 200)
    big = PrintedOcr(FakeEngine("1:100"), Files(data), whole_sheet_px=400 * 200 - 1)
    assert [t.text for t in small.tokens(FILE, sheet, printed)] == ["1:100"]
    assert big.tokens(FILE, sheet, printed) == []


# -- the wiring: PRINTED_OCR_CHECK=on checks before with_printed; off is today's --


class Inner:
    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return Extracted(method="detector", scale=Scale(status="no_scale"))


class Reader:
    def __init__(self, printed: PrintedSheet) -> None:
        self.printed = printed

    def read(self, source: DrawingFile, sheet: Sheet) -> PrintedSheet:
        return self.printed


class Checker:
    def __init__(self, tokens: list[OcrToken]) -> None:
        self._tokens = tokens

    def tokens(self, source: DrawingFile, sheet: Sheet, printed: PrintedSheet) -> list[OcrToken]:
        return self._tokens


def test_printed_scale_with_a_checker_adds_ocrs_reading() -> None:
    sheet = Sheet(file=FILE, pages=(Page(page=1, width=2000, height=1000, unit="px"),))
    printed = PrintedSheet(printed_facts=(fact("48 DORMS", 48),))
    files = Files(png(10, 10, (0, 0, 1, 1)))
    plain = PrintedScale(Inner(), Reader(printed), files).extract(FILE, sheet)
    agreed = PrintedScale(Inner(), Reader(printed), files, checker=Checker([token("48")]))
    assert agreed.extract(FILE, sheet).model_dump(exclude={"steps"}) == plain.model_dump(
        exclude={"steps"}
    )
    differs = PrintedScale(Inner(), Reader(printed), files, checker=Checker([token("46")]))
    out = differs.extract(FILE, sheet)
    assert [m.value.method for m in out.printed] == [m.value.method for m in plain.printed] + [
        "annotation"
    ]
    assert "printed on the sheet: 48 DORMS: OCR reads 46 there" in out.notes
    assert "OCR: 0 confirmed, 1 disagrees, 0 not found" in out.steps[-1].did


def test_the_setting_picks_the_checker() -> None:
    def built(check: str) -> object:
        settings = Settings(
            _env_file=None,  # pyright: ignore[reportCallIssue]
            raster_printed_scale="carbon",
            printed_ocr_check=check,  # pyright: ignore[reportArgumentType]
            gemini_api_key="k",  # pyright: ignore[reportArgumentType]
        )
        return _printed(settings, Inner(), Files(b""), lambda path: None)

    assert vars(built("off"))["_checker"] is None
    assert isinstance(vars(built("on"))["_checker"], PrintedOcr)


def test_confirmations_say_what_was_checked() -> None:
    sheet = PrintedSheet(printed_facts=(fact("48 DORMS", 48),))
    assert confirm_printed(sheet, [token("48")]) == [
        Confirmation(kind="fact", printed="48 DORMS", outcome="confirmed", index=0)
    ]


def test_a_fact_ocr_disagrees_with_decides_no_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """PRINTED_TOTAL_ANSWERS makes an exactly matching printed count the answer: not one OCR
    reads differently."""
    import app.adapters.printed_scale as module

    seen: list[list[PrintedFact]] = []

    def answers(found: Extracted, facts: Sequence[PrintedFact]) -> Extracted:
        seen.append(list(facts))
        return found

    monkeypatch.setattr(module, "printed_answers", answers)
    sheet = Sheet(file=FILE, pages=(Page(page=1, width=2000, height=1000, unit="px"),))
    printed = PrintedSheet(printed_facts=(fact("48 DORMS", 48),))
    files = Files(png(10, 10, (0, 0, 1, 1)))
    for tokens in ([token("48")], [token("46")]):
        PrintedScale(
            Inner(), Reader(printed), files, answers=True, checker=Checker(tokens)
        ).extract(FILE, sheet)
    assert seen == [list(printed.printed_facts), []]
