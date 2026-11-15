"""walls: a services picture's wall lines (grey, under the coloured runs), in page pixels."""

import ast
import math
from pathlib import Path

import cv2
import numpy as np

from app.adapters.discipline_pictures.walls import walls
from app.core.services.register import Place, Segment, register

H, W = 700, 1000
PX_PER_M = 30.0
ORIGIN = (150.0, 120.0)  # px of the plan's (0, 0)
# a plan (metres): the outer box and rooms
PLAN = [
    ((0, 0), (24, 0)),
    ((24, 0), (24, 14)),
    ((24, 14), (0, 14)),
    ((0, 14), (0, 0)),
    ((8, 0), (8, 9)),
    ((8, 9), (17, 9)),
    ((17, 4), (17, 14)),
    ((0, 5), (5, 5)),
    ((20, 6), (24, 6)),
]
PIPES = [((60.0, 400.0), (940.0, 420.0)), ((500.0, 80.0), (500.0, 650.0))]  # px, blue


def px(p) -> tuple[int, int]:
    return round(ORIGIN[0] + p[0] * PX_PER_M), round(ORIGIN[1] + p[1] * PX_PER_M)


def sheet(noisy: bool = False) -> np.ndarray:
    """A services picture: a frame and title block, grey walls, blue pipes over them, text."""
    rgb = np.full((H, W, 3), 255, np.uint8)
    cv2.rectangle(rgb, (10, 10), (W - 10, H - 10), (0, 0, 0), 2)  # frame
    cv2.rectangle(rgb, (W - 260, H - 90), (W - 10, H - 10), (0, 0, 0), 2)  # title block
    cv2.line(rgb, (W - 260, H - 50), (W - 10, H - 50), (0, 0, 0), 1)
    for a, b in PLAN:
        cv2.line(rgb, px(a), px(b), (150, 150, 150), 5)
    for a, b in PIPES:
        cv2.line(rgb, tuple(map(round, a)), tuple(map(round, b)), (200, 60, 20), 3)
    for i in range(6):  # room text
        cv2.putText(rgb, "WC 1.0" + str(i), (200 + 90 * i, 300), 0, 0.5, (0, 0, 0), 1)
    if noisy:  # a scan: blur, uneven light, salt and pepper
        rng = np.random.default_rng(0)
        rgb = cv2.GaussianBlur(rgb, (3, 3), 0)
        light = np.linspace(0.85, 1.0, W)[None, :, None]
        rgb = (rgb * light).astype(np.uint8)
        salt = rng.random((H, W)) < 0.001
        rgb[salt] = rng.choice([0, 255], (int(salt.sum()), 1))
    return rgb


def dist(p, a, b) -> float:
    """From point p to the segment a-b."""
    pa, ba = np.subtract(p, a), np.subtract(b, a)
    t = np.clip(pa @ ba / (ba @ ba), 0, 1)
    return float(np.linalg.norm(pa - t * ba))


def on(seg: Segment, line, tol: float = 6.0) -> bool:
    return all(dist(p, *line) <= tol for p in (seg.a, seg.b))


def check(found: list[Segment]) -> None:
    truth = [(px(a), px(b)) for a, b in PLAN]
    for line in truth:  # every wall is found, nearly whole
        mine = [s for s in found if on(s, line)]
        assert sum(math.dist(s.a, s.b) for s in mine) >= 0.8 * math.dist(*line), line
    for s in found:  # and nothing else: no pipe, no frame, no title block, no text
        assert any(on(s, line) for line in truth), s


def test_the_grey_walls_are_found_and_the_pipes_frame_and_text_are_not() -> None:
    check(list(walls(sheet())))


def test_a_scan_of_it_gives_the_same_walls() -> None:
    check(list(walls(sheet(noisy=True))))


def test_a_blank_page_has_no_walls() -> None:
    assert walls(np.full((H, W, 3), 255, np.uint8)) == ()


def test_its_walls_lay_the_picture_over_the_plan() -> None:
    plan = [Segment(a=a, b=b) for a, b in PLAN]
    place = register(plan, walls(sheet(noisy=True)))
    assert isinstance(place, Place), place
    assert abs(place.rotation_deg) < 0.5 and abs(place.scale * PX_PER_M - 1) < 0.02
    assert math.dist(place.shift, (-ORIGIN[0] / PX_PER_M, -ORIGIN[1] / PX_PER_M)) < 0.2


def test_nothing_in_the_app_calls_it_yet() -> None:
    """With DISCIPLINE_PICTURES off nothing changes: no module of the app imports `walls`."""
    app = Path(__file__).resolve().parents[1] / "app"
    for path in app.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module + "." + a.name for a in node.names]
                assert not any(n.endswith("discipline_pictures.walls") for n in names), path
                assert not node.module.endswith("discipline_pictures.walls"), path


def building(fill: float) -> tuple[np.ndarray, list]:
    """A frame and a building whose outer walls span `fill` of the page, rooms inside."""
    rgb = np.full((H, W, 3), 255, np.uint8)
    cv2.rectangle(rgb, (4, 4), (W - 5, H - 5), (0, 0, 0), 2)
    x0, y0 = round(W * (1 - fill) / 2), round(H * (1 - fill) / 2)
    x1, y1 = W - x0, H - y0
    lines = [
        ((x0, y0), (x1, y0)),
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
        ((x0, 300), (600, 300)),  # touches the outer wall: one ink piece
        ((600, y0), (600, 300)),
    ]
    for a, b in lines:
        cv2.line(rgb, a, b, (120, 120, 120), 4)
    return rgb, lines


def test_a_building_filling_the_page_keeps_its_walls_and_the_frame_goes() -> None:
    rgb, lines = building(0.92)
    found = walls(rgb)
    for line in lines:
        assert any(on(s, line) for s in found), line
    for s in found:
        assert any(on(s, line) for line in lines), s


def test_a_hatched_page_does_not_crash_and_keeps_its_frame_out() -> None:
    rgb, _ = building(0.92)
    for x in range(-H, W, 12):  # hatching across the building
        cv2.line(rgb, (x, H), (x + H, 0), (90, 90, 90), 1)
    for s in walls(rgb):
        assert not (min(s.a[0], s.b[0]) < 8 and max(s.a[0], s.b[0]) < 8), s  # not the left frame


def test_an_empty_image_has_no_walls() -> None:
    assert walls(np.zeros((0, 0, 3), np.uint8)) == ()


def test_grey_and_four_channel_pictures_give_the_same_walls() -> None:
    rgb, _ = building(0.8)
    want = walls(rgb)
    assert walls(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)) == want
    assert walls(cv2.cvtColor(rgb, cv2.COLOR_RGB2RGBA)) == want
