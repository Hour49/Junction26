"""Room outlines of a raster plan (app/adapters/raster_ocr/room_outlines.py) on a drawn plan:
outer walls, a partition with a door gap, an open space of two labels left of it."""

import io

import cv2
import numpy as np
from PIL import Image
from shapely.geometry import Polygon

from app.adapters.raster_ocr.room_outlines import RoomOutlines, outlines
from app.core.drawing.model import Page, Room, Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet

W, H = 1000, 700


def plan() -> Image.Image:
    page = np.full((H, W), 255, np.uint8)
    cv2.rectangle(page, (50, 50), (950, 650), 0, 12)  # outer walls, 12 px
    cv2.line(page, (500, 50), (500, 300), 0, 12)  # partition with a 36 px door gap
    cv2.line(page, (500, 336), (500, 650), 0, 12)
    cv2.putText(page, "A", (185, 208), cv2.FONT_HERSHEY_SIMPLEX, 1, 0, 1)  # text is not a wall
    cv2.line(page, (100, 400), (300, 400), 0, 1)  # a thin dimension line is not a wall
    return Image.fromarray(page).convert("RGB")


def room(n: int, cx: int, cy: int) -> Room:
    box = ((cx - 20) / W, (cy - 10) / H, (cx + 20) / W, (cy + 10) / H)
    return Room.model_validate({"id": f"r{n}", "type": "other", "page": 1, "box": box})


def shaped() -> dict[str, Polygon]:
    rooms = outlines(plan(), (room(1, 200, 200), room(2, 200, 500), room(3, 750, 350)))
    return {r.id: Polygon(r.polygon) for r in rooms if r.polygon}


def test_each_room_gets_the_free_space_inside_its_walls() -> None:
    found = shaped()
    assert set(found) == {"r1", "r2", "r3"}
    right = found["r3"]
    assert right.bounds[0] > 0.47 and right.bounds[2] < 0.95  # not into the wall or the page
    assert right.area > 0.8 * (440 / W) * (590 / H)  # the whole room, not a patch
    for a in ("r1", "r2"):
        assert found[a].bounds[0] > 0.05 and found[a].bounds[2] < 0.51


def test_an_open_space_is_split_between_its_labels_without_overlap() -> None:
    found = shaped()
    top, bottom = found["r1"], found["r2"]
    assert top.centroid.y < bottom.centroid.y
    assert top.intersection(bottom).area < 0.02 * top.area
    assert top.area > 0.3 * (440 / W) * (590 / H) and bottom.area > 0.3 * (440 / W) * (590 / H)


def test_the_door_gap_does_not_merge_the_rooms() -> None:
    found = shaped()
    assert found["r3"].intersection(found["r1"]).area < 0.02 * found["r3"].area
    assert found["r3"].intersection(found["r2"]).area < 0.02 * found["r3"].area


def test_a_label_on_a_wall_or_outside_the_plan_keeps_its_box() -> None:
    rooms = outlines(plan(), (room(1, 500, 150), room(2, 20, 20)))
    assert [r.polygon for r in rooms] == [None, None]  # on the partition; outside, leaks to edge


def test_the_wrapper_sets_polygons_and_notes_it() -> None:
    class Files:
        def read(self, path: str) -> bytes:
            out = io.BytesIO()
            plan().save(out, format="PNG")
            return out.getvalue()

    class Inner:
        def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
            return Extracted(
                method="printed_label",
                scale=Scale(status="no_scale"),
                rooms=(room(1, 750, 350),),
                read=("room",),
            )

    source = DrawingFile(path="a.png", size=1, sha256="x", kind="png")
    sheet = Sheet(
        file=DrawingFile(path="a.png", size=1, sha256="x", kind="png"),
        pages=(Page(page=1, width=W, height=H, unit="px"),),
    )
    found = RoomOutlines(Inner(), Files()).extract(source, sheet)  # type: ignore[arg-type]
    assert found.rooms[0].polygon is not None
    assert "room outlines: 1 of 1" in found.notes[-1]
