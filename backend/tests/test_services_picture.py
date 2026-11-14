"""SV-29, SV-30 (backend part): one storey drawn from the stored model, and a services change
drawn over it, on the two-room fixture. Frame (-2, -2, 12, 6) m at 1600 px: 114.3 px per m."""

import io
import time

import pytest
from PIL import Image

from app.adapters.services_picture import (
    ADDED,
    MOVED,
    REMOVED,
    ROOM,
    before_after_png,
    change_png,
    legend,
    storey_png,
)
from app.core.errors import NotFoundError
from app.core.services.edit import Moved, Patch, RunChange, ServicesChange
from app.core.services.stored import fraction
from tests.services_fixtures import RETURN, SUPPLY, two_rooms

WIDTH = 1600


def picture(png: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(png))
    assert image.format == "PNG"
    return image.convert("RGB")


def at(image: Image.Image, x: float, y: float) -> tuple[int, int, int]:
    """The pixel at a model point (metres) of the storey's frame."""
    fx, fy = fraction(two_rooms().storeys[0], (x, y))
    return image.getpixel((round(fx * image.width), round(fy * image.height)))  # type: ignore[return-value]


def test_sv29_a_storey_is_drawn_to_its_frame_rooms_grey_runs_per_system() -> None:
    model = two_rooms()
    image = picture(storey_png(model, "L1"))
    assert image.size == (WIDTH, round(WIDTH * 8 / 14))  # SV-6: the frame fixes the fractions
    colours = dict(legend(model, "L1"))
    assert colours[SUPPLY] != colours[RETURN]
    assert at(image, 4.0, 0.25) == colours[SUPPLY]  # the supply main
    assert at(image, 4.0, 0.31) == colours[RETURN]
    assert at(image, 1.0, 3.5) == ROOM  # inside a room
    assert [name for name, _ in legend(model, "L1")] == [
        RETURN,  # by name
        SUPPLY,
        "terminal",
        "equipment",
    ]


def test_sv29_an_unknown_storey_is_not_found() -> None:
    with pytest.raises(NotFoundError):
        storey_png(two_rooms(), "L9")


def test_sv29_a_storey_draws_fast() -> None:
    model = two_rooms()
    start = time.perf_counter()
    storey_png(model, "L1")
    assert time.perf_counter() - start < 0.2


def change() -> ServicesChange:
    storey = two_rooms().storeys[0]

    def line(*points: tuple[float, float]) -> tuple[tuple[float, float], ...]:
        return tuple(fraction(storey, p) for p in points)

    return ServicesChange(
        op="move_terminal",
        storey="L1",
        moved=(
            Moved.model_validate(
                {
                    "id": "E3",
                    "label": "Radiator",
                    "from": line((7.5, 0.1))[0],
                    "to": line((9.8, 2.0))[0],
                }
            ),
        ),
        removed=(RunChange(id="E11", polyline=line((6.0, 2.0), (9.0, 2.0)), label="Pipe DN15"),),
        added=(RunChange(id="N1", polyline=line((6.0, 3.0), (9.0, 3.0)), label="Pipe DN15"),),
        patch=Patch(),
    )


def test_sv30_removed_runs_dashed_grey_added_thick_moved_with_an_arrow() -> None:
    image = picture(change_png(two_rooms(), change()))
    dashes = [at(image, 6.0 + i * 0.02, 2.0) == REMOVED for i in range(150)]
    assert 0.3 < sum(dashes) / len(dashes) < 0.9  # dashed: some drawn, some gaps
    assert at(image, 7.5, 3.0) == ADDED and at(image, 7.5, 3.03) == ADDED  # thick
    assert at(image, 8.65, 1.05) == MOVED  # on the arrow, halfway
    assert at(image, 7.5, 0.1) != MOVED  # the old place is a hollow mark


def test_sv30_before_and_after_side_by_side() -> None:
    model = two_rooms()
    image = picture(before_after_png(model, change()))
    assert image.width >= 2 * WIDTH and image.height > round(WIDTH * 8 / 14)


def test_sv29_many_systems_are_coloured_by_system_type_so_the_legend_stays_short() -> None:
    model = two_rooms()
    many = tuple(
        e.model_copy(update={"systems": (f"{e.system_type} {i}",)}) if e.system_type else e
        for i, e in enumerate(model.elements)
    )
    names = [name for name, _ in legend(model.model_copy(update={"elements": many}), "L1")]
    assert names == ["Hydronic Return", "Hydronic Supply", "terminal", "equipment"]


def test_sv30_a_removed_element_without_a_run_is_a_grey_cross() -> None:
    storey = two_rooms().storeys[0]
    gone = RunChange(id="E3", polyline=(fraction(storey, (7.5, 2.0)),), label="Radiator")
    image = picture(
        change_png(
            two_rooms(),
            ServicesChange(op="remove_element", storey="L1", removed=(gone,), patch=Patch()),
        )
    )
    assert at(image, 7.5, 2.0) == REMOVED


def test_sv29_the_legend_goes_in_the_emptiest_corner_not_over_the_plan() -> None:
    model = two_rooms()
    storey = model.storeys[0].model_copy(update={"frame_m": (1.0, -0.5, 12.0, 3.5)})
    image = picture(storey_png(model.model_copy(update={"storeys": (storey,)}), "L1"))
    assert image.getpixel((12, 12)) == ROOM  # the top left is a room: the legend went elsewhere
