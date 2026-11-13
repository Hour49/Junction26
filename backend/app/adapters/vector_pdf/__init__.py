"""`EXTRACTOR_VECTOR=pdf`: the vector route's `Extractor`, reading a drawn (not scanned) PDF.

It reads the source PDF and nothing else: no DXF, SVG or IFC next to it, no model call. Page 1's
paths and text objects (objects.py) go to the reading rules of the sheet style they match
(swiss.py, ifc_render.py); the scale comes from the sheet's own text and scale bar (scale.py).

Positions are fractions of the PDF page. A PNG of the same sheet is that page rendered, so the
fractions hold on it too and only the metres per unit change (metres per point x PDF width /
PNG width). A sheet whose shape differs from the PDF page is not that render, and gets nothing.

`read` says which classes the matched style's rules look for (its `LOOKS_FOR`). It is empty when
only the scale was read or nothing was, so a class nobody looked for never counts as 0.

`SECOND_COUNTER=pdf` is `PdfSecondCounter`: the second readings the same page gives of what the
extractor measured, for ingest stage 8.
"""

from app.adapters.vector_pdf import frame, ifc_render, swiss
from app.adapters.vector_pdf.objects import Bounds, PdfPage, read_page
from app.adapters.vector_pdf.scale import read_bar, read_ratio, read_scale
from app.core.drawing.model import Box, MeasuredValue, MeasureMethod, Scale, Subject
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, Sheet
from app.core.pipeline.ports import DrawingFiles

STYLES = (swiss, ifc_render)
SAME_SHAPE = 0.01  # relative difference of width / height between the PDF page and the sheet


class PdfVectorExtractor:
    def __init__(self, files: DrawingFiles) -> None:
        self._files = files

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        page = _page_behind(self._files, source, sheet)
        if isinstance(page, str):
            return _nothing(page)
        target = sheet.pages[0]
        scale, notes = read_scale(page)
        style = next((style for style in STYLES if style.matches(page)), None)
        if style is None:
            return Extracted(
                method="parser",
                scale=_per_unit(scale, page.width / target.width),
                read=(),
                notes=(*notes, "no sheet style we have reading rules for: only the scale was read"),
            )
        reading = style.read(page, scale.m_per_unit)
        if page.page_count > 1:
            notes = (*notes, f"only page 1 of {page.page_count} was read")
        return Extracted(
            method="parser",
            scale=_per_unit(scale, page.width / target.width),
            plans=reading.plans,
            elements=reading.elements,
            rooms=reading.rooms,
            apartments=reading.apartments,
            read=style.LOOKS_FOR,
            notes=(*notes, *reading.notes),
        )


class PdfSecondCounter:
    """What a drawn PDF sheet says a second time about a quantity the extractor measured:

    - the scale, as the sheet prints it and as its scale bar measures it, when it has both;
    - on a swiss plan, the area printed in each room. The extractor's area for the room is its
      outline at the sheet's scale.

    It reads the page again and uses the same room rules as the extractor, so the room ids are
    the extractor's."""

    def __init__(self, files: DrawingFiles) -> None:
        self._files = files

    def measure(self, source: DrawingFile, sheet: Sheet) -> list[Measurement]:
        page = _page_behind(self._files, source, sheet)
        if isinstance(page, str):
            return []
        target = sheet.pages[0]
        measured: list[Measurement] = []
        ratio, bar = read_ratio(page), read_bar(page)
        if ratio and bar:
            readings: tuple[tuple[MeasureMethod, float, Bounds | None], ...] = (
                ("scale_text", ratio[0], ratio[2]),
                ("scale_bar", *bar),
            )
            for method, m_per_pt, at in readings:
                measured.append(
                    Measurement(
                        quantity="scale",
                        subject=Subject(kind="sheet", ref=None),
                        value=MeasuredValue(
                            value=_in_sheet_units(m_per_pt, page.width / target.width),
                            unit=f"m/{target.unit}",
                            method=method,
                            page=1,
                            box=None if at is None else _box(at, page),
                        ),
                    )
                )
        if swiss.matches(page):
            for room, m2, at in swiss.printed_areas(page):
                measured.append(
                    Measurement(
                        quantity="room_area",
                        subject=Subject(kind="room", ref=room),
                        value=MeasuredValue(
                            value=m2, unit="m2", method="printed_label", page=1, box=_box(at, page)
                        ),
                    )
                )
        return measured


def _page_behind(files: DrawingFiles, source: DrawingFile, sheet: Sheet) -> PdfPage | str:
    """Page 1 of the source PDF when `sheet` is that page (the PDF itself, or its render), else
    why it is not."""
    if source.kind != "pdf":
        return f"the source {source.path} is {source.kind}, not a PDF"
    page = read_page(files.read(source.path))
    target = sheet.pages[0]
    shape, target_shape = page.width / page.height, target.width / target.height
    if abs(shape / target_shape - 1) > SAME_SHAPE:
        return f"{sheet.file.path} is not page 1 of {source.path} rendered"
    return page


def _box(at: Bounds, page: PdfPage) -> Box:
    return frame.box((at[:2], at[2:]), page)


def _nothing(why: str) -> Extracted:
    return Extracted(
        method="parser", scale=Scale(status="no_scale"), read=(), notes=(f"pdf extractor: {why}",)
    )


def _in_sheet_units(m_per_pt: float, points_per_unit: float) -> float:
    """Metres per point as metres per unit of the sheet (points, or the pixels of its render)."""
    return round(m_per_pt * points_per_unit, 6)


def _per_unit(scale: Scale, points_per_unit: float) -> Scale:
    """The scale in the sheet's own unit: metres per point times points per sheet unit."""
    if scale.m_per_unit is None:
        return scale
    value = _in_sheet_units(scale.m_per_unit, points_per_unit)
    return scale.model_copy(update={"m_per_unit": value})
