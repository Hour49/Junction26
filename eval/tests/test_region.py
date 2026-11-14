"""The annotated region of each experiment image and the ink beyond it (golden-13 task 1)."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image, ImageDraw

from stoa_eval.exp_split import ExpSplit
from stoa_eval.extraction import Extraction
from stoa_eval.families import group_of
from stoa_eval.region import (
    EXTENDS_AT,
    AnnotatedRegions,
    annotate,
    grey,
    ink,
    outer_rings,
    region,
)
from tests.test_exp_split import dataset, exp_split, plan_files, run
from tests.test_extraction_scoring import element

__all__ = ["dataset"]  # the fixture, used by name

W, H = 600, 300
M_PER_PX = 0.05  # margin 10 px, gap 5 px, solid 10 px; the border band is 6 px


def gold(
    file: str = "data/cubicasa5k/plan-1.png",
    rooms: list[tuple[float, float, float, float]] | None = None,
    elements: list[dict[str, Any]] | None = None,
    m_per_px: float | None = M_PER_PX,
    size: tuple[int, int] = (W, H),
) -> Extraction:
    """A one-page gold with square rooms given as pixel boxes."""
    width, height = size
    shapes = [
        {
            "id": f"r{n}",
            "type": "living",
            "page": 1,
            "plan": "p1",
            "polygon": [
                [x0 / width, y0 / height],
                [x1 / width, y0 / height],
                [x1 / width, y1 / height],
                [x0 / width, y1 / height],
            ],
            "box": [x0 / width, y0 / height, x1 / width, y1 / height],
        }
        for n, (x0, y0, x1, y1) in enumerate(rooms or [(50, 50, 250, 250)])
    ]
    scale = (
        {"status": "estimated", "m_per_unit": m_per_px, "source": "test", "uncertainty": 0.1}
        if m_per_px
        else {"status": "no_scale"}
    )
    return Extraction.model_validate(
        {
            "schema": "extraction_v1",
            "file": file,
            "split": "dev",
            "truth": "elements",
            "pages": [{"page": 1, "width": width, "height": height, "unit": "px"}],
            "plans": [{"id": "p1", "page": 1, "box": [0, 0, 1, 1]}],
            "elements": elements or [],
            "rooms": shapes,
            "scale": scale,
        }
    )


def flat(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """A 200 px flat drawn in 2 px lines: outer walls and two partitions."""
    draw.rectangle((x, y, x + 200, y + 200), outline=0, width=2)
    draw.line((x + 100, y, x + 100, y + 200), fill=0, width=2)
    draw.line((x, y + 100, x + 100, y + 100), fill=0, width=2)


def sheet() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(image)
    flat(draw, 50, 50)
    return image, draw


def test_region_is_the_gold_grown_by_the_margin_in_pixels() -> None:
    shape = region(gold())
    assert shape.bounds == pytest.approx((40, 40, 260, 260))  # 0.5 m at 0.05 m/px = 10 px
    [ring] = outer_rings(shape)
    assert ring[0] == ring[-1]
    assert set(ring) == {(40.0, 40.0), (260.0, 40.0), (260.0, 260.0), (40.0, 260.0)}


def test_region_adds_elements_and_clips_to_the_page() -> None:
    door = element("e1", [0.0, 0.5, 20 / W, 0.6])  # at the left edge, beyond the room
    shape = region(gold(elements=[door]))
    assert shape.bounds[0] == 0  # the door's margin would reach x = -10
    assert shape.area > region(gold()).area


def test_a_plan_with_no_room_or_element_adds_its_box() -> None:
    made = gold().model_copy(deep=True)
    made.rooms[0].plan = "p1"
    made.plans[0].box = (300 / W, 50 / H, 500 / W, 250 / H)
    assert region(made).bounds == pytest.approx(
        (40, 40, 260, 260)
    )  # p1 has a room: its box adds nothing
    made.rooms[0].plan = "p2"
    assert region(made).bounds == pytest.approx((40, 40, 510, 260))  # p1 is empty: its box counts
    made.rooms = []
    assert region(made).bounds == pytest.approx((290, 40, 510, 260))


def test_two_flats_far_apart_are_two_rings() -> None:
    assert len(outer_rings(region(gold(rooms=[(50, 50, 250, 250), (350, 50, 550, 250)])))) == 2


@pytest.mark.parametrize(
    ("made", "reason"),
    [
        (gold(m_per_px=None), "no m_per_unit"),
        (gold().model_copy(update={"rooms": [], "plans": []}), "no gold room, element or plan"),
    ],
)
def test_region_refuses(made: Extraction, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        region(made)


def test_a_lone_flat_does_not_extend() -> None:
    image, _ = sheet()
    record = annotate("train", gold(), image)
    assert record.ink_outside == 0
    assert not record.extends
    assert (record.width, record.height, record.style) == (W, H, "plan")


def test_a_neighbouring_flat_extends() -> None:
    image, draw = sheet()
    flat(draw, 330, 50)  # the same flat again, unannotated
    record = annotate("val", gold(), image)
    assert record.ink_outside == pytest.approx(1.0, abs=0.05)
    assert record.extends


def test_ink_just_beyond_the_region_is_its_own() -> None:
    image, draw = sheet()
    draw.line((263, 50, 263, 250), fill=0, width=2)  # 3 px past the region, inside the gap
    assert annotate("train", gold(), image).ink_outside == 0


def test_a_line_along_the_image_edge_is_not_drawing() -> None:
    image, draw = sheet()
    draw.line((0, 2, W, 2), fill=0, width=2)  # a scan edge, inside the 6 px border band
    assert annotate("train", gold(), image).ink_outside == 0


def test_a_scanner_bar_is_not_drawing() -> None:
    image, draw = sheet()
    draw.rectangle((0, 270, W, H), fill=0)  # 30 px of solid black along the bottom
    record = annotate("train", gold(), image)
    assert record.ink_outside < 0.01
    assert not record.extends


def test_a_thin_scanner_bar_across_the_sheet_is_not_drawing() -> None:
    image, draw = sheet()
    draw.rectangle((0, 280, W, 285), fill=0)  # 6 px: thinner than a fill, past the border band
    draw.rectangle((0, 290, W // 2, 292), fill=0)  # half the width: a line, so it counts
    record = annotate("train", gold(), image)
    assert record.ink_outside == pytest.approx(300 * 3 / 2200, abs=0.03)  # only the half line


@pytest.mark.parametrize("m_per_px", [M_PER_PX, 0.5 / 11])  # windows of 10 and 11 px
def test_thin_lines_are_ink_and_solid_fills_are_not(m_per_px: float) -> None:
    pixels = np.full((100, 100), 255, dtype=np.uint8)
    pixels[10:12, 10:90] = 0  # a 2 px line
    pixels[40:80, 40:80] = 0  # a 40 px block
    pixels[90:100, 0:10] = 0  # a 10 px block in the corner
    dark = ink(pixels, m_per_px)
    assert dark[10:12, 10:90].all()
    assert not dark[40:80, 40:80].any()
    if m_per_px == M_PER_PX:  # it fits a 10 px window exactly: a fill
        assert not dark[90:100, 0:10].any()
    else:  # an 11 px window doesn't fit: lines
        assert dark[90:100, 0:10].all()


def test_transparent_background_is_white() -> None:
    image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    image.putpixel((1, 1), (0, 0, 0, 255))
    pixels = grey(image)
    assert pixels[1, 1] == 0
    assert (pixels == 255).sum() == 15


def test_a_size_mismatch_is_refused() -> None:
    image, _ = sheet()
    with pytest.raises(ValueError, match="image 600x300, gold 300x300"):
        annotate("train", gold(size=(300, 300)), image)


def test_extends_cut() -> None:
    assert EXTENDS_AT == 0.2  # the cut chosen on hand-labelled images (.agents/exp/golden.md)


def give_drawing(dataset: Path, file: str, split: str = "dev", neighbour: bool = False) -> None:
    """A gold with a room and a scale, and a drawing, for one image."""
    name = file.removeprefix("data/cubicasa5k/").replace("/", "__")
    made = gold(file=file).model_copy(update={"split": split})
    (dataset / f"gold/cubicasa5k/{name}.json").write_text(made.model_dump_json(by_alias=True))
    image, draw = sheet()
    if neighbour:
        flat(draw, 330, 50)
    path = dataset / "drawings" / file
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def give_drawings(dataset: Path, split: ExpSplit, neighbour: set[str]) -> None:
    for part in ("train", "val"):
        for file in split.parts[part].files:
            give_drawing(dataset, file, neighbour=file in neighbour)


def annotated_region(dataset: Path, out: Path, *extra: object) -> int:
    return run(
        "annotated-region", "--exp-dir", dataset / "exp", "--split-dir", dataset / "split",
        "--golden-dir", dataset / "v2", "--gold", dataset / "gold",
        "--dataset", dataset / "drawings", "--out", out, *extra,
    )  # fmt: skip


def test_cli_covers_train_and_val_only(dataset: Path) -> None:
    assert exp_split(dataset, dataset / "exp") == 0
    split = ExpSplit.model_validate_json((dataset / "exp/split.json").read_text())
    neighbour = {split.parts["train"].files[0], split.parts["val"].files[0]}
    give_drawings(dataset, split, neighbour)
    out = dataset / "labels/annotated_region.json"
    assert annotated_region(dataset, out) == 0
    result = AnnotatedRegions.model_validate_json(out.read_text())
    expected = {file: part for file, part in split.part_of().items() if part != "test"}
    assert {file: record.part for file, record in result.images.items()} == expected
    assert {file for file, record in result.images.items() if record.extends} == neighbour
    sealed = set(json.loads((dataset / "split/manifest.json").read_text())["eval_groups"])
    assert not {group_of(file) for file in result.images} & sealed
    assert not set(split.excluded_golden) & set(result.images)
    plan = result.styles["plan"]
    assert (plan["train"].extends, plan["val"].extends) == (1, 1)
    parallel = dataset / "labels/parallel.json"
    assert annotated_region(dataset, parallel, "--workers", 2) == 0
    assert parallel.read_bytes() == out.read_bytes()  # the same file, however it is run


@pytest.mark.parametrize(
    ("intruder", "reason"), [("eval", "sealed eval group"), ("golden", "golden v2 drawing")]
)
def test_cli_refuses_a_split_with_an_eval_or_golden_file(
    dataset: Path, intruder: str, reason: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert exp_split(dataset, dataset / "exp") == 0
    path = dataset / "exp/split.json"
    split = ExpSplit.model_validate_json(path.read_text())
    give_drawings(dataset, split, set())
    sealed = set(json.loads((dataset / "split/manifest.json").read_text())["eval_groups"])
    if intruder == "eval":
        extra = next(file for file in plan_files() if group_of(file) in sealed)
    else:
        extra = split.excluded_golden[0]
    give_drawing(dataset, extra, split=intruder if intruder == "eval" else "dev")  # readable
    split.parts["train"].files.append(extra)
    path.write_text(split.model_dump_json(), "utf-8")
    assert annotated_region(dataset, dataset / "out.json") == 1
    assert reason in capsys.readouterr().err
    assert not (dataset / "out.json").exists()
