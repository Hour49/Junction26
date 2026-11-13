"""The drawn objects of a PDF page, through pypdfium2: every vector path with its style and
vertices, and every text object with its own text.

Coordinates are points on the page as rendered: origin top left, y down, after the page's /Rotate,
measured from the corner of the visible box. So `x / page.width` is the page fraction
extraction_v1 wants, and an area is still in pt².

Text is read per text object. The page-level text joins neighbouring labels ("Bad Schlafzimmer
2.38") and interleaves overlapping ones; per object, a label is exact. Objects inside a form
XObject are not read: the sheets we read draw everything on the page itself.
"""

import ctypes
from collections.abc import Callable
from dataclasses import dataclass

import pypdfium2
from pypdfium2 import raw

FILL_NONE, FILL_EVEN_ODD, FILL_WINDING = 0, 1, 2

Point = tuple[float, float]
Bounds = tuple[float, float, float, float]  # x0, y0, x1, y1 with y0 the top
Rgb = tuple[int, int, int]


@dataclass(frozen=True)
class PdfPath:
    segments: int  # as the PDF counts them: a rectangle closed by a line has 5
    fill_mode: int  # FILL_NONE, FILL_EVEN_ODD or FILL_WINDING
    stroked: bool
    stroke: Rgb
    width: float  # the stroke width the PDF states, 2 decimals
    fill: Rgb
    rings: tuple[tuple[Point, ...], ...]  # one per sub-path; curve control points left out

    @property
    def points(self) -> tuple[Point, ...]:
        return tuple(point for ring in self.rings for point in ring)

    @property
    def bounds(self) -> Bounds:
        return bounds_of(self.points)


@dataclass(frozen=True)
class PdfText:
    text: str
    bounds: Bounds

    @property
    def centre(self) -> Point:
        x0, y0, x1, y1 = self.bounds
        return (x0 + x1) / 2, (y0 + y1) / 2


@dataclass(frozen=True)
class PdfPage:
    width: float  # points, as rendered
    height: float
    page_count: int  # pages in the document this page came from
    paths: tuple[PdfPath, ...]
    texts: tuple[PdfText, ...]
    text: str  # the page text in reading order, for words that span text objects


def bounds_of(points: tuple[Point, ...]) -> Bounds:
    xs, ys = [x for x, _ in points], [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def read_page(data: bytes, index: int = 0) -> PdfPage:
    document = pypdfium2.PdfDocument(data)
    try:
        page = document[index]
        width, height = page.get_size()
        left, bottom, right, top = page.get_bbox()  # the media box cut by the crop box
        quarter_turns = page.get_rotation() // 90

        def rendered(x: float, y: float) -> Point:
            u, v = (x - left) / (right - left), (top - y) / (top - bottom)
            for _ in range(quarter_turns):  # /Rotate turns the page clockwise
                u, v = 1 - v, u
            return u * width, v * height

        textpage = page.get_textpage()
        paths: list[PdfPath] = []
        texts: list[PdfText] = []
        for obj in page.get_objects(max_depth=1):
            kind = raw.FPDFPageObj_GetType(obj.raw)
            if kind == raw.FPDF_PAGEOBJ_PATH:
                rings = _rings(obj, rendered)
                if rings:
                    paths.append(_path(obj, rings))
            elif kind == raw.FPDF_PAGEOBJ_TEXT:
                text = _object_text(obj, textpage)
                if text:
                    x0, y0, x1, y1 = obj.get_bounds()
                    texts.append(PdfText(text, bounds_of((rendered(x0, y0), rendered(x1, y1)))))
        return PdfPage(
            width=width,
            height=height,
            page_count=len(document),
            paths=tuple(paths),
            texts=tuple(texts),
            text=textpage.get_text_range(),
        )
    finally:
        document.close()


def _rgb(obj: pypdfium2.PdfObject, getter: Callable[..., object]) -> Rgb:
    r, g, b, a = (ctypes.c_uint() for _ in range(4))
    getter(obj.raw, r, g, b, a)
    return r.value, g.value, b.value


def _path(obj: pypdfium2.PdfObject, rings: tuple[tuple[Point, ...], ...]) -> PdfPath:
    width = ctypes.c_float()
    raw.FPDFPageObj_GetStrokeWidth(obj.raw, width)
    fill_mode, stroked = ctypes.c_int(), ctypes.c_int()
    raw.FPDFPath_GetDrawMode(obj.raw, fill_mode, stroked)
    return PdfPath(
        segments=raw.FPDFPath_CountSegments(obj.raw),
        fill_mode=fill_mode.value,
        stroked=bool(stroked.value),
        stroke=_rgb(obj, raw.FPDFPageObj_GetStrokeColor),
        width=round(width.value, 2),
        fill=_rgb(obj, raw.FPDFPageObj_GetFillColor),
        rings=rings,
    )


def _rings(
    obj: pypdfium2.PdfObject, rendered: Callable[[float, float], Point]
) -> tuple[tuple[Point, ...], ...]:
    """The sub-paths of a path object. A curve gives three segments (two control points, then
    its end); only the end is a point of the outline."""
    a, b, c, d, e, f = obj.get_matrix().get()
    rings: list[list[Point]] = []
    curve_part = 0
    for index in range(raw.FPDFPath_CountSegments(obj.raw)):
        segment = raw.FPDFPath_GetPathSegment(obj.raw, index)
        kind = raw.FPDFPathSegment_GetType(segment)
        if kind == raw.FPDF_SEGMENT_BEZIERTO:
            curve_part = (curve_part + 1) % 3
            if curve_part:
                continue
        x, y = ctypes.c_float(), ctypes.c_float()
        raw.FPDFPathSegment_GetPoint(segment, x, y)
        if kind == raw.FPDF_SEGMENT_MOVETO or not rings:
            rings.append([])
        rings[-1].append(rendered(a * x.value + c * y.value + e, b * x.value + d * y.value + f))
    return tuple(tuple(ring) for ring in rings)


def _object_text(obj: pypdfium2.PdfObject, textpage: pypdfium2.PdfTextPage) -> str:
    size = raw.FPDFTextObj_GetText(obj.raw, textpage.raw, None, 0)  # bytes, with the final NUL
    if size <= 2:
        return ""
    buffer = ctypes.create_string_buffer(size)
    raw.FPDFTextObj_GetText(
        obj.raw, textpage.raw, ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ushort)), size
    )
    return buffer.raw.decode("utf-16-le").rstrip("\x00").strip()
