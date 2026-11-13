"""Synthetic PDF sheets for the tests, drawn with pypdfium2: no partner data in the repo.

Coordinates are given the way a person reads a page: points from the top left corner, y down,
which is also the frame the reader reports in. `SheetPdf` turns them into PDF user space.
"""

import ctypes
import io
import math
from collections.abc import Sequence

import pypdfium2
from pypdfium2 import raw

Point = tuple[float, float]
Rgb = tuple[int, int, int]
BLACK: Rgb = (0, 0, 0)
WHITE: Rgb = (255, 255, 255)


def rect(x0: float, y0: float, x1: float, y1: float) -> list[Point]:
    """A rectangle as a closed 5-point ring (the PDF then counts 5 segments)."""
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def ring(cx: float, cy: float, radius: float, points: int) -> list[Point]:
    """A closed ring of `points` points around a centre: a symbol with that many segments."""
    turn = 2 * math.pi / (points - 1)
    return [
        (cx + radius * math.cos(turn * at), cy + radius * math.sin(turn * at))
        for at in range(points - 1)
    ] + [(cx + radius, cy)]


class SheetPdf:
    """One page under construction. `path` and `text` draw; `pdf()` gives the file's bytes."""

    def __init__(self, width: float = 600, height: float = 400) -> None:
        self.width, self.height = width, height
        self._document = pypdfium2.PdfDocument.new()
        self._page = self._document.new_page(width, height)

    def path(
        self,
        *rings: Sequence[Point],
        stroke: Rgb | None = BLACK,
        width: float = 1.0,
        fill: Rgb | None = None,
        even_odd: bool = False,
    ) -> None:
        """One path object with a sub-path per ring. Stroke only unless `fill` is given."""
        first = rings[0][0]
        obj = raw.FPDFPageObj_CreateNewPath(first[0], self.height - first[1])
        for number, points in enumerate(rings):
            for at, (x, y) in enumerate(points):
                if at == 0 and number == 0:
                    continue
                draw = raw.FPDFPath_MoveTo if at == 0 else raw.FPDFPath_LineTo
                draw(obj, x, self.height - y)
        if stroke is not None:
            raw.FPDFPageObj_SetStrokeColor(obj, *stroke, 255)
            raw.FPDFPageObj_SetStrokeWidth(obj, width)
        fill_mode = raw.FPDF_FILLMODE_NONE
        if fill is not None:
            raw.FPDFPageObj_SetFillColor(obj, *fill, 255)
            fill_mode = raw.FPDF_FILLMODE_ALTERNATE if even_odd else raw.FPDF_FILLMODE_WINDING
        raw.FPDFPath_SetDrawMode(obj, fill_mode, stroke is not None)
        raw.FPDFPage_InsertObject(self._page.raw, obj)

    def twin(self, *rings: Sequence[Point], fill: Rgb, stroke: Rgb, width: float) -> None:
        """A shape the way an SVG converter writes it: the fill, then the outline again."""
        self.path(*rings, stroke=None, fill=fill, even_odd=True)
        self.path(*rings, stroke=stroke, width=width)

    def text(self, text: str, x: float, y: float, size: float = 6.0) -> None:
        """A text object of its own, starting at (x, y) on its baseline."""
        obj = raw.FPDFPageObj_NewTextObj(self._document.raw, b"Helvetica", size)
        encoded = (text + "\x00").encode("utf-16-le")
        buffer = ctypes.create_string_buffer(encoded, len(encoded))
        raw.FPDFText_SetText(obj, ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ushort)))
        raw.FPDFPageObj_Transform(obj, 1, 0, 0, 1, x, self.height - y)
        raw.FPDFPage_InsertObject(self._page.raw, obj)

    def rotate(self, degrees: int) -> None:
        self._page.set_rotation(degrees)

    def add_page(self) -> None:
        """A second, empty page; drawing stays on the first."""
        self._document.new_page(self.width, self.height)

    def pdf(self) -> bytes:
        raw.FPDFPage_GenerateContent(self._page.raw)
        buffer = io.BytesIO()
        self._document.save(buffer)
        return buffer.getvalue()

    def png(self, scale: int = 2) -> bytes:
        """The page rendered, as the dataset's PNG of a sheet is."""
        document = pypdfium2.PdfDocument(self.pdf())
        try:
            image = document[0].render(scale=scale).to_pil()
        finally:
            document.close()
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        return buffer.getvalue()
