"""What a schedule is made of on a drawn PDF page: its ruling lines and its characters.

Positions are points on the page as rendered (origin top left, y down, after /Rotate), the frame
of `vector_pdf.objects`, whose paths give the rulings. Characters come from pdfium's text page one
by one: a text object on a schedule often runs across several cells ("100.A1 X. VEST. 100 2' - 11
3/16" ..." is one object), so only character positions can place text in a cell.
"""

from dataclasses import dataclass
from itertools import pairwise

import pypdfium2
from pypdfium2 import raw

from app.adapters.pdfium_lock import PDFIUM
from app.adapters.vector_pdf.objects import FILL_NONE, Bounds, PdfPath, read_page

STRAIGHT = 0.5  # pt: an edge whose ends differ less than this across is axis-aligned
SHORTEST = 1.0  # pt: shorter edges are dots or arrow tips, not rulings


@dataclass(frozen=True)
class Char:
    text: str
    bounds: Bounds  # the glyph's loose box: its advance across, the font's height up
    size: float  # the loose box's height, about the font size: pdfium's own font size leaves
    # out the text matrix, so on some sheets it is hundreds of points


@dataclass(frozen=True)
class Rule:
    """An axis-aligned stroke: at y from x `start` to `end` (horizontal), or at x from y."""

    horizontal: bool
    at: float
    start: float
    end: float


@dataclass(frozen=True)
class TablePage:
    width: float
    height: float
    chars: tuple[Char, ...]
    rules: tuple[Rule, ...]


def read_table_page(data: bytes, index: int = 0) -> TablePage:
    page = read_page(data, index)
    return TablePage(
        width=page.width,
        height=page.height,
        chars=_chars(data, index),
        rules=tuple(rule for path in page.paths for rule in rules_of(path)),
    )


def rules_of(path: PdfPath) -> list[Rule]:
    """The axis-aligned edges of a drawn path. A filled ring is closed by its fill, so its last
    edge counts too (a cell drawn as a filled rectangle)."""
    if not path.stroked and path.fill_mode == FILL_NONE:
        return []
    found: list[Rule] = []
    for ring in path.rings:
        points = list(ring)
        if path.fill_mode != FILL_NONE and len(points) > 2 and points[0] != points[-1]:
            points.append(points[0])
        for (x0, y0), (x1, y1) in pairwise(points):
            if abs(y1 - y0) < STRAIGHT and abs(x1 - x0) >= SHORTEST:
                found.append(Rule(True, (y0 + y1) / 2, min(x0, x1), max(x0, x1)))
            elif abs(x1 - x0) < STRAIGHT and abs(y1 - y0) >= SHORTEST:
                found.append(Rule(False, (x0 + x1) / 2, min(y0, y1), max(y0, y1)))
    return found


def _chars(data: bytes, index: int) -> tuple[Char, ...]:
    with PDFIUM:  # pdfium is not thread-safe (app/adapters/pdfium_lock.py)
        document = pypdfium2.PdfDocument(data)
        try:
            page = document[index]
            width, height = page.get_size()
            left, bottom, right, top = page.get_bbox()
            quarter_turns = page.get_rotation() // 90

            def rendered(x: float, y: float) -> tuple[float, float]:
                u, v = (x - left) / (right - left), (top - y) / (top - bottom)
                for _ in range(quarter_turns):  # /Rotate turns the page clockwise
                    u, v = 1 - v, u
                return u * width, v * height

            textpage = page.get_textpage()
            found: list[Char] = []
            for at in range(textpage.count_chars()):
                text = chr(raw.FPDFText_GetUnicode(textpage.raw, at))
                if not text.strip() or raw.FPDFText_IsGenerated(textpage.raw, at) == 1:
                    continue
                x0, y0, x1, y1 = textpage.get_charbox(at, loose=True)
                (ax, ay), (bx, by) = rendered(x0, y0), rendered(x1, y1)
                bounds = (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
                found.append(Char(text, bounds, bounds[3] - bounds[1]))
            return tuple(found)
        finally:
            document.close()
