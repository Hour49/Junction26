"""RASTER_TILES=auto (app/adapters/raster_detector/tiles.py): a page longer than 4000 px is read
by the detector tile by tile; a small page is read whole, as before. Fake ONNX session, no
weights."""

import numpy as np

from app.adapters.raster_detector import OnnxDetector, tiles
from tests.test_raster_detector import FakeSession, Files, config, png, sheet


def session() -> FakeSession:
    """Every canvas (page or tile) shows one door in its middle and one window on its right edge."""
    return FakeSession(
        ["images", "orig_target_sizes"],
        {
            "labels": np.array([[0, 2]]),
            "boxes": np.array([[[45, 45, 55, 55], [90, 45, 100, 55]]], dtype=np.float32),
            "scores": np.array([[0.9, 0.8]], dtype=np.float32),
        },
    )


def counts(width: int, height: int, tiled: bool) -> dict[str, int]:
    detector = OnnxDetector(Files(png(width, height)), config(), session(), "B", tiles=tiled)
    found = detector.extract(*sheet(width, height))
    made: dict[str, int] = {}
    for element in found.elements:
        made[element.class_] = made.get(element.class_, 0) + 1
    return made


def test_a_big_page_is_read_tile_by_tile_and_seams_are_not_counted_twice() -> None:
    # 5000 x 3000: tile origins x 0, 1792, 2952 and y 0, 952 -> 6 tiles of 2048 px
    assert tiles.grid(5000, 3000) == [
        (0, 0, 2048, 2048), (1792, 0, 3840, 2048), (2952, 0, 5000, 2048),
        (0, 952, 2048, 3000), (1792, 952, 3840, 3000), (2952, 952, 5000, 3000),
    ]  # fmt: skip
    assert counts(5000, 3000, tiled=False) == {"door": 1, "window": 1}  # letterboxed whole
    # a door in each tile's middle; the right-edge window is the neighbour's in the first two
    # columns (an inner edge), and only the last column's touches the page's own edge
    assert counts(5000, 3000, tiled=True) == {"door": 6, "window": 2}


def test_a_page_up_to_4000_px_is_read_whole_with_tiles_on() -> None:
    whole = {"door": 1, "window": 1}
    assert counts(4000, 300, tiled=True) == counts(4000, 300, tiled=False) == whole


def test_tiles_cover_the_page_and_overlap() -> None:
    assert tiles.starts(2048) == [0] and tiles.starts(1000) == [0]
    assert tiles.starts(4100) == [0, 1792, 2052]  # the last tile ends at the page edge
    assert not tiles.tiled(4000, 4000) and tiles.tiled(4001, 10)


def test_overlapping_finds_of_one_class_or_group_merge_to_the_best() -> None:
    a = tiles.Found("door", 0.9, (0, 0, 10, 10))
    b = tiles.Found("door_none", 0.8, (1, 0, 11, 10))  # IoU 0.82 with a, same door group
    c = tiles.Found("window", 0.7, (0, 0, 10, 10))  # another class: kept
    d = tiles.Found("door", 0.6, (20, 20, 30, 30))  # elsewhere: kept
    assert tiles.merge([b, d, c, a], groups=[("door", "door_none")]) == [a, c, d]
    assert tiles.merge([a, b]) == [a, b]  # without the group the two kinds don't compete
