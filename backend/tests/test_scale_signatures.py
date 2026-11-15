"""SCALE_SIGNATURES: two scales whose quotient is a known print or scale slip (scale_signatures)."""

import itertools
import math

import pytest

from app.core.drawing.model import Page, Room, Scale
from app.core.pipeline.scale_signatures import FACTORS, TOLERANCE, label_pick, slip

BASE = 0.01  # m/px


@pytest.mark.parametrize("factor", FACTORS, ids=lambda f: f.name)
def test_every_factor_is_a_slip_both_ways(factor):
    for a, b in ((BASE * factor.value, BASE), (BASE, BASE * factor.value)):
        found = slip(a, b)
        assert found is not None and found.name == factor.name
        assert found.cause == factor.cause
    first, second = slip(BASE * factor.value, BASE), slip(BASE, BASE * factor.value)
    assert first is not None and first.larger == "first"
    assert second is not None and second.larger == "second"


@pytest.mark.parametrize(
    ("quotient", "name"),
    [
        (4 / 3 * 1.02, "4/3"),  # inside the tolerance
        (4 / 3 * 0.98, "4/3"),
        (math.sqrt(2) * 1.02, "√2"),
        (1.5 * 0.98, "3/2"),
        (2.0 * 1.02, "2"),
        (24 / 11 * 1.01, "24/11"),  # ARCH D fitted to 11x17: the closer of 24/11 and 36/17
        (36 / 17, "36/17"),
    ],
)
def test_near_a_factor_inside_the_tolerance(quotient, name):
    found = slip(BASE * quotient, BASE)
    assert found is not None and found.name == name


@pytest.mark.parametrize(
    "quotient",
    [
        1.0,
        1.05,
        1.15,
        4 / 3 * 1.03,
        4 / 3 * 0.97,
        math.sqrt(2) * 0.97,
        1.5 * 1.03,
        2.0 * 0.97,
        2.5,
        3.0,
    ],
)
def test_no_slip_outside_the_tolerance(quotient):
    assert slip(BASE * quotient, BASE) is None
    assert slip(BASE, BASE * quotient) is None


def test_no_slip_without_two_positive_scales():
    assert slip(0.0, BASE) is None
    assert slip(BASE, -1.0) is None


def test_windows_never_overlap_except_the_two_arch_d_fits():
    values = sorted(FACTORS, key=lambda f: f.value)
    for low, high in itertools.pairwise(values):
        if {low.name, high.name} == {"36/17", "24/11"}:
            continue  # one cause, either name is right
        assert high.value / low.value > (1 + TOLERANCE) ** 2


PAGE = Page(page=1, width=1000.0, height=1000.0, unit="px")


def _room(i: int, printed_m2: float, side_px: float = 200.0) -> Room:
    # a polygon room side_px square at the top left, offset per room
    x0, y0 = 0.001 * i, 0.001 * i
    s = side_px / 1000.0
    poly = ((x0, y0), (x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s))
    return Room(
        id=f"r{i}",
        type="other",
        page=1,
        box=(x0, y0, x0 + s, y0 + s),
        polygon=poly,
        area_m2=printed_m2,
        area_source="printed",
    )


def _scale(m: float) -> Scale:
    return Scale(status="scaled", m_per_unit=m)


def test_label_pick_names_the_candidate_the_printed_areas_agree_with():
    # 200 px squares; at 0.01 m/px each is 4 m², at 0.0075 m/px 2.25 m²
    rooms = [_room(i, 4.1) for i in range(3)]
    assert label_pick(rooms, [PAGE], _scale(0.01), _scale(0.0075)) == "first"
    assert label_pick(rooms, [PAGE], _scale(0.0075), _scale(0.01)) == "second"


def test_label_pick_none_with_too_few_rooms_or_no_clear_winner():
    two = [_room(i, 4.0) for i in range(2)]
    assert label_pick(two, [PAGE], _scale(0.01), _scale(0.0075)) is None
    between = [_room(i, 3.1) for i in range(3)]  # 3.1 m²: neither 4 nor 2.25 within 10%
    assert label_pick(between, [PAGE], _scale(0.01), _scale(0.0075)) is None
