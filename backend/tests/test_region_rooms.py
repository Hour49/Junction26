"""RegionRooms (app/adapters/raster_ocr/region_rooms.py): rooms off the predicted flat are left
out, by region's own rule. A stand-in mask replaces the U-Net; no model, no data/."""

import io

import numpy as np
from PIL import Image

from app.adapters.raster_ocr.region_rooms import RegionRooms
from app.adapters.raster_region.steps import Frame
from app.core.drawing.model import Element, Page, ReadClass, Room, Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet

SIDE = 100  # the stand-in mask canvas; the 200 x 100 page sits on it at 100 x 50, 25 px down


class LeftHalf:
    """The drawn flat is the left half of the page (or `share` of the canvas's left columns)."""

    def __init__(self, columns: int = SIDE // 2) -> None:
        self.columns = columns
        self.asked = 0

    def mask(self, page: Image.Image) -> tuple[np.ndarray, Frame]:
        self.asked += 1
        mask = np.zeros((SIDE, SIDE), dtype=bool)
        mask[:, : self.columns] = True
        return mask, Frame.fit(page.width, page.height, SIDE)


class BytesFiles:
    def read(self, path: str) -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", (200, 100), "white").save(buffer, format="PNG")
        return buffer.getvalue()


class Rooms:
    def __init__(self, read: tuple[ReadClass, ...] | None = ("room",)) -> None:
        self.read = read

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return Extracted(
            method="printed_label",
            scale=Scale(status="no_scale"),
            elements=(Element(id="e1", class_="door", page=1, box=(0.8, 0.4, 0.9, 0.5)),),
            rooms=(
                Room(id="r1", type="bedroom", page=1, box=(0.1, 0.2, 0.3, 0.6)),  # left
                Room(id="r2", type="bedroom", page=1, box=(0.7, 0.2, 0.9, 0.6)),  # right
                Room(id="r3", type="kitchen", page=1, box=(0.3, 0.3, 0.6, 0.5)),  # centre x .45
            ),
            read=self.read,
            notes=("gemini: 3 rooms",),
        )


def extract(region: LeftHalf, inner: Rooms | None = None) -> Extracted:
    source = DrawingFile(path="data/cubicasa5k/x.png", size=1, sha256="0" * 64, kind="png")
    sheet = Sheet(file=source, pages=(Page(page=1, width=200, height=100, unit="px"),))
    return RegionRooms(inner or Rooms(), BytesFiles(), region).extract(source, sheet)


def test_rooms_off_the_drawn_flat_are_left_out_and_the_rest_is_kept() -> None:
    found = extract(LeftHalf())
    assert [room.id for room in found.rooms] == ["r1", "r3"]
    assert [e.id for e in found.elements] == ["e1"]  # only rooms are cut
    assert found.notes == ("gemini: 3 rooms", "region rooms: 2 of 3 rooms on the drawn flat")


def test_a_mask_that_found_no_flat_keeps_every_room() -> None:
    assert len(extract(LeftHalf(columns=1)).rooms) == 3  # 1 % of the page: a failed prediction


def test_rooms_the_reader_did_not_read_stay_unread_without_a_mask() -> None:
    region = LeftHalf()
    found = extract(region, Rooms(read=()))
    assert (found.read, region.asked) == ((), 0)
