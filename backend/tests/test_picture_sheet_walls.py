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
PICTURE = Sheet(  # its scale bar read: 30 px a metre on a 1000 x 700 px page
    drawing_id="pic",
    page=1,
    name="heating.png",
    disciplines=("heating",),
    size_m=(1000 / PX_PER_M, 700 / PX_PER_M),
)


def with_schedule(rgb: np.ndarray) -> np.ndarray:
    """The picture with a door schedule (a grid of cells) beside the plan, as real sheets."""
    out = rgb.copy()
    for r in range(9):
        cv2.line(out, (880, 120 + 25 * r), (980, 120 + 25 * r), (0, 0, 0), 1)
    for c in range(3):
        cv2.line(out, (880 + 50 * c, 120), (880 + 50 * c, 320), (0, 0, 0), 1)
    return out


def stored(image: np.ndarray | None, sha: str = "sha-1"):
    """A sheet's file as the follower finds it: its sha256 and how to load its bytes."""
    data = b"%PDF-1.7 not a picture" if image is None else cv2.imencode(".png", image)[1].tobytes()
    return lambda _: (sha, lambda: data)


def test_a_picture_is_laid_over_its_plan_through_its_parts() -> None:
    image = with_schedule(sheet())
    walls = by_walls([Segment(a=a, b=b) for a, b in PLAN], sheet_walls.reader(stored(image), {}))
    laid = walls(PLAN_SHEET, PICTURE)
    assert not isinstance(laid, str), laid
    to_plan, how = laid
    h, w = image.shape[:2]
    for corner in ((0, 0), (24, 0), (24, 14), (8, 9)):
        x, y = px(corner)
        fx, fy = to_plan.apply((x / w, y / h))
        assert abs(fx * 40 - corner[0]) < 0.3 and abs(fy * 30 - corner[1]) < 0.3, (corner, how)


def test_with_no_scale_bar_a_sheet_laid_only_by_its_part_is_refused() -> None:
    """Review #590 SHOULD: the same picture without its scale bar read. Its whole page (title
    block, schedule, frame) does not lay; its plan view does, but nothing checks that part's
    size: refused, said why."""
    image = with_schedule(sheet())
    walls = by_walls([Segment(a=a, b=b) for a, b in PLAN], sheet_walls.reader(stored(image), {}))
    got = walls(PLAN_SHEET, PICTURE.model_copy(update={"size_m": None}))
    assert isinstance(got, str) and "the sheet has no scale and its whole page does not lay" in got


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
    for file_of in (stored(None), lambda _: None):
        read = sheet_walls.reader(file_of, {})
        assert read(PICTURE) == "the services sheet is no picture file: its walls are not read"
    blank = sheet_walls.reader(stored(np.full((400, 600, 3), 255, np.uint8)), {})
    assert blank(PICTURE) == "no wall lines were read on the services sheet"


def test_a_sheet_s_parts_are_read_once_per_file_and_code_version(monkeypatch) -> None:
    """Every proposal pairs every picture sheet: its parts (0.2-0.5 s a picture on the dev1
    DigitalHub renders) are kept by the file's sha256, page and the reader's code version, so
    the next proposal reads neither the file nor its walls again."""
    calls = {"walls": 0, "load": 0}
    real = sheet_walls.walls

    def counted(image):
        calls["walls"] += 1
        return real(image)

    monkeypatch.setattr(sheet_walls, "walls", counted)
    data = cv2.imencode(".png", with_schedule(sheet()))[1].tobytes()

    def file_of(sha: str):
        def load() -> bytes:
            calls["load"] += 1
            return data

        return lambda _: (sha, load)

    kept: dict = {}
    first = sheet_walls.reader(file_of("sha-1"), kept)(PICTURE)
    reads = calls["walls"]
    assert reads >= 1 and calls["load"] == 1
    again = sheet_walls.reader(file_of("sha-1"), kept)(PICTURE)  # the next proposal's follower
    assert again == first and calls == {"walls": reads, "load": 1}
    sheet_walls.reader(file_of("sha-2"), kept)(PICTURE)  # another file
    assert calls["load"] == 2
    monkeypatch.setattr(sheet_walls, "CODE", "another")  # walls() or the finder changed
    sheet_walls.reader(file_of("sha-1"), kept)(PICTURE)
    assert calls["load"] == 3


def test_the_kept_parts_are_bounded(monkeypatch) -> None:
    monkeypatch.setattr(sheet_walls, "KEPT", 2)
    kept: dict = {}
    blank = cv2.imencode(".png", np.full((100, 100, 3), 255, np.uint8))[1].tobytes()
    for i in range(5):
        sheet_walls.reader(lambda _, i=i: (f"sha-{i}", lambda: blank), kept)(PICTURE)
        assert len(kept) <= 2
