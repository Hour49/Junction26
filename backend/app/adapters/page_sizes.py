"""Pages of a sheet file (the `PageReader` port): PDF through pypdfium2, images through Pillow.

Only the sizes are read today. Rendering a page to pixels, which the raster route and any vision
model need, belongs in this adapter too.
"""

import io

import pypdfium2
from PIL import Image

from app.adapters.pdfium_lock import PDFIUM
from app.core.drawing.model import Page
from app.core.pipeline.model import DrawingFile
from app.core.pipeline.ports import DrawingFiles


class PageSizes:
    def __init__(self, files: DrawingFiles) -> None:
        self._files = files

    def pages(self, file: DrawingFile) -> tuple[Page, ...]:
        data = self._files.read(file.path)
        if file.kind == "pdf":
            with PDFIUM:  # pdfium is not thread-safe (app/adapters/pdfium_lock.py)
                return _pdf_pages(data)
        if file.kind in ("png", "jpeg"):
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
            return (Page(page=1, width=width, height=height, unit="px"),)
        raise ValueError(f"{file.path}: a {file.kind} file has no pages")


def _pdf_pages(data: bytes) -> tuple[Page, ...]:
    """Sizes in points, as rendered: pdfium applies each page's /Rotate."""
    document = pypdfium2.PdfDocument(data)
    try:
        sizes = [document[index].get_size() for index in range(len(document))]
    finally:
        document.close()
    return tuple(
        Page(page=number, width=width, height=height, unit="pt")
        for number, (width, height) in enumerate(sizes, start=1)
    )
