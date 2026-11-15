"""sheet_walls.reader: a services picture's wall lines per part (whole page and plan views),
in the picture's pixels, laid over the plan by pairing.by_walls (the follower's wall step)."""

import cv2
import numpy as np

from app.adapters.discipline_pictures import sheet_walls
from app.core.services.pairing import by_walls
from app.core.services.picture_follow import Sheet
from app.core.services.register import Segment
from tests.test_picture_walls import PLAN, PX_PER_M, px, sheet

PLAN_SHEET = Sheet(drawing_id="plan", page=1, size_m=(40.0, 30.0), name="plan.pdf")
PICTURE = Sheet(drawing_id="pic", page=1, name="heating.png", disciplines=("heating",))


def with_schedule(rgb: np.ndarray) -> np.ndarray:
    """The picture with a door schedule (a grid of cells) beside the plan, as real sheets."""
    out = rgb.copy()
    for r in range(9):
        cv2.line(out, (880, 120 + 25 * r), (980, 120 + 25 * r), (0, 0, 0), 1)
    for c in range(3):
        cv2.line(out, (880 + 50 * c, 120), (880 + 50 * c, 320), (0, 0, 0), 1)
    return out


def test_a_picture_is_laid_over_its_plan_through_its_parts() -> None:
    image = with_schedule(sheet())
    walls = by_walls([Segment(a=a, b=b) for a, b in PLAN], sheet_walls.reader(lambda _: image))
    laid = walls(PLAN_SHEET, PICTURE)
    assert not isinstance(laid, str), laid
    to_plan, how = laid
    h, w = image.shape[:2]
    for corner in ((0, 0), (24, 0), (24, 14), (8, 9)):
        x, y = px(corner)
        fx, fy = to_plan.apply((x / w, y / h))
        assert abs(fx * 40 - corner[0]) < 0.3 and abs(fy * 30 - corner[1]) < 0.3, (corner, how)


def test_a_big_picture_is_read_shrunk_and_given_back_in_its_own_pixels() -> None:
    image = cv2.resize(sheet(), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)  # 3000 px
    parts, size = sheet_walls.crops(image)
    assert size == (3000.0, 2100.0)
    assert parts[0][0] == (0.0, 0.0, 3000.0, 2100.0) or any(
        box == (0.0, 0.0, 3000.0, 2100.0) for box, _ in parts
    )
    whole = next(lines for box, lines in parts if box == (0.0, 0.0, 3000.0, 2100.0))
    xs = [v for s in whole for v in (s.a[0], s.b[0])]
    assert max(xs) > 2500  # in the picture's pixels, not the shrunk ones
    a, b = px((0, 0)), px((24, 0))  # the plan's top wall, 3x
    assert any(
        abs(s.a[1] - 3 * a[1]) < 15 and abs(s.b[1] - 3 * b[1]) < 15 and abs(s.a[0] - s.b[0]) > 600
        for s in whole
    ), PX_PER_M


def test_no_picture_or_no_lines_is_said() -> None:
    read = sheet_walls.reader(lambda _: None)
    assert read(PICTURE) == "the services sheet is no picture file: its walls are not read"
    blank = sheet_walls.reader(lambda _: np.full((400, 600, 3), 255, np.uint8))
    assert blank(PICTURE) == "no wall lines were read on the services sheet"
