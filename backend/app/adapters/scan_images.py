"""The raster route's view of the files: a scanned PDF reads as its page 1, rendered once to a PNG.

Ingest routes a scanned PDF (its page is one big image, archive/probe.py `is_scanned_pdf`) to
the raster route, whose readers open the bytes as an image: the detector, the count arbiter, the
room readers, Carbon, the printed-scale reader and the Decisions swap and answer confidence. Given
the PDF they failed ("cannot identify image file", local-dec BK S0, 2026-11-14). `ScanImages`
hands every one of them the same PNG of the page: rendered once per file and shared, at
`SCAN_DPI` pixels per inch of the page (fewer when that is over page_render's MAX_PIXELS). Page
fractions are the page's either way, so boxes land where the served page shows them. Every other
file (an image, a drawn PDF) reads as it is. A later page of a PDF is a file of its own (ingest
splits them), so page 1 is the page.
"""

import hashlib
import io
import threading
from collections import OrderedDict

import pypdfium2

from app.adapters.archive.probe import is_scanned_pdf
from app.adapters.page_render import fitted
from app.adapters.pdfium_lock import PDFIUM
from app.core.pipeline.ports import DrawingFiles

SCAN_DPI = 150  # a scan's text and symbols stay legible; the detector reads 1024 px anyway
KEEP = 8  # renders kept, newest first (a project's pages are read one after another)


def scan_png(data: bytes, dpi: float = SCAN_DPI) -> bytes:
    """Page 1 of a PDF as a PNG, `dpi` pixels per inch of the page, at most MAX_PIXELS."""
    with PDFIUM:  # pdfium is not thread-safe (app/adapters/pdfium_lock.py)
        document = pypdfium2.PdfDocument(data)
        try:
            page = document[0]
            width, height = page.get_size()  # points, 72 to the inch
            wide = fitted(width, height, max(1, round(width * dpi / 72)))[0]
            image = page.render(scale=wide / width).to_pil().convert("RGB")
        finally:
            document.close()
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class ScanRenders:
    """The PNG each scanned PDF reads as, rendered once per file content and kept (`KEEP`); one
    of them can serve many `ScanImages` (answer time: a view per request, review-280 S2)."""

    def __init__(self) -> None:
        self._made: OrderedDict[str, bytes] = OrderedDict()  # sha256 of the PDF -> what reads
        self._rendering: dict[str, threading.Lock] = {}  # sha256 -> the lock of its one render
        self._lock = threading.Lock()  # guards both; never held during a render

    def image(self, data: bytes) -> bytes:
        """What the PDF `data` reads as: the PNG of its page if it is a scan, else itself. Readers
        of one page wait for its one render; readers of other pages do not (review-280 S1)."""
        key = hashlib.sha256(data).hexdigest()
        with self._lock:
            rendering = self._rendering.setdefault(key, threading.Lock())
        with rendering:
            with self._lock:
                made = self._made.get(key)
            if made is None:
                made = scan_png(data) if is_scanned_pdf(data) else data
            with self._lock:
                self._made[key] = made
                self._made.move_to_end(key)
                while len(self._made) > KEEP:
                    self._made.popitem(last=False)
                self._rendering.pop(key, None)
            return made


class ScanImages:
    """`files` with each scanned PDF read as `scan_png` of it, one render per file content (in
    `renders`, by default its own)."""

    def __init__(self, files: DrawingFiles, renders: ScanRenders | None = None) -> None:
        self._files = files
        self._renders = renders or ScanRenders()

    def read(self, path: str) -> bytes:
        data = self._files.read(path)
        if not data.startswith(b"%PDF"):
            return data
        return self._renders.image(data)
