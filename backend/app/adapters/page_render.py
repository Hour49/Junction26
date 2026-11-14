"""A sheet's page as a PNG for the screen: a PDF page rasterised with pypdfium2, a PNG or JPEG
sheet re-encoded. The image keeps the frame the drawing model's page fractions are given in: the
sheet as ingest hands it over (`IngestService.sheet`), which is the normalised page, so marks drawn
over it at their fractions land where they belong."""

import io
import math

import pypdfium2
from PIL import Image, ImageOps

from app.adapters.pdfium_lock import PDFIUM
from app.core.errors import InvalidInputError, NotFoundError
from app.core.ingest.model import SheetFile

MAX_PIXELS = 16_000_000  # a larger request is scaled down, so a tall page can't make a huge bitmap


def render_png(sheet: SheetFile, page: int, width: int) -> bytes:
    """Page `page` (from 1) at `width` pixels wide (less when over MAX_PIXELS), aspect kept."""
    if sheet.kind == "pdf":
        image = _pdf_page(sheet.data, page, width)
    else:
        if page != 1:
            raise NotFoundError(f"{sheet.path} is an image with one page, not {page}")
        with Image.open(io.BytesIO(sheet.data)) as found:
            found.load()
            image = found.convert("RGB")
        size = _size(image.width, image.height, width)
        image = image.resize(size, Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def render_upload(data: bytes, kind: str, width: int) -> bytes:
    """An uploaded file as it came, for a before/after view: an image with only its EXIF turn
    applied, or a PDF's first page. `kind` is its content kind (pdf_vector, photo_plan...).
    InvalidInputError for bytes no decoder opens (cut off, damaged): a half-decoded picture would
    show the grey of what is missing as if it were the file."""
    try:
        if kind.startswith("pdf_"):
            image = _pdf_page(data, 1, width)
        else:
            with Image.open(io.BytesIO(data)) as found:
                found.load()
                image = (ImageOps.exif_transpose(found) or found).convert("RGB")
            image = image.resize(_size(image.width, image.height, width), Image.Resampling.LANCZOS)
    except (OSError, Image.DecompressionBombError, pypdfium2.PdfiumError) as error:
        raise InvalidInputError(
            f"the upload cannot be decoded, so it has no preview: {error}"
        ) from error
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _size(page_width: float, page_height: float, width: int) -> tuple[int, int]:
    height = page_height * width / page_width
    shrink = min(1.0, math.sqrt(MAX_PIXELS / (width * height)))
    return max(1, round(width * shrink)), max(1, round(height * shrink))


def _pdf_page(data: bytes, page: int, width: int) -> Image.Image:
    with PDFIUM:
        document = pypdfium2.PdfDocument(data)
        try:
            if not 1 <= page <= len(document):
                raise NotFoundError(f"the sheet has {len(document)} page(s), not page {page}")
            found = document[page - 1]
            page_width, page_height = found.get_size()
            scale = _size(page_width, page_height, width)[0] / page_width
            return found.render(scale=scale).to_pil().convert("RGB")
        finally:
            document.close()
