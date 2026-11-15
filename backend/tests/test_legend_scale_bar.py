"""The scale bar `read_legend` reads (pic-cls Round 7a, the clinic pages): a size label misread as a
bar label never gives a scale (C), and a bar label OCR glued to the ratio is still read (B). The OCR
is a fake that returns the lines a test places, so each case is exact; the bars are drawn ink."""

from collections.abc import Sequence

import numpy as np
import pytest

from app.adapters.discipline_pictures.legend import BAR_LABEL, read_legend
from app.adapters.raster_ocr.reader import Quad
from app.core.drawing.model import Page
from app.core.pipeline.printed import printed_scale

W, H = 2000, 1400
BAR_PX = 295  # 5 m at 1:100 and 150 dpi: 0.0169 m/px
PAGE = [Page(page=1, width=W, height=H, unit="px")]

Box = tuple[int, int, int, int]


class FakeOcr:
    """Detects the placed lines; a cut carries the line's index, which recognise reads back."""

    def __init__(self, lines: Sequence[tuple[str, Box]]) -> None:
        self.lines = list(lines)

    def detect(self, image: np.ndarray) -> list[Quad]:
        return [[(a, b), (c, b), (c, d), (a, d)] for _, (a, b, c, d) in self.lines]

    def cut(self, image: np.ndarray, quad: Quad) -> np.ndarray:
        corner = tuple(quad[0])
        return np.array([[next(n for n, (_, box) in enumerate(self.lines) if box[:2] == corner)]])

    def recognise(self, crops: Sequence[np.ndarray]) -> list[tuple[str, float]]:
        return [(self.lines[int(crop[0, 0])][0], 0.9) for crop in crops]


def page(*bars: tuple[int, int, int]) -> np.ndarray:
    """A white page with black bars (x0, x1, y middle), 6 px thick."""
    rgb = np.full((H, W, 3), 255, dtype=np.uint8)
    for x0, x1, mid in bars:
        rgb[mid - 3 : mid + 3, x0:x1] = 0
    return rgb


def label(text: str, x0: int, mid: int) -> tuple[str, Box]:
    """A text line 20 px high starting 10 px right of a bar's end."""
    return text, (x0, mid - 10, x0 + 12 * len(text), mid + 10)


NOTE = label("Heating plan level 1", 900, 200)  # the page's other text: a line height


def scale_of(rgb: np.ndarray, ocr: FakeOcr) -> float | None:
    _, printed = read_legend(rgb, ocr)
    found = printed_scale(printed, PAGE, None)
    return None if found is None else found.m_per_unit


# --- C: a bar that disagrees with the printed ratio is not a bar --------------------------------


def test_a_size_label_read_as_a_bar_label_gives_no_scale_against_the_printed_ratio() -> None:
    # the 11x page: a pipe size OCR'd as "15 m" beside an 81 px pipe stub, ratio 1:100 printed
    rgb = page((500, 581, 700))
    ocr = FakeOcr([NOTE, label("15 m", 591, 700), label("1:100", 100, 1300)])
    _, printed = read_legend(rgb, ocr)
    assert printed.bars == ()  # 15 m in 81 px at 1:100 is 14 dpi: no scan prints that
    assert printed_scale(printed, PAGE, None) is None  # no scale rather than one 11x off


def test_the_true_bar_is_kept_and_the_misread_one_dropped() -> None:
    rgb = page((100, 100 + BAR_PX, 1300), (500, 581, 700))
    ocr = FakeOcr([NOTE, label("15 m", 591, 700), label("5 m 1:100", 100 + BAR_PX + 10, 1300)])
    assert scale_of(rgb, ocr) == pytest.approx(5 / BAR_PX, rel=0.01)


def test_a_bar_is_kept_when_any_printed_ratio_agrees_with_it() -> None:
    # a detail at 1:20 printed first; the plan's bar is at 1:100
    rgb = page((100, 100 + BAR_PX, 1300))
    ocr = FakeOcr([NOTE, label("Detail A 1:20", 900, 400), label("5 m 1:100", 110 + BAR_PX, 1300)])
    assert scale_of(rgb, ocr) == pytest.approx(5 / BAR_PX, rel=0.01)


def test_with_no_ratio_printed_a_bar_is_taken_as_it_reads() -> None:
    rgb = page((100, 100 + BAR_PX, 1300))
    ocr = FakeOcr([NOTE, label("5 m", 110 + BAR_PX, 1300)])
    assert scale_of(rgb, ocr) == pytest.approx(5 / BAR_PX, rel=0.01)


# --- B: the bar label as OCR reads it on a scan ------------------------------------------------


@pytest.mark.parametrize("text", ["5 m1:100", "5m1:100", "5.m 1:100", "5 m 1:100", "5 m", "2,5 m"])
def test_a_bar_label_glued_to_its_ratio_is_still_a_bar_label(text: str) -> None:
    assert BAR_LABEL.match(text), text


@pytest.mark.parametrize("text", ["5 mm", "5 m:", "12.5 m2", "5 m²", "5 m1", "Room 5 m2 1:100"])
def test_sizes_areas_and_m_colon_text_are_not_bar_labels(text: str) -> None:
    assert not BAR_LABEL.match(text), text


def test_a_scan_whose_bar_label_ocr_glued_to_the_ratio_is_scaled_by_its_bar() -> None:
    rgb = page((100, 100 + BAR_PX, 1300))
    ocr = FakeOcr([NOTE, label("5 m1:100", 110 + BAR_PX, 1300)])
    assert scale_of(rgb, ocr) == pytest.approx(5 / BAR_PX, rel=0.01)
