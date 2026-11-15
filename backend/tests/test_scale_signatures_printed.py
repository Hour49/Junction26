"""SCALE_SIGNATURES in with_printed: a bar against its ratio, a ratio against the doors, and no
change at all without a signature. Synthetic sheets, the helpers of test_printed_scale."""

import pytest
from test_printed_scale import BAR, FILE, SHEET, SQUARE, Files, Fixed, Reader, drawing_of, png

from app.adapters.printed_scale import PrintedScale
from app.adapters.raster_scale import PriorScale
from app.core.drawing.model import Room
from app.core.pipeline.model import Extracted
from app.core.pipeline.printed import PrintedSheet
from app.core.pipeline.raster_scale import DOOR_M
from app.core.pipeline.rules import apply_rules
from app.core.pipeline.scale_signatures import SCALE_SLIP, Signatures
from app.core.pipeline.second_count import measured, second_count
from app.core.pipeline.takeoff import take_off

RATIO = 100 * 0.0254 / 150  # 1:100 at 150 dpi: 0.01693 m/px


def read(
    inner: Fixed, printed: PrintedSheet, dpi: float | None, on: bool, mode: Signatures = "on"
) -> Extracted:
    signatures: Signatures = mode if on else "off"
    wrapped = PrintedScale(
        PriorScale(inner), Reader(printed), Files(png(dpi)), signatures=signatures
    )
    return wrapped.extract(FILE, SHEET)


def scale_values(found: Extracted) -> dict[str, float]:
    entries = [c for c in second_count(measured(found), found.printed) if c.quantity == "scale"]
    return {v.method: v.value for entry in entries for v in entry.values}


def areas_held(found: Extracted) -> list[str]:
    drawing = drawing_of(found).model_copy(update={"notes": found.notes})  # as ingest.py has it
    quantities = take_off(drawing, apply_rules(drawing.marks_by_quantity()))
    return [q.estimate or "" for q in quantities.values() if q.unit in ("m2", "m")]


def scale_entry(found: Extracted):
    (entry,) = [c for c in second_count(measured(found), found.printed) if c.quantity == "scale"]
    return entry


@pytest.mark.parametrize("mode", ["bar", "on"])
def test_a_bar_and_its_ratio_four_thirds_apart_keep_the_bar_and_name_the_cause(mode) -> None:
    # the bar says 0.02 m/px; 1:200 at 190.5 dpi says 0.02667, 4/3 of it
    inner, printed = (
        Fixed(side_px=DOOR_M / 0.02, n=5),
        PrintedSheet(printed_scale="1:200", bars=(BAR,)),
    )
    found = read(inner, printed, dpi=190.5, on=True, mode=mode)
    assert found.scale.m_per_unit == pytest.approx(0.02) and "scale_bar" in found.scale.evidence
    (said,) = [n for n in found.notes if "is 4/3 times the measured scale bar" in n]
    assert "neighbouring scales" in said and "the bar is used" in said
    assert scale_values(found)["scale_text"] == pytest.approx(0.02 * 4 / 3, rel=1e-3)
    entry = scale_entry(found)  # shown, and decided for the bar: no person is asked
    assert entry.resolution is not None and entry.resolution.value == pytest.approx(0.02)
    assert not any(SCALE_SLIP in n for n in found.notes)
    assert all("misread" not in held for held in areas_held(found))  # the bar is not doubted
    off = read(inner, printed, dpi=190.5, on=False)
    assert "scale_text" not in scale_values(off)
    assert off.scale == found.scale and off.rooms == found.rooms  # same numbers either way


def test_a_bar_alone_gets_its_ratio_as_a_second_scale_value() -> None:
    inner = Fixed(side_px=DOOR_M / 0.02)
    inner.found = inner.found.model_copy(update={"elements": ()})  # no doors: no estimate
    found = read(inner, PrintedSheet(printed_scale="1:200", bars=(BAR,)), dpi=190.5, on=True)
    values = scale_values(found)
    assert values["scale_bar"] == pytest.approx(0.02)
    assert values["scale_text"] == pytest.approx(0.02 * 4 / 3, rel=1e-3)
    entry = scale_entry(found)
    assert entry.resolution is not None and entry.resolution.value == pytest.approx(0.02)


def test_a_ratio_and_the_doors_a_slip_apart_hold_every_area() -> None:
    inner = Fixed(side_px=DOOR_M / (RATIO * 4 / 3), n=5)
    found = read(inner, PrintedSheet(printed_scale="1:100"), dpi=150.0, on=True)
    assert found.scale.m_per_unit == pytest.approx(RATIO, rel=1e-3)  # today's choice stays
    (said,) = [n for n in found.notes if n.startswith(SCALE_SLIP)]
    assert "is 3/4 of the scale estimated from the doors" in said
    held = areas_held(found)
    assert held and all(said.removeprefix(SCALE_SLIP) in h for h in held)
    off = read(inner, PrintedSheet(printed_scale="1:100"), dpi=150.0, on=False)
    assert all("misread" not in h for h in areas_held(off))  # today: answered on the ratio
    bar = read(inner, PrintedSheet(printed_scale="1:100"), dpi=150.0, on=True, mode="bar")
    timeless = {"steps"}
    assert bar.model_dump(exclude=timeless) == off.model_dump(exclude=timeless)  # "bar": not run


def labelled(printed_m2: float) -> tuple[Room, ...]:
    """Three rooms on SQUARE (200 x 200 px) with an area printed in their labels."""
    return tuple(
        Room(id=f"l{i}", type="other", page=1, box=(0.1, 0.1, 0.2, 0.3), polygon=SQUARE,
             area_m2=printed_m2, area_status="exact", area_source="printed")
        for i in range(3)
    )  # fmt: skip


@pytest.mark.parametrize(
    ("printed_m2", "winner"),
    [(40000 * RATIO**2, "ratio"), (40000 * (RATIO * 4 / 3) ** 2, "doors")],
)
def test_the_rooms_printed_areas_pick_the_scale_they_agree_with(printed_m2, winner) -> None:
    inner = Fixed(side_px=DOOR_M / (RATIO * 4 / 3), n=5)
    inner.found = inner.found.model_copy(update={"rooms": labelled(printed_m2)})
    estimate = PriorScale(inner).extract(FILE, SHEET)
    found = read(inner, PrintedSheet(printed_scale="1:100"), dpi=150.0, on=True)
    assert not any(n.startswith(SCALE_SLIP) for n in found.notes)
    if winner == "ratio":
        assert found.scale.m_per_unit == pytest.approx(RATIO, rel=1e-3)
        assert any("agree with the ratio" in n for n in found.notes)
    else:
        assert found.scale == estimate.scale
        assert any("agree with the doors: the ratio is not used" in n for n in found.notes)
        assert set(scale_values(found)) == {"detector", "scale_text"}  # both stay shown


@pytest.mark.parametrize(
    ("side_px", "printed", "dpi"),
    [
        (DOOR_M / (RATIO * 1.15), PrintedSheet(printed_scale="1:100"), 150.0),  # no slip
        (DOOR_M / (RATIO * 2.6), PrintedSheet(printed_scale="1:100"), 150.0),  # over 2x
        (DOOR_M / 0.02, PrintedSheet(printed_scale="1:200", bars=(BAR,)), 254.0),  # agree
        (DOOR_M / 0.0266, PrintedSheet(bars=(BAR,)), None),  # a bar alone, 4/3 off the doors
        (DOOR_M / 0.02, PrintedSheet(printed_scale="1:200", bars=(BAR,)), None),  # no dpi
    ],
)
def test_without_a_signature_the_setting_changes_nothing(side_px, printed, dpi) -> None:
    inner = Fixed(side_px=side_px, n=5)
    on, off = (read(inner, printed, dpi, on=flag) for flag in (True, False))
    timeless = {"steps"}  # each read's step carries its own clock
    assert on.model_dump(exclude=timeless) == off.model_dump(exclude=timeless)
