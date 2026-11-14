"""`VECTOR_FALLBACK=raster`: whether a PDF matches no sheet style the vector reader has reading
rules for, so stage 5 routes it to the raster route (local-dec BK S1, 2026-11-14).

The vector reader reads only the styles in `STYLES` (swiss, ifc_render); any other drawn PDF (a
Revit or AutoCAD plot: 584 of opening_design's 587 drawn PDFs, .agents/exp/vector-generic.md)
gets only its scale and "no sheet style we have reading rules for". This asks the same question
of page 1 before the route is chosen. A later page of a PDF is a file of its own (ingest splits
them), so page 1 is the page. A PDF pdfium cannot open is not called unruled: it stays where it
was routed, and fails there as it did.
"""

import hashlib
import threading
from collections import OrderedDict

import pypdfium2

from app.adapters.vector_pdf import STYLES
from app.adapters.vector_pdf.objects import PdfPath, any_filled_path

KEEP = 64  # answers kept by file content: one read of a page's objects per file


class Unruled:
    """`unruled(data)`: whether the PDF's page 1 matches none of the vector reader's styles."""

    def __init__(self) -> None:
        self._seen: OrderedDict[str, bool] = OrderedDict()  # sha256 of the PDF -> unruled
        self._lock = threading.Lock()

    def __call__(self, data: bytes) -> bool:
        if not data.startswith(b"%PDF"):
            return False
        key = hashlib.sha256(data).hexdigest()
        with self._lock:
            if key not in self._seen:
                self._seen[key] = _unruled(data)
                while len(self._seen) > KEEP:
                    self._seen.popitem(last=False)
            self._seen.move_to_end(key)
            return self._seen[key]


def _unruled(data: bytes) -> bool:
    """No path of page 1 is drawn in a style; every style's paths are filled, so the check reads
    only filled paths (objects.any_filled_path)."""
    try:
        return not any_filled_path(data, _styled)
    except pypdfium2.PdfiumError:
        return False


def _styled(path: PdfPath) -> bool:
    return any(style.matches_path(path) for style in STYLES)
