"""The raster OCR room reader (app/adapters/raster_ocr): the label table, the turn and mirror
vote, and labels that name no room. The rules run against a fake engine that reads a crop only
when it lies the way it was printed (a red mark in its top-left corner), so each test is exact;
one live test runs the real PP-OCRv6 engine on text drawn with Pillow."""

import io
from collections.abc import Sequence

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.adapters.raster_ocr import OcrRoomExtractor, RapidOcrEngine, RoomLabelReader
from app.adapters.raster_ocr.labels import fold, room_type, table
from app.adapters.raster_ocr.reader import Quad, crop
from app.core.drawing.model import Page
from app.core.pipeline.model import DrawingFile, Sheet

RED, BLUE = (255, 0, 0), (0, 0, 255)
CELL = 60  # a label is drawn as a CELL x CELL tile


def tile() -> Image.Image:
    """A blank label tile, red mark top-left and blue top-right as printed: a turn keeps the
    two in that order (clockwise), a mirror swaps it."""
    image = Image.new("RGB", (CELL, CELL), "white")
    ImageDraw.Draw(image).rectangle((0, 0, 9, 9), fill=RED)
    ImageDraw.Draw(image).rectangle((CELL - 10, 0, CELL - 1, 9), fill=BLUE)
    return image


class MarkEngine:
    """Detects the tiles placed on the page; reads a crop as its label only when it lies as
    printed (red mark top-left, blue top-right), and as the reversed label otherwise."""

    def __init__(self, labels: dict[tuple[int, int], str]) -> None:
        self.labels = labels  # tile origin (x, y) on the page as given -> its label

    def detect(self, image: np.ndarray) -> list[Quad]:
        scale = image.shape[1] / self.width
        return [
            [(x * scale, y * scale), ((x + CELL) * scale, y * scale),
             ((x + CELL) * scale, (y + CELL) * scale), (x * scale, (y + CELL) * scale)]
            for x, y in self.labels
        ]  # fmt: skip

    def recognise(self, crops: Sequence[np.ndarray]) -> list[tuple[str, float]]:
        out = []
        texts = iter(t for t in self.labels.values() for _ in range(8))
        for part in crops:
            text = next(texts)
            h, w = part.shape[:2]
            left = part[: h // 8, : w // 8].reshape(-1, 3)
            right = part[: h // 8, w - w // 8 :].reshape(-1, 3)
            upright = bool(
                (left == RED).all(axis=1).mean() > 0.5 and (right == BLUE).all(axis=1).mean() > 0.5
            )
            out.append((text, 0.99) if upright else (text[::-1], 0.9))
        return out

    width = 0

    def cut(self, image: np.ndarray, quad: Quad) -> np.ndarray:
        return crop(image, quad)


def page(labels: dict[tuple[int, int], str], turn: int = 0, mirror: bool = False):
    """A page with a marked tile at each origin; the whole page then turned or mirrored, with
    the engine told where each tile ended up."""
    w, h = 600, 400
    image = Image.new("RGB", (w, h), "white")
    for x, y in labels:
        image.paste(tile(), (x, y))
    arr = np.asarray(image)
    placed = dict(labels)
    if mirror:
        arr = arr[:, ::-1]
        placed = {(w - x - CELL, y): t for (x, y), t in labels.items()}
    for _ in range(turn):  # counter-clockwise quarter turns
        ww = arr.shape[1]
        arr = np.rot90(arr)
        placed = {(y, ww - x - CELL): t for (x, y), t in placed.items()}
    engine = MarkEngine(placed)
    engine.width = arr.shape[1]
    return Image.fromarray(np.ascontiguousarray(arr)), engine


def test_table_maps_the_common_codes_from_dev_gold() -> None:
    assert room_type("MH") == "bedroom"
    assert room_type("MH 2") == "bedroom"  # digits and spaces fold away
    assert room_type("kph") == "bathroom"
    assert room_type("WC") == "wc"
    assert room_type("Keittiö") == "kitchen"
    assert room_type("KEITTIO") == "kitchen"  # OCR often drops the dots
    assert room_type("PARVEKE") == "balcony"
    assert fold("lasitettu parveke") == "LASITETTUPARVEKE"
    assert "UNDEFINED" not in table() and "ULKOTILA" not in table()  # tool defaults


def test_unknown_text_names_no_room() -> None:
    assert room_type("MH 12,5 m2") == "bedroom"  # the first word that is a label
    assert room_type("12,5 m2") is None
    assert room_type("2. KERROS S") is None  # a lone letter in other text names nothing
    assert room_type("ASUNTO") is None


def test_dimension_notes_name_no_room() -> None:
    # "mm" sits in many train bedrooms (ceiling notes), but at share 0.71 it is a unit, not a label
    assert room_type("n = 130 mm.") is None
    assert room_type("h=1600 MM") is None
    assert room_type("rSxE") is None
    image, engine = page({(40, 40): "MH", (200, 40): "XYZ", (40, 200): "12,5"})
    found = RoomLabelReader(engine).read(image)
    assert [(r.type, r.label) for r in found.rooms] == [("bedroom", "MH")]


@pytest.mark.parametrize("turn", [0, 1, 2, 3])
def test_a_turned_page_reads_its_labels(turn: int) -> None:
    labels = {(40, 40): "MH", (200, 40): "WC", (40, 200): "KPH", (300, 200): "OH"}
    image, engine = page(labels, turn=turn)
    found = RoomLabelReader(engine).read(image)
    assert sorted(r.type for r in found.rooms) == ["bathroom", "bedroom", "living", "wc"]
    assert all(r.label in labels.values() for r in found.rooms)  # never the reversed text
    assert any("most often" in note for note in found.notes)


def test_a_mirrored_page_reads_its_labels_mirrored_back() -> None:
    labels = {(40, 40): "MH", (200, 40): "WC", (40, 200): "KPH"}
    image, engine = page(labels, mirror=True)
    found = RoomLabelReader(engine).read(image)
    assert sorted(r.label or "" for r in found.rooms) == ["KPH", "MH", "WC"]
    assert all("mirrored" in str(r.attrs["turn"]) for r in found.rooms)


def test_boxes_are_page_fractions_of_the_label() -> None:
    image, engine = page({(300, 200): "MH"})
    (room,) = RoomLabelReader(engine).read(image).rooms
    assert room.box == pytest.approx((0.5, 0.5, 0.6, 0.65))
    assert room.page == 1 and room.attrs["score"] == pytest.approx(0.99)


class BytesFiles:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self, path: str) -> bytes:
        return self.data


def test_the_extractor_reads_rooms_only() -> None:
    image, engine = page({(40, 40): "MH", (200, 40): "K"})
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    source = DrawingFile(path="data/cubicasa5k/x.png", size=1, sha256="0" * 64, kind="png")
    sheet = Sheet(file=source, pages=(Page(page=1, width=600, height=400, unit="px"),))
    found = OcrRoomExtractor(BytesFiles(buf.getvalue()), engine).extract(source, sheet)
    assert found.read == ("room",)
    assert found.scale.status == "no_scale"
    assert sorted(r.type for r in found.rooms) == ["bedroom", "kitchen"]


@pytest.mark.live  # rapidocr downloads its two models (about 20 MB) from modelscope on first use
@pytest.mark.parametrize("turn", [0, 2])
def test_the_real_engine_reads_drawn_labels(turn: int) -> None:
    image = Image.new("RGB", (900, 500), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=36)
    for (x, y), text in {
        (80, 80): "MH",
        (500, 80): "KPH",
        (80, 330): "WC",
        (500, 330): "OH",
    }.items():
        draw.text((x, y), text, fill="black", font=font)
    image = image.rotate(90 * turn, expand=True)
    found = RoomLabelReader(RapidOcrEngine()).read(image)
    assert sorted(r.type for r in found.rooms) == ["bathroom", "bedroom", "living", "wc"]
