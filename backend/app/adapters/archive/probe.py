"""What a file is from its bytes (the `ContentProbe` port), never from its name.

The format comes from the first bytes (`sniff`, app/core/pipeline/identify.py). Then:

- **PDF**: page 1's objects (pypdfium2). A page with under 50 paths whose images cover half of
  it or more (even with an OCR text layer, or cut into tiles), or that has images and next to
  no text, is a scan (`pdf_scan`). A page
  with 10 paths or more and under 20 characters of text per path is a drawing (`pdf_vector`):
  a near-empty roof plan has about 40 paths and 500 characters. A page of text with fewer paths
  is a document (`pdf_text`). A PDF no empty password opens is `pdf_encrypted`.
  A page whose drawing is held in annotations (ink strokes, a pasted stamp, rectangles and
  lines) and that has no drawing of its own is read as an image (`pdf_scan`): pdfium draws the
  annotations when it renders the page, the vector reader reads page objects only. On the
  dataset: a floor plan pasted as a stamp and two hand sketches made of 200-265 ink strokes,
  set aside before (2026-11-14). When page 1 is text, the next pages (up to `MAX_PAGES`) are
  looked at, and the ones that hold a drawing are named: the vector reader reads page 1 only. A
  page that does not load (a damaged cross-reference table) makes the file a damaged PDF.
- **PNG/JPEG**: drawing, photo of a drawing, or photo. Measured on a 256 px thumbnail,
  white-balanced on its own brightest 5% (paper under warm room light is yellow until then):
  - `white`: the share of near-white pixels (grey level >= 230). A scan or a rendered plan is
    mostly white paper; a photo of paper under room light is grey, so it is not.
  - `paper`: bright, colourless pixels (grey >= 140, saturation < 20%), and `ink`: dark pixels
    (grey < 90). A photo of a plan is mostly paper with some ink; a photo of a site or a
    person is neither.
  - camera EXIF (Make or Model): the image came from a camera.
  Without camera EXIF the image is a drawing (`png_plan`/`jpeg_plan`): setting a file aside
  loses it, so that needs evidence. On the dataset's 4,787 CubiCasa scans a rule on the pixels
  alone called 19 a photo (coloured renderings, dark backgrounds), so the pixels only decide
  between the two kinds of camera image: `paper` >= 30% and `ink` between 0.3% and 35% is a
  photo of a drawing (`photo_plan`), else a photo that is not of a drawing (`photo`). A phone
  photo with its EXIF stripped passes as a drawing: it takes the same raster route, unflagged.
  An image under 64 px a side is too small to read. An image with no drawing in it is not a
  drawing (`unknown`, set aside), whatever its EXIF says (QA R2-qa5-1: these were "ready" plans
  whose counts read a measured 0):
  - no sharp line: the 99.9th percentile of the step between neighbouring pixels, on the image
    at 1024 px, under 10 grey levels. A blank page, a black frame or a photo blurred past
    reading. Drawings measured: 18 or more (old faint scans), 55 or more on CubiCasa.
  - no structure: neighbouring pixels of the 256 px thumbnail unrelated both across and down
    (correlation under 0.3, from their mean squared step and the variance): noise.
  Checked 2026-11-14 with this code on 13,560 images, none set aside: CubiCasa 4,787, swiss
  1,040, the 30 Commons phone photos, the demo archive's 9 images, 6,566 historic scans
  (wikimedia, habs, finna, europeana, opening_design) and 1,128 synthetic phone photos of plans.
  Set aside: black, white, noise, and a plan or photo blurred by 15 or 25 px (8 px and less
  are kept). Both checks add about 26 ms per image.
- Text: UTF-8 with next to no control characters. A DWG, an office file and a zip that was not
  unpacked are named, and set aside by the service.

Checked 2026-11-14 (.agents/ingest.md has the counts): all 4,787 CubiCasa and 1,040 swiss PNGs are
drawings; the three real phone photos of evacuation plans that kept their camera EXIF (Wikimedia
Commons, data/stoa/exp/photo/real/) are photos of a drawing.
"""

import codecs
import ctypes
import io
import zipfile
from typing import Any

import pypdfium2
from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError
from pypdfium2 import raw

from app.adapters.pdfium_lock import PDFIUM
from app.core.ingest.model import Probed
from app.core.pipeline.identify import sniff
from app.core.wording import count as counted

THUMB = 256
MIN_SIDE = 64
PAPER_PHOTO = 0.30
INK_PHOTO = (0.003, 0.35)
BALANCE_AT = 0.95  # the percentile of each channel taken as white
CAMERA_TAGS = (0x010F, 0x0110)  # Make, Model
VECTOR_PATHS = 10  # path objects on page 1 that make a drawing, with text no more than 20x that
SCAN_COVER = 0.5  # share of the page its images cover in a scan (tiles add up)
SCAN_PATHS = 50  # a scan with more paths than this has a drawn layer on it
TEXT_CHARS = 200
MAX_PAGES = 20  # pages after a text page 1 looked at for drawings
# The annotations that draw: what a page held only in them is a drawing (FPDF_ANNOT_*).
DRAWN_ANNOTATIONS = {
    raw.FPDF_ANNOT_INK: "ink drawing",
    raw.FPDF_ANNOT_STAMP: "stamp",
    raw.FPDF_ANNOT_LINE: "line",
    raw.FPDF_ANNOT_SQUARE: "rectangle",
    raw.FPDF_ANNOT_CIRCLE: "circle",
    raw.FPDF_ANNOT_POLYGON: "polygon",
    raw.FPDF_ANNOT_POLYLINE: "polyline",
}
MAX_OBJECTS = 20000  # page objects looked at; a drawing has passed the bar long before
TEXT_HEAD = 65536
SHARP_SIDE = 1024  # long side the sharpness is measured at
SHARP_AT = 0.999  # the share of neighbour steps below the image's sharpest
SHARP_STEP = 10  # grey levels: an image whose sharpest steps are smaller has no line in it
NOISE_CORRELATION = 0.3  # neighbouring pixels less related than this: noise, no drawing


class FileProbe:
    def probe(self, data: bytes) -> Probed:
        if not data:
            return Probed(kind="unknown", did="an empty file")
        match sniff(data):
            case "pdf":
                return _pdf(data)
            case "png" | "jpeg" as image:
                return _image(data, image)
            case "ifc":
                if b"IFC" in data[:4096].upper():
                    return Probed(kind="ifc", did="first bytes: an IFC building model (STEP)")
                return Probed(kind="unknown", did="a STEP file that is not an IFC model")
            case "dxf":
                return Probed(kind="dxf", did="first bytes: a DXF drawing")
            case "svg":
                return Probed(kind="svg", did="first bytes: an SVG drawing")
            case None:
                return _other(data)


def is_scanned_pdf(data: bytes) -> bool:
    """Whether a PDF is a scan, by the rule above: what core's stage 5 asks (`scanned`)."""
    return _pdf(data).kind == "pdf_scan"


def _pdf(data: bytes) -> Probed:
    with PDFIUM:  # pdfium is not thread-safe (app/adapters/pdfium_lock.py)
        return _pdf_unlocked(data)


class _PageNotLoadedError(Exception):
    def __init__(self, number: int, error: pypdfium2.PdfiumError) -> None:
        super().__init__(f"page {number} does not load ({error})")


def _pdf_unlocked(data: bytes) -> Probed:
    try:
        document = pypdfium2.PdfDocument(data)
    except pypdfium2.PdfiumError as error:
        if "password" in str(error).lower():
            return Probed(kind="pdf_encrypted", did="an encrypted PDF that no empty password opens")
        return Probed(kind="unknown", did=f"a PDF that cannot be opened: {error}")
    try:
        if len(document) == 0:
            return Probed(kind="unknown", did="a PDF with no pages")
        return _pdf_pages(document)
    except _PageNotLoadedError as error:
        return Probed(kind="unknown", did=f"a damaged PDF: {error}")
    finally:
        document.close()


def _pdf_pages(document: pypdfium2.PdfDocument) -> Probed:
    count = len(document)
    page = _page(document, 1)
    width, height = page.get_size()
    paths, images, cover = _objects(page, width * height)
    chars = page.get_textpage().count_chars()
    seen = f"page 1 of {count}: {paths} paths, {images} images, {chars} characters"
    if paths < SCAN_PATHS and (cover >= SCAN_COVER or (images and chars < TEXT_CHARS)):
        return Probed(kind="pdf_scan", did=f"a scanned PDF, images cover {cover:.0%} ({seen})")
    if paths >= VECTOR_PATHS and chars < 20 * paths:
        return Probed(kind="pdf_vector", did=f"a drawn PDF ({seen})")
    if chars >= TEXT_CHARS:
        drawn = [number for number in range(2, min(count, MAX_PAGES + 1) + 1)
                 if _drawn(_page(document, number))]  # fmt: skip
        return Probed(
            kind="pdf_text", did=f"a text document, not a drawing ({seen}){_later(drawn)}"
        )
    annotations = _drawn_annotations(page)
    if annotations and not images and paths < VECTOR_PATHS:
        held = f"a drawing held in the PDF's annotations ({annotations}), read as an image"
        return Probed(kind="pdf_scan", did=f"{held} ({seen})")
    if paths:
        return Probed(kind="pdf_vector", did=f"a drawn PDF with little on it ({seen})")
    return Probed(kind="unknown", did=f"a PDF with nothing to read on page 1 ({seen})")


def _page(document: pypdfium2.PdfDocument, number: int) -> pypdfium2.PdfPage:
    try:
        return document[number - 1]
    except pypdfium2.PdfiumError as error:
        raise _PageNotLoadedError(number, error) from error


def _objects(page: pypdfium2.PdfPage, area: float) -> tuple[int, int, float]:
    """The page's path and image objects (form XObjects' too), and the share of the page its
    images cover."""
    paths = images = 0
    cover = 0.0
    for at, obj in enumerate(page.get_objects()):
        if at >= MAX_OBJECTS:
            break
        kind = raw.FPDFPageObj_GetType(obj.raw)
        if kind == raw.FPDF_PAGEOBJ_PATH:
            paths += 1
        elif kind == raw.FPDF_PAGEOBJ_IMAGE:
            images += 1
            cover = min(1.0, cover + _area(obj.raw) / max(area, 1e-9))
    return paths, images, cover


def _drawn(page: pypdfium2.PdfPage) -> bool:
    """Whether a page is a drawing by the drawn-PDF rule of page 1."""
    width, height = page.get_size()
    paths, _, _ = _objects(page, width * height)
    return paths >= VECTOR_PATHS and page.get_textpage().count_chars() < 20 * paths


def _later(drawn: list[int]) -> str:
    if not drawn:
        return ""
    if len(drawn) == 1:
        return f"; page {drawn[0]} holds a drawing, which is not read (only page 1 is)"
    numbers = f"{', '.join(map(str, drawn[:-1]))} and {drawn[-1]}"
    return f"; pages {numbers} hold drawings, which are not read (only page 1 is)"


def _drawn_annotations(page: pypdfium2.PdfPage) -> str:
    """The page's visible annotations that draw, counted by type ("1 stamp, 3 rectangles"), or
    an empty string."""
    found: dict[str, int] = {}
    for index in range(raw.FPDFPage_GetAnnotCount(page.raw)):
        annot = raw.FPDFPage_GetAnnot(page.raw, index)
        try:
            name = DRAWN_ANNOTATIONS.get(raw.FPDFAnnot_GetSubtype(annot))
            hidden = raw.FPDFAnnot_GetFlags(annot) & raw.FPDF_ANNOT_FLAG_HIDDEN
        finally:
            raw.FPDFPage_CloseAnnot(annot)
        if name is not None and not hidden:
            found[name] = found.get(name, 0) + 1
    return ", ".join(counted(n, name) for name, n in found.items())


def _area(obj: Any) -> float:
    """The area of a page object's bounding box, in points squared."""
    left, bottom, right, top = (ctypes.c_float() for _ in range(4))
    if not raw.FPDFPageObj_GetBounds(obj, left, bottom, right, top):
        return 0.0
    return max(0.0, right.value - left.value) * max(0.0, top.value - bottom.value)


def _image(data: bytes, image_format: str) -> Probed:
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            exif = image.getexif()
            camera = " ".join(str(exif[tag]).strip() for tag in CAMERA_TAGS if exif.get(tag))
            image.draft("RGB", (THUMB, THUMB))  # JPEG: decode at a fraction of the size
            thumb = image.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        return Probed(kind="unknown", did=f"an image that cannot be decoded: {error}")
    name = image_format.upper()
    if min(width, height) < MIN_SIDE:
        return Probed(kind="unknown", did=f"a {name} of {width}x{height} px: too small to read")
    thumb.thumbnail((THUMB, THUMB))
    thumb = _balanced(thumb)
    grey = thumb.convert("L")
    saturation = thumb.convert("HSV").getchannel("S")
    count = grey.width * grey.height
    levels = grey.histogram()
    white = sum(levels[230:]) / count
    ink = sum(levels[:90]) / count
    bright = grey.point([255 if level >= 140 else 0 for level in range(256)])
    plain = saturation.point([255 if level < 51 else 0 for level in range(256)])
    paper = ImageChops.multiply(bright, plain).histogram()[255] / count
    seen = f"{width}x{height} px, {white:.0%} white, {paper:.0%} paper, {ink:.1%} ink" + (
        f", camera EXIF ({camera})" if camera else ""
    )
    empty = _no_drawing(data, grey)
    if empty is not None:
        return Probed(kind="unknown", did=f"not a drawing: {empty} ({seen})")
    if not camera:
        kind = "png_plan" if image_format == "png" else "jpeg_plan"
        return Probed(kind=kind, did=f"a drawing as a {name} ({seen})")
    if paper >= PAPER_PHOTO and INK_PHOTO[0] <= ink <= INK_PHOTO[1]:
        return Probed(kind="photo_plan", did=f"a photo of a drawing ({seen})")
    return Probed(kind="photo", did=f"a photo, not of a drawing ({seen})")


def _no_drawing(data: bytes, thumb: Image.Image) -> str | None:
    """Why an image holds no drawing (no sharp line, or no structure), or None. `thumb`: the
    probe's white-balanced grey thumbnail."""
    with Image.open(io.BytesIO(data)) as image:
        image.draft("L", (SHARP_SIDE, SHARP_SIDE))
        grey = image.convert("L")
    grey.thumbnail((SHARP_SIDE, SHARP_SIDE))
    across, down = _steps(grey)
    levels = ImageChops.lighter(across, down).histogram()
    seen, total, sharpest = 0, sum(levels), 0
    for level, count in enumerate(levels):
        seen += count
        if seen >= SHARP_AT * total:
            sharpest = level
            break
    if sharpest < SHARP_STEP:
        return f"no sharp line in it (sharpest step {sharpest} grey levels): blank or blurred"
    variance = ImageStat.Stat(thumb).var[0]
    related = 1.0
    if variance:  # the better of the two directions: a thin upright line only relates downwards
        squares = [sum(level * level * count for level, count in enumerate(step.histogram()))
                   / (step.width * step.height) for step in _steps(thumb)]  # fmt: skip
        related = 1 - min(squares) / (2 * variance)
    if related < NOISE_CORRELATION:
        return f"no structure in it (neighbouring pixels correlate {related:.2f}): noise"
    return None


def _steps(grey: Image.Image) -> tuple[Image.Image, Image.Image]:
    """|step| to the right neighbour and to the one below, for every pixel that has both."""
    width, height = grey.size
    here = grey.crop((0, 0, width - 1, height - 1))
    right = grey.crop((1, 0, width, height - 1))
    below = grey.crop((0, 1, width - 1, height))
    return ImageChops.difference(here, right), ImageChops.difference(here, below)


def _balanced(image: Image.Image) -> Image.Image:
    """White balance on the image's own brightest pixels: each channel is stretched so its
    `BALANCE_AT` percentile is white. Paper under warm room light is yellow; balanced, it is
    paper again, while a blue sky or green grass stays coloured."""
    channels = []
    for channel in image.split():
        levels = channel.histogram()
        seen, top = 0, 255
        for level in range(255, -1, -1):
            seen += levels[level]
            if seen >= (1 - BALANCE_AT) * image.width * image.height:
                top = max(level, 1)
                break
        channels.append(channel.point([min(255, level * 255 // top) for level in range(256)]))
    return Image.merge("RGB", channels)


def _other(data: bytes) -> Probed:
    if data[:3] == b"AC1" and data[3:6].isdigit():
        return Probed(kind="dwg", did="a DWG drawing: converting it to DXF is not built yet")
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                office = "[Content_Types].xml" in archive.namelist()
        except zipfile.BadZipFile:
            return Probed(kind="unknown", did="a damaged zip")
        if office:
            return Probed(kind="office", did="an office document (Word, Excel or PowerPoint)")
        return Probed(kind="archive", did="a zip that was not unpacked")
    try:
        text = codecs.getincrementaldecoder("utf-8")().decode(data[:TEXT_HEAD], final=False)
    except UnicodeDecodeError:
        return Probed(kind="unknown", did="binary content in no format we read")
    control = sum(ord(char) < 32 and char not in "\t\r\n\f" for char in text)
    if text and control <= len(text) / 100:
        return Probed(kind="text", did=f"plain text, {len(data)} bytes")
    return Probed(kind="unknown", did="binary content in no format we read")
