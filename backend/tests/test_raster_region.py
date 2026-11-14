"""The region component (`region:<arm>`): eight views, plan windows, the annotated-flat filter
and view fusion, with a fake detector and a fake segmenter on pages drawn by code. No weights.

The fake detector really looks at its input: a grey block is a plan, a red block of at least
three canvas pixels across is a door. So the eight views agree, a door too small on the whole
sheet is found in its plan's window, and the counts follow from the drawing."""

import io
import json
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.adapters.raster_detector import post
from app.adapters.raster_detector.views import VIEWS, Det, box_back, fuse_views, view_of
from app.adapters.raster_region import RegionDetector, RegionFacts, load_arm, predict_mask, steps
from app.adapters.raster_region.steps import Frame, Window
from app.core.drawing.model import Page
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Sheet

PNG = "data/cubicasa5k/x.png"
SIDE = 100
CONFIG = post.DetectorConfig.model_validate(
    {
        "format": "dfine",
        "side": SIDE,
        "classes": ("door", "window", "plan"),
        "element_class": {"door": "door", "window": "window", "plan": None},
        "read": ["door", "window"],
        "thresholds": {"door": 0.5, "window": 0.5, "plan": 0.5},
        "groups": [["door"]],
    }
)
GREY, RED, MAGENTA = (160, 160, 160), (230, 0, 0), (230, 0, 230)
FACTS = RegionFacts(side=64, mean=(0.5, 0.5, 0.5), std=(0.25, 0.25, 0.25))


class Named:
    def __init__(self, name: str) -> None:
        self.name = name


def blobs(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Bounding boxes (x0, y0, x1, y1, end exclusive) of 4-connected true pixels."""
    seen = np.zeros_like(mask, dtype=bool)
    found = []
    for y, x in zip(*np.nonzero(mask), strict=True):
        if seen[y, x]:
            continue
        queue, xs, ys = deque([(y, x)]), [], []
        seen[y, x] = True
        while queue:
            cy, cx = queue.popleft()
            xs.append(cx)
            ys.append(cy)
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                inside = 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1]
                if inside and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        found.append((min(xs), min(ys), max(xs) + 1, max(ys) + 1))
    return found


class FakeDetector:
    """A YOLO export (format dfine) that finds grey plans and red doors in what it is fed."""

    def __init__(self) -> None:
        self.calls = 0

    def get_inputs(self) -> list[Named]:
        return [Named("images"), Named("orig_target_sizes")]

    def get_outputs(self) -> list[Named]:
        return [Named("labels"), Named("boxes"), Named("scores")]

    def run(self, output_names: Any, input_feed: dict[str, Any]) -> list[np.ndarray]:
        self.calls += 1
        rgb = input_feed["images"][0].transpose(1, 2, 0)
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        rows: list[tuple[int, tuple[int, int, int, int], float]] = []
        grey = (abs(r - g) < 0.08) & (abs(g - b) < 0.08) & (r > 0.4) & (r < 0.8)
        for box in blobs(grey | (r > 0.6) & (g < 0.35) & (b < 0.35)):
            if (box[2] - box[0]) * (box[3] - box[1]) >= 100:
                rows.append((2, box, 0.9))
        for box in blobs((r > 0.6) & (g < 0.35) & (b < 0.35)):
            if min(box[2] - box[0], box[3] - box[1]) >= 3:
                rows.append((0, box, 0.8))
        labels = np.array([[label for label, _, _ in rows] + [0]], dtype=np.int64)
        boxes = np.array([[list(map(float, box)) for _, box, _ in rows] + [[0, 0, 0, 0]]])
        scores = np.array([[score for _, _, score in rows] + [0.0]], dtype=np.float32)
        return [labels, boxes.astype(np.float32), scores]


class FakeSegmenter:
    """The annotated flat = everything outside the box around the magenta (a neighbour flat)."""

    def get_inputs(self) -> list[Named]:
        return [Named("images")]

    def get_outputs(self) -> list[Named]:
        return [Named("logits")]

    def run(self, output_names: Any, input_feed: dict[str, Any]) -> list[np.ndarray]:
        x = input_feed["images"][0].transpose(1, 2, 0) * np.array(FACTS.std) + np.array(FACTS.mean)
        r, g, b = x[..., 0], x[..., 1], x[..., 2]
        logits = np.full(r.shape, 8.0, dtype=np.float32)
        ys, xs = np.nonzero((r > 0.6) & (b > 0.6) & (g < 0.4))
        if len(xs):
            logits[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1] = -8.0
        return [logits[None, None]]


class Files:
    def __init__(self, image: Image.Image) -> None:
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        self.data = buffer.getvalue()

    def read(self, path: str) -> bytes:
        assert path == PNG
        return self.data


def sheet(image: Image.Image) -> tuple[DrawingFile, Sheet]:
    file = DrawingFile(path=PNG, size=1, sha256="0" * 64, kind="png")
    page = Page(page=1, width=image.width, height=image.height, unit="px")
    return file, Sheet(file=file, pages=(page,))


def run(image: Image.Image, region: bool = True, views: int = 8, windows: bool = True):
    detector = FakeDetector()
    segmenter = (FACTS, FakeSegmenter()) if region else None
    component = RegionDetector(Files(image), CONFIG, detector, segmenter, "fake", views, windows)
    return component.extract(*sheet(image)), detector


def flat_with_neighbour() -> Image.Image:
    """One flat (grey, a door) and a neighbour drawn beside it (magenta, a door)."""
    image = Image.new("RGB", (200, 100), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 110, 90), fill=GREY)
    draw.rectangle((40, 40, 55, 55), fill=RED)
    draw.rectangle((130, 10, 190, 90), fill=MAGENTA)
    draw.rectangle((150, 40, 165, 55), fill=RED)
    return image


def two_flats(door: int) -> Image.Image:
    """Two plans side by side on a wide sheet, each with a door `door` pixels wide."""
    image = Image.new("RGB", (800, 200), "white")
    draw = ImageDraw.Draw(image)
    for left in (20, 420):
        draw.rectangle((left, 20, left + 360, 180), fill=GREY)
        draw.rectangle((left + 100, 90, left + 100 + door - 1, 90 + door - 1), fill=RED)
    return image


def test_doors_of_the_neighbouring_flat_are_not_counted() -> None:
    found, detector = run(flat_with_neighbour())
    assert [e.class_ for e in found.elements] == ["door"]
    assert found.elements[0].box[0] < 0.5  # the flat's door, not the neighbour's
    assert len(found.plans) == 1
    assert detector.calls == 8  # one plan: the whole page in eight views, no windows
    assert found.elements[0].attrs["score"] == pytest.approx(0.8)  # every view saw it


def test_the_mask_is_on_the_segmenters_canvas_and_leaves_the_neighbour_out() -> None:
    mask, frame = predict_mask(flat_with_neighbour(), FACTS, FakeSegmenter())
    assert mask.shape == (64, 64)
    assert (frame.side, frame.new_width, frame.new_height, frame.dx, frame.dy) == (
        64,
        64,
        32,
        0,
        16,
    )
    flat = frame.to_canvas(47, 47)  # the flat's door, page pixels
    neighbour = frame.to_canvas(157, 47)  # the neighbour's door
    assert mask[int(flat[1]), int(flat[0])]
    assert not mask[int(neighbour[1]), int(neighbour[0])]


def test_without_a_segmenter_the_whole_page_counts() -> None:
    found, _ = run(flat_with_neighbour(), region=False)
    assert [e.class_ for e in found.elements] == ["door", "door"]


def test_on_a_sheet_of_two_plans_each_plan_is_read_in_its_own_window() -> None:
    image = two_flats(door=12)  # 1.5 px on the whole sheet's 100 px canvas, about 3 in a window
    canvas, _ = post.letterbox(image, SIDE)
    alone = FakeDetector().run(None, {"images": post.pixels(canvas, CONFIG)})
    assert 0 not in alone[0][0][alone[2][0] > 0]  # the whole sheet alone shows no door

    found, detector = run(image)
    assert detector.calls == 8 + 2 * 8  # the page, then two windows, eight views each
    assert [e.class_ for e in found.elements] == ["door", "door"]
    assert len(found.plans) == 2


def test_with_windows_off_a_sheet_of_two_plans_is_read_whole() -> None:
    found, detector = run(two_flats(door=12), windows=False)
    assert detector.calls == 8
    assert found.elements == ()  # the doors are too small on the whole sheet
    assert len(found.plans) == 2


def test_each_detector_arm_brings_its_own_knobs_and_others_are_refused(tmp_path: Path) -> None:
    model = {
        "format": "dfine",
        "side": 1536,
        "classes": ["door", "plan"],
        "element_class": {"door": "door", "plan": None},
        "licence": "prose is ignored",
    }
    folder = tmp_path / "C-yolo26s-1536"
    folder.mkdir()
    (folder / "model.json").write_text(json.dumps(model))
    (folder / "detector.json").write_text("{}")  # core's own thresholds: not used
    knobs, config = load_arm(folder)
    assert (knobs.views, knobs.windows) == (1, False)
    assert config.side == 1536
    assert set(config.thresholds) >= {"door", "plan"}
    assert config.dedup == "ios" and config.groups == (("door",),)

    other = tmp_path / "C-yolo26m"
    other.mkdir()
    (other / "model.json").write_text(json.dumps(model))
    with pytest.raises(InvalidInputError, match="no knobs"):
        load_arm(other)


class HalfBlind(FakeDetector):
    """Sees nothing in every second view."""

    def run(self, output_names: Any, input_feed: dict[str, Any]) -> list[np.ndarray]:
        found = super().run(output_names, input_feed)
        if self.calls % 2 == 0:
            found[2] = np.zeros_like(found[2])
        return found


def test_a_door_half_the_views_miss_scores_half_and_is_not_counted() -> None:
    image = flat_with_neighbour()
    component = RegionDetector(Files(image), CONFIG, HalfBlind(), None, "fake")
    found = component.extract(*sheet(image))
    assert found.elements == ()  # door score 4 x 0.8 / 8 = 0.4, under the 0.5 threshold
    assert len(found.plans) == 0  # the plan too: 0.45


def test_one_view_reads_the_canvas_once() -> None:
    found, detector = run(flat_with_neighbour(), views=1)
    assert detector.calls == 1
    assert [e.class_ for e in found.elements] == ["door"]


def test_only_a_yolo_export_and_up_to_eight_views() -> None:
    rfdetr = CONFIG.model_copy(update={"format": "rfdetr"})
    with pytest.raises(InvalidInputError, match="dfine"):
        RegionDetector(Files(flat_with_neighbour()), rfdetr, FakeDetector(), None, "x")
    with pytest.raises(InvalidInputError, match="views"):
        RegionDetector(Files(flat_with_neighbour()), CONFIG, FakeDetector(), None, "x", 9)


# ------------------------------------------------------------------------------ the steps


@pytest.mark.parametrize("view", VIEWS)
def test_a_box_found_on_a_view_goes_back_to_the_canvas(view: tuple[int, int, int]) -> None:
    canvas = Image.new("RGB", (50, 50), "white")
    ImageDraw.Draw(canvas).rectangle((5, 10, 14, 29), fill="black")  # x 5..15, y 10..30
    turned = np.asarray(view_of(canvas, view).convert("L")) < 128
    (box,) = blobs(turned)
    x0, y0, x1, y1 = (float(v) for v in box)
    assert box_back((x0, y0, x1, y1), view, 50) == (5.0, 10.0, 15.0, 30.0)


def test_views_of_one_object_fuse_into_one_detection_scored_over_all_views() -> None:
    found = [
        Det("door", 0.8, (10, 10, 20, 20), 0),
        Det("door", 0.6, (11, 11, 21, 21), 1),
        Det("door", 0.7, (10, 10, 20, 20), 1),  # second box of view 1: its own object
        Det("window", 0.9, (10, 10, 20, 20), 2),  # other class: its own object
    ]
    fused = fuse_views(found, views=8)
    assert [(d.name, d.score, d.box) for d in fused] == [
        ("window", round(0.9 / 8, 4), (10.0, 10.0, 20.0, 20.0)),
        ("door", round(1.5 / 8, 4), (10.0, 10.0, 20.0, 20.0)),
        ("door", round(0.6 / 8, 4), (11.0, 11.0, 21.0, 21.0)),
    ]
    assert fuse_views(found, views=1) == found


def test_windows_come_from_sure_plans_and_keep_their_own_elements() -> None:
    page = Frame.fit(2000, 1000, 1000)  # scale 0.5, dy 250
    found = [Det("plan", 0.9, (0, 250, 500, 750)), Det("plan", 0.9, (500, 250, 1000, 750)),
             Det("plan", 0.3, (0, 250, 1000, 750))]  # fmt: skip
    windows = steps.plan_windows(found, page, "plan", 0.43, 0.05, 0.0)
    assert [w.crop for w in windows] == [(0, 0, 1050, 1000), (950, 0, 2000, 1000)]

    left = Window((0, 0, 1100, 1000), (0.0, 0.0, 1000.0, 1000.0))
    right = Window((900, 0, 2000, 1000), (1000.0, 0.0, 2000.0, 1000.0))
    one = Frame.fit(1100, 1000, 1100)  # scale 1, dy 50
    merged = steps.merge_windows(
        [*found, Det("door", 0.9, (10, 260, 20, 270))],
        page,
        [
            (left, one, [Det("door", 0.9, (100, 100, 120, 140)),  # page x 110: left's
                         Det("window", 0.9, (1050, 100, 1090, 110)),  # page x 1070: right's
                         Det("plan", 0.9, (0, 0, 10, 10))]),  # window plans are dropped
            (right, one, [Det("window", 0.9, (150, 100, 190, 110))]),  # page x 1070
        ],
        "plan",
    )  # fmt: skip
    assert [d.name for d in merged] == ["plan", "plan", "plan", "door", "window"]
    assert merged[3].box == pytest.approx((50.0, 275.0, 60.0, 295.0))  # page px / 2, + dy


def test_an_empty_mask_keeps_every_box() -> None:
    page = Frame.fit(100, 100, 100)
    found = [Det("door", 0.9, (10, 10, 20, 20))]
    empty = np.zeros((50, 50), dtype=bool)
    assert steps.keep_in_region(found, page, empty, Frame.fit(100, 100, 50), "plan", 0.02) == found
