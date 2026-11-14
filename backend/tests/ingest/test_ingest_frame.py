"""B4: an image's frame. A phone stores a portrait shot lying on its side with an EXIF
orientation; ingest turns it upright once, and the page size, every box and the served sheet
are then in that one frame, whatever a reader does with EXIF."""

import io

import pytest
from conftest import MakeService
from PIL import Image, ImageDraw, ImageOps

from app.core.drawing.model import Element, Scale
from app.core.ingest.model import ContentKind, Rectified
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles
from scripts.make_sample_archive import (
    PHOTO_CORNERS,
    PHOTO_SIZE,
    corners_of,
    perspective,
    phone_photo,
)

WIDTH, HEIGHT = 400, 600  # upright, portrait
SQUARE = (40, 60, 120, 140)  # where the dark square is in the upright image
ROTATE_RIGHT = 6  # EXIF: turn 90 degrees clockwise to show


def upright() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    ImageDraw.Draw(image).rectangle(SQUARE, fill="black")
    return image


def as_a_phone_stores_it() -> bytes:
    """The sensor's landscape image, with the tag that says how to turn it."""
    exif = Image.Exif()
    exif[0x0112] = ROTATE_RIGHT
    buffer = io.BytesIO()
    upright().transpose(Image.Transpose.ROTATE_90).save(buffer, "JPEG", quality=95, exif=exif)
    return buffer.getvalue()


def dark_box(data: bytes) -> tuple[float, float, float, float]:
    """The dark square as page fractions, read the naive way: Pillow, no EXIF turn. A 2%
    border is left out: resampling a photo's paper edge pulls in the table's colour there."""
    with Image.open(io.BytesIO(data)) as image:
        ink = ImageOps.invert(image.convert("L")).point(
            [255 * (level > 128) for level in range(256)]
        )
        edge_x, edge_y = image.width // 50, image.height // 50
        ImageDraw.Draw(ink).rectangle((0, 0, image.width, edge_y), fill=0)
        ImageDraw.Draw(ink).rectangle((0, image.height - edge_y, image.width, image.height), fill=0)
        ImageDraw.Draw(ink).rectangle((0, 0, edge_x, image.height), fill=0)
        ImageDraw.Draw(ink).rectangle((image.width - edge_x, 0, image.width, image.height), fill=0)
        box = ink.getbbox()
        assert box is not None
        width, height = image.size
    return box[0] / width, box[1] / height, box[2] / width, box[3] / height


class SquareReader:
    """A raster reader that places the dark square it finds in the file it is given."""

    def __init__(self, files: DrawingFiles) -> None:
        self._files = files

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        box = dark_box(self._files.read(source.path))
        element = Element.model_validate({"id": "e1", "class": "door", "page": 1, "box": box})
        return Extracted(
            method="detector", scale=Scale(status="no_scale"), elements=(element,), read=("door",)
        )


def test_page_size_box_and_served_sheet_are_in_the_upright_frame(
    make_service: MakeService,
) -> None:
    upload = as_a_phone_stores_it()
    with Image.open(io.BytesIO(upload)) as stored:
        assert stored.size == (HEIGHT, WIDTH)  # lying on its side, as uploaded
    ingest = make_service(raster=SquareReader)
    status = ingest.status(ingest.start("portrait.jpg", upload))
    (file,) = status.files
    assert (file.kind, file.state) == ("jpeg_plan", "ready")
    assert file.normalised is not None
    assert (file.normalised.exif, file.normalised.width, file.normalised.height) == (6, 400, 600)
    assert (file.normalised.rectified, file.normalised.quad) == (False, None)
    assert file.drawing_id is not None

    drawing = ingest.drawing(file.drawing_id)
    page = drawing.pages[0]
    assert (page.width, page.height, page.unit) == (WIDTH, HEIGHT, "px")
    expected = (
        SQUARE[0] / WIDTH,
        SQUARE[1] / HEIGHT,
        (SQUARE[2] + 1) / WIDTH,
        (SQUARE[3] + 1) / HEIGHT,
    )
    assert drawing.elements[0].box == pytest.approx(expected, abs=3 / WIDTH)

    sheet = ingest.sheet(file.drawing_id)
    assert sheet.normalised == file.normalised
    with Image.open(io.BytesIO(sheet.data)) as served:
        assert served.size == (WIDTH, HEIGHT)
        assert served.getexif().get(0x0112) in (None, 1)  # no reader turns it a second time
    assert dark_box(sheet.data) == pytest.approx(drawing.elements[0].box, abs=1e-9)

    assert ingest.upload_bytes(status.id, file.id) == upload  # the file as uploaded
    normalise = next(s for s in ingest.trace(status.id, file.id).stages if s.stage == "normalise")
    assert normalise.did.startswith("EXIF orientation 6 applied: 400x600 px; ")


def test_an_upright_image_keeps_its_bytes(make_service: MakeService) -> None:
    buffer = io.BytesIO()
    upright().save(buffer, "PNG")
    ingest = make_service(raster=SquareReader)
    status = ingest.status(ingest.start("plan.png", buffer.getvalue()))
    (file,) = status.files
    assert file.normalised is not None and file.normalised.exif is None
    assert file.drawing_id is not None
    assert ingest.sheet(file.drawing_id).data == buffer.getvalue()
    assert ingest.upload_bytes(status.id, file.id) == buffer.getvalue()


# --------------------------------------------------------------------------- the rectifier

PLAN_SIZE = (1200, 850)
PLAN_SQUARE = (500, 300, 640, 420)  # where the dark square is on the paper, seen straight on


def plan_on_paper() -> Image.Image:
    image = Image.new("RGB", PLAN_SIZE, "white")
    ImageDraw.Draw(image).rectangle(PLAN_SQUARE, fill="black")
    return image


def photographed_sideways() -> bytes:
    """The plan photographed at an angle on a table (make_sample_archive), stored as a phone
    stores a shot it should show turned: lying on its side, with EXIF orientation 6."""
    exif = Image.Exif()
    exif[0x010F] = "SyntheticPhone"
    exif[0x0112] = ROTATE_RIGHT
    buffer = io.BytesIO()
    shot = phone_photo(plan_on_paper()).transpose(Image.Transpose.ROTATE_90)
    shot.save(buffer, "JPEG", quality=95, exif=exif)
    return buffer.getvalue()


class KnownCorners:
    """A rectifier that knows where the paper is (the photo's known corners), as the photo
    worker's finds it, and undoes the perspective."""

    def __init__(self) -> None:
        self.given: list[tuple[tuple[int, int], str]] = []

    def rectify(self, image: bytes, kind: ContentKind) -> Rectified | None:
        with Image.open(io.BytesIO(image)) as photo:
            self.given.append((photo.size, kind))
            width, height = photo.size
            flat = photo.convert("RGB").transform(
                PLAN_SIZE,
                Image.Transform.PERSPECTIVE,
                perspective(corners_of(PLAN_SIZE), PHOTO_CORNERS),
                Image.Resampling.BICUBIC,
            )
        buffer = io.BytesIO()
        flat.save(buffer, "PNG")
        quad = tuple((x / width, y / height) for x, y in PHOTO_CORNERS)
        return Rectified.model_validate(
            {"data": buffer.getvalue(), "quad": quad, "width": PLAN_SIZE[0],
             "height": PLAN_SIZE[1], "method": "known corners"}
        )  # fmt: skip


def test_a_rectified_photo_is_read_served_and_boxed_in_the_rectified_frame(
    make_service: MakeService,
) -> None:
    upload = photographed_sideways()
    rectifier = KnownCorners()
    ingest = make_service(raster=SquareReader, rectifier=rectifier)
    status = ingest.status(ingest.start("photo.jpg", upload))
    (file,) = status.files
    # the rectifier got the upright photo (EXIF applied first), once
    assert rectifier.given == [(PHOTO_SIZE, "photo_plan")]
    assert file.normalised is not None
    assert (file.normalised.exif, file.normalised.rectified) == (6, True)
    assert file.normalised.rectifier == "known corners"
    assert (file.normalised.width, file.normalised.height) == PLAN_SIZE
    assert file.normalised.quad is not None
    corners = [value for point in file.normalised.quad for value in point]
    known = [v / size for point in PHOTO_CORNERS for v, size in zip(point, PHOTO_SIZE, strict=True)]
    assert corners == pytest.approx(known)
    assert file.drawing_id is not None

    drawing = ingest.drawing(file.drawing_id)
    page = drawing.pages[0]
    assert (page.width, page.height) == PLAN_SIZE
    # the square found by the reader sits where it is on the paper, not where the photo had it
    x0, y0, x1, y1 = PLAN_SQUARE
    width, height = PLAN_SIZE
    expected = (x0 / width, y0 / height, (x1 + 1) / width, (y1 + 1) / height)
    assert drawing.elements[0].box == pytest.approx(expected, abs=0.01)
    sheet = ingest.sheet(file.drawing_id)
    with Image.open(io.BytesIO(sheet.data)) as served:
        assert served.size == PLAN_SIZE
    assert dark_box(sheet.data) == pytest.approx(drawing.elements[0].box, abs=1e-9)
    assert sheet.normalised == file.normalised
    assert ingest.upload_bytes(status.id, file.id) == upload
    normalise = next(s for s in ingest.trace(status.id, file.id).stages if s.stage == "normalise")
    assert normalise.did.startswith(
        "EXIF orientation 6 applied; rectified by known corners: paper corners at (0.16, 0.18)"
    )
    assert "a phone photo, rectified by known corners" in file.reason


class SlowKnownCorners(KnownCorners):
    """KnownCorners on a clock that moves only while it rectifies: 0.4 s per photo."""

    def __init__(self) -> None:
        super().__init__()
        self.now = 0.0

    def rectify(self, image: bytes, kind: ContentKind) -> Rectified | None:
        self.now += 0.4
        return super().rectify(image, kind)


def test_the_rectifier_time_is_the_normalise_stage_s_not_identify_s(
    make_service: MakeService,
) -> None:
    rectifier = SlowKnownCorners()
    ingest = make_service(raster=SquareReader, rectifier=rectifier, clock=lambda: rectifier.now)
    status = ingest.status(ingest.start("photo.jpg", photographed_sideways()))
    stages = {s.stage: s.ms for s in ingest.trace(status.id, status.files[0].id).stages}
    assert (stages["identify"], stages["normalise"]) == (0, pytest.approx(400))


def test_without_a_rectifier_a_photo_keeps_its_frame(make_service: MakeService) -> None:
    ingest = make_service(raster=SquareReader)
    (file,) = ingest.status(ingest.start("photo.jpg", photographed_sideways())).files
    assert file.normalised is not None
    assert (file.normalised.rectified, file.normalised.quad) == (False, None)
    assert (file.normalised.width, file.normalised.height) == PHOTO_SIZE
    assert "a phone photo, read without perspective correction" in file.reason
