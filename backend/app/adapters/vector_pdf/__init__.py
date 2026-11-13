"""`EXTRACTOR_VECTOR=pdf`: the vector route's `Extractor`, reading a drawn (not scanned) PDF.

It reads the source PDF and nothing else: no DXF, SVG or IFC next to it, no model call. Page 1's
paths and text objects (objects.py) go to the reading rules of the sheet style they match
(swiss.py, ifc_render.py); the scale comes from the sheet's own text and scale bar (scale.py).

Positions are fractions of the PDF page. A PNG of the same sheet is that page rendered, so the
fractions hold on it too and only the metres per unit change (metres per point x PDF width /
PNG width). A sheet whose shape differs from the PDF page is not that render, and gets nothing.
"""

from app.adapters.vector_pdf import ifc_render, swiss
from app.adapters.vector_pdf.objects import read_page
from app.adapters.vector_pdf.scale import read_scale
from app.core.drawing.model import Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles

STYLES = (swiss, ifc_render)
SAME_SHAPE = 0.01  # relative difference of width / height between the PDF page and the sheet


class PdfVectorExtractor:
    def __init__(self, files: DrawingFiles) -> None:
        self._files = files

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        if source.kind != "pdf":
            return _nothing(f"the source {source.path} is {source.kind}, not a PDF")
        page = read_page(self._files.read(source.path))
        target = sheet.pages[0]
        shape, target_shape = page.width / page.height, target.width / target.height
        if abs(shape / target_shape - 1) > SAME_SHAPE:
            return _nothing(f"{sheet.file.path} is not page 1 of {source.path} rendered")
        scale, notes = read_scale(page)
        style = next((style for style in STYLES if style.matches(page)), None)
        if style is None:
            return Extracted(
                method="parser",
                scale=_per_unit(scale, page.width / target.width),
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
            notes=(*notes, *reading.notes),
        )


def _nothing(why: str) -> Extracted:
    return Extracted(
        method="parser", scale=Scale(status="no_scale"), notes=(f"pdf extractor: {why}",)
    )


def _per_unit(scale: Scale, points_per_unit: float) -> Scale:
    """The scale in the sheet's own unit: metres per point times points per sheet unit."""
    if scale.m_per_unit is None:
        return scale
    return scale.model_copy(update={"m_per_unit": round(scale.m_per_unit * points_per_unit, 6)})
