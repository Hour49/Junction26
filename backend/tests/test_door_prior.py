"""DOOR_PRIOR_UNITS: on a sheet whose printed text is imperial, the door estimate takes a 3'-0"
US leaf (IMPERIAL_DOOR_M) in place of the CubiCasa-fitted DOOR_M, and its rooms are measured again.
A metric sheet, a printed scale and Carbon's door estimate are left exactly as they were. The
reader is a fake standing in for the Carbon call; the strings are synthetic but shaped like the
sheets' own (T2's "1\" = 40'-0\"", USCG's typeset quarter inch, a SF area total)."""

from pathlib import Path

import pytest
from test_printed_scale import BAR, FILE, SHEET, SQUARE, Files, Fixed, Reader, png

from app.adapters.printed_scale import PrintedScale
from app.adapters.raster_scale import CARBON_READ, PriorScale
from app.composition import build_ingest
from app.core.drawing.model import Element, Room, Scale
from app.core.pipeline.door_prior import (
    IMPERIAL_DOOR_M,
    imperial_doors,
    is_imperial,
    read_only_by,
)
from app.core.pipeline.model import Extracted
from app.core.pipeline.printed import CARBON_DOORS_REFUSED, PrintedFact, PrintedSheet, ScaleBar
from app.core.pipeline.raster_scale import (
    AREA_REFUSED,
    CARBON_DOOR_M,
    CARBON_DOORS,
    DOOR_M,
    SPREAD_FEW,
)
from app.core.pipeline.second_count import measured, second_count
from app.settings import Settings

US = IMPERIAL_DOOR_M / DOOR_M  # how much larger the scale is on an imperial sheet


@pytest.mark.parametrize(
    "text",
    [
        '1/8" = 1\'-0"',
        '1" = 40\'-0"',  # T2's site scale
        'SIZE ¼"=1\'-0"',  # USCG Building 407, typeset
        "1/4 in = 1 ft",
        "BEDROOM 12'-6\" x 10'-0\"",  # a feet-inch dimension in a room label
        "12\u2019-6\u201d",  # typographic quotes
        "12\u2032 6\u2033",  # primes, no hyphen
        "SECOND FLOOR = 12,400 SF",
        "LOBBY 1,200 SQ. FT.",
        "320 sq ft",
        "TOTAL 2400 S.F.",
        "0 10 20 40 FEET",  # a scale bar's labels
        "0 5 10 ft",
    ],
)
def test_imperial_text_is_found(text: str) -> None:
    assert is_imperial([text])


@pytest.mark.parametrize(
    "text",
    [
        "1:100",
        "1:200 @ A1",
        "Rev 1:0",
        "12.5",
        "KH 9.7 m²",
        "SAUNA 3,5 m2",
        "4H+K",
        "2.40 m",
        "0 1 2 5 m",
        "BEDROOM",
        "SECOND FLOOR = 48 DORMS",  # a count says nothing about units
        "A-301",
        "6'",  # a lone prime: feet, or a stray mark
        "SF-1",  # a sheet or room code, no number before it
        "LOFT",
        "",
    ],
)
def test_metric_and_unitless_text_is_not_imperial(text: str) -> None:
    assert not is_imperial([text])


def test_no_text_is_not_imperial() -> None:
    assert not is_imperial([])
    assert not is_imperial([None, None])


IMPERIAL_RATIO = PrintedSheet(printed_scale='1/8" = 1\'-0"')  # a ratio, no dpi: not used
METRIC_RATIO = PrintedSheet(printed_scale="1:100")


def read(inner: Fixed, printed: PrintedSheet, on: bool, dpi: float | None = None) -> Extracted:
    wrapped = PrintedScale(PriorScale(inner), Reader(printed), Files(png(dpi)), door_units=on)
    return wrapped.extract(FILE, SHEET)


def without_steps(found: Extracted) -> dict[str, object]:
    return found.model_dump(exclude={"steps"})  # steps carry wall-clock times


def test_an_imperial_sheet_takes_a_us_door_and_measures_its_rooms_again() -> None:
    inner = Fixed(side_px=DOOR_M / 0.02)  # 0.02 m/px at DOOR_M
    found = read(inner, IMPERIAL_RATIO, on=True)
    assert found.scale.status == "estimated"
    assert found.scale.m_per_unit == pytest.approx(0.02 * US)
    assert found.scale.uncertainty == SPREAD_FEW  # one door: the band is the same
    assert found.scale.source is not None
    assert found.scale.source.startswith(f"a door is about {IMPERIAL_DOOR_M} m wide")
    assert "imperial" in found.scale.source
    (room,) = found.rooms
    assert room.area_m2 == pytest.approx(200 * 200 * (0.02 * US) ** 2, abs=0.01)
    assert room.area_source == "geometry_x_estimate"
    estimates = [n for n in found.notes if n.startswith("scale estimate:")]
    assert estimates == [f"scale estimate: {found.scale.source}"]  # the old note is replaced


def test_off_keeps_the_fitted_door() -> None:
    found = read(Fixed(side_px=DOOR_M / 0.02), IMPERIAL_RATIO, on=False)
    assert found.scale.m_per_unit == pytest.approx(0.02)
    assert found.scale.source is not None and str(DOOR_M) in found.scale.source


@pytest.mark.parametrize(
    "printed",
    [
        METRIC_RATIO,
        PrintedSheet(),
        PrintedSheet(
            printed_facts=(PrintedFact(text="48 DORMS", subject="room", value=48, unit="count"),)
        ),
    ],
)
def test_a_metric_sheet_is_byte_identical_on_and_off(printed: PrintedSheet) -> None:
    inner = Fixed(side_px=DOOR_M / 0.02, n=3)
    assert without_steps(read(inner, printed, on=True)) == without_steps(
        read(inner, printed, on=False)
    )


def test_a_printed_bar_still_wins_and_the_conflict_shows_the_us_estimate() -> None:
    bar = BAR.model_copy(update={"text": "0 4 8 16 FEET"})
    found = read(Fixed(side_px=DOOR_M / 0.02 * 1.5), PrintedSheet(bars=(bar,)), on=True)
    assert found.scale.status == "scaled" and found.scale.m_per_unit == pytest.approx(0.02)
    (entry,) = [c for c in second_count(measured(found), found.printed) if c.quantity == "scale"]
    assert entry.values[0].method == "detector"
    assert entry.values[0].value == pytest.approx(0.02 / 1.5 * US)


def test_a_room_refused_at_the_fitted_door_is_measured_again_at_the_us_door() -> None:
    inner = Fixed(side_px=DOOR_M / 0.02)
    # 30 x 37.5 px: 0.60 x 0.75 m (0.45 m², refused) at 0.02; 0.69 x 0.86 m (0.60 m²) at the US door
    closet = Room(id="c1", type="other", page=1, box=(0.5, 0.5, 0.515, 0.5375))
    inner.found = inner.found.model_copy(update={"rooms": (*inner.found.rooms, closet)})
    off = read(inner, IMPERIAL_RATIO, on=False)
    assert AREA_REFUSED in off.rooms[1].attrs
    on = read(inner, IMPERIAL_RATIO, on=True)
    assert AREA_REFUSED not in on.rooms[1].attrs and on.rooms[1].area_m2 is not None
    assert not [n for n in on.notes if n.startswith("room area: c1")]


def estimated(source: str) -> Extracted:
    room = Room(id="r1", type="bedroom", page=1, box=(0.1, 0.1, 0.2, 0.3), polygon=SQUARE)
    scale = Scale(status="estimated", m_per_unit=0.02, source=source, uncertainty=SPREAD_FEW)
    return Extracted(method="detector", scale=scale, rooms=(room,))


def test_carbon_doors_and_printed_scales_are_left_alone() -> None:
    sheet = PrintedSheet(printed_scale='1/4" = 1\'-0"')
    carbon = estimated(f"a door is about 1.069 m wide; median of 4 {CARBON_DOORS} (...)")
    assert imperial_doors(carbon, sheet, SHEET.pages) is carbon
    scaled = Extracted(method="detector", scale=Scale(status="scaled", m_per_unit=0.02))
    assert imperial_doors(scaled, sheet, SHEET.pages) is scaled
    none = Extracted(method="detector", scale=Scale(status="no_scale"))
    assert imperial_doors(none, sheet, SHEET.pages) is none


def test_the_sheet_text_includes_bars_facts_and_room_labels() -> None:
    detector = estimated(f"a door is about {DOOR_M} m wide; median of 1 detected doors")
    bar = ScaleBar(page=1, start=(0, 0), end=(0.1, 0), length_m=6.1, text="0 10 20 FEET")
    fact = PrintedFact(text="GROSS AREA 12,400 SF", subject="floor_area", value=1152, unit="m2")
    for printed in (PrintedSheet(bars=(bar,)), PrintedSheet(printed_facts=(fact,))):
        assert imperial_doors(detector, printed, SHEET.pages).scale.m_per_unit == pytest.approx(
            0.02 * US
        )
    labelled = detector.model_copy(
        update={"rooms": (detector.rooms[0].model_copy(update={"label": "BR 11'-4\" x 12'-0\""}),)}
    )
    assert imperial_doors(labelled, PrintedSheet(), SHEET.pages).scale.m_per_unit == pytest.approx(
        0.02 * US
    )
    assert imperial_doors(detector, METRIC_RATIO, SHEET.pages) is detector


def test_the_setting_is_off_by_default_and_named_only_when_on(tmp_path: Path) -> None:
    assert Settings(_env_file=None).door_prior_units == "off"  # pyright: ignore[reportCallIssue]

    def readers(**on: str) -> dict[str, str]:
        key = {"gemini_api_key": "unused"}
        settings = Settings(_env_file=None, **key, **on)  # pyright: ignore[reportCallIssue]
        service = build_ingest(settings, tmp_path / "projects", background=False)
        service.close()
        return service._names  # pyright: ignore[reportPrivateUsage]

    assert "door_prior_units" not in readers()
    assert readers(door_prior_units="on")["door_prior_units"] == "on"


CARBON = "carbon:0123456789ab"  # the Carbon reader's tag on what it reads


def carbon_doors(side_px: float, n: int) -> Fixed:
    """A composite whose doors are Carbon's (no detector score): `n` of `side_px`."""
    inner = Fixed(side_px=side_px, n=n)
    doors = tuple(e.model_copy(update={"attrs": {"reader": CARBON}}) for e in inner.found.elements)
    inner.found = inner.found.model_copy(update={"elements": doors})
    return inner


def boxes(inner: Fixed, on: bool) -> Extracted:
    return PriorScale(inner, CARBON if on else None).extract(FILE, SHEET)


def test_carbon_boxes_take_carbons_width_when_on() -> None:
    inner = carbon_doors(side_px=CARBON_DOOR_M / 0.02, n=3)  # 0.02 m/px at Carbon's width
    off = boxes(inner, on=False)
    assert off.scale.m_per_unit == pytest.approx(0.02 * DOOR_M / CARBON_DOOR_M)  # today: 26% low
    on = boxes(inner, on=True)
    assert on.scale.m_per_unit == pytest.approx(0.02)
    assert on.scale.source is not None and CARBON_DOORS in on.scale.source
    assert on.scale.source.endswith(f"({CARBON_READ})")
    assert on.scale.uncertainty == SPREAD_FEW
    (room,) = on.rooms
    assert room.area_m2 == pytest.approx(200 * 200 * 0.02**2, abs=0.01)
    assert on.notes[-1] == f"scale estimate: {on.scale.source}"
    assert on.steps[-1].did == f"scale estimated: {on.scale.source}"  # #651's step kept


def test_detector_doors_are_byte_identical_on_and_off() -> None:
    inner = Fixed(side_px=DOOR_M / 0.02, n=3)  # the detector's: a score, no Carbon tag
    on, off = boxes(inner, on=True), boxes(inner, on=False)
    assert without_steps(on) == without_steps(off)
    assert on.scale.m_per_unit == pytest.approx(0.02)


def test_mixed_doors_keep_the_detector_width() -> None:
    inner = carbon_doors(side_px=DOOR_M / 0.02, n=3)
    detector = Fixed(side_px=DOOR_M / 0.02, n=1).found.elements[0].model_copy(update={"id": "x"})
    inner.found = inner.found.model_copy(update={"elements": (*inner.found.elements, detector)})
    assert boxes(inner, on=True).scale.m_per_unit == pytest.approx(0.02)


@pytest.mark.parametrize(
    ("attrs", "only"),
    [
        ({"reader": CARBON}, True),
        ({"reader": "carbon:ffffffffffff"}, False),  # another Carbon reader's tag
        ({"score": 0.9}, False),
        ({"reader": CARBON, "score": 0.3}, False),  # not counted: below MIN_DOOR_SCORE
        # snapped onto a detector door (#310): the detector's opening box, not Carbon's
        ({"reader": CARBON, "box_from": "detector"}, False),
    ],
)
def test_read_only_by_looks_at_the_counted_doors(attrs: dict[str, object], only: bool) -> None:
    door = Element.model_validate(
        {"id": "d", "class": "door", "page": 1, "box": (0.1, 0.1, 0.12, 0.11), "attrs": attrs}
    )
    placeholder = Element.model_validate(  # an unlocated door added by a counter: not counted
        {"id": "p", "class": "door", "page": 1, "box": (0, 0, 1, 1), "attrs": {"located": False}}
    )
    assert read_only_by(CARBON, [door, placeholder], SHEET.pages) is only
    assert read_only_by(CARBON, [placeholder], SHEET.pages) is False


def test_the_unit_rule_leaves_a_carbon_box_estimate_alone() -> None:
    inner = carbon_doors(side_px=CARBON_DOOR_M / 0.02, n=3)
    fact = PrintedFact(text="GROSS AREA 12,400 SF", subject="floor_area", value=1152, unit="m2")
    reader, files = Reader(PrintedSheet(printed_facts=(fact,))), Files(png(None))
    wrapped = PrintedScale(PriorScale(inner, CARBON), reader, files, door_units=True)
    found = wrapped.extract(FILE, SHEET)
    assert found.scale.m_per_unit == pytest.approx(0.02)  # no x0.914/0.794 on Carbon's boxes


def test_with_boxes_on_an_unread_printed_scale_refuses_the_carbon_door_estimate() -> None:
    """On purpose: printed.py's CARBON_DOORS_REFUSED (jf03, #417) already refuses a Carbon-door
    scale on a sheet that prints a scale nobody could read; with boxes on that covers these too."""
    inner = carbon_doors(side_px=CARBON_DOOR_M / 0.02, n=3)
    wrapped = PrintedScale(PriorScale(inner, CARBON), Reader(IMPERIAL_RATIO), Files(png(None)))
    found = wrapped.extract(FILE, SHEET)
    assert found.scale.status == "no_scale"
    assert CARBON_DOORS_REFUSED in found.notes


def test_the_boxes_setting_is_off_by_default_and_named_only_when_on(tmp_path: Path) -> None:
    assert Settings(_env_file=None).door_prior_boxes == "off"  # pyright: ignore[reportCallIssue]
    key = {"gemini_api_key": "unused"}
    on = {"door_prior_boxes": "on"}
    settings = Settings(_env_file=None, **key, **on)  # pyright: ignore[reportCallIssue]
    service = build_ingest(settings, tmp_path / "projects", background=False)
    service.close()
    assert service._names["door_prior_boxes"] == "on"  # pyright: ignore[reportPrivateUsage]


def test_snapped_carbon_doors_keep_the_detector_width() -> None:
    """Review of #681: in the demo (detector + CARBON_READER=large) Carbon's doors on a big sheet
    are mostly snapped onto the detector's boxes; one snapped door among Carbon's own keeps DOOR_M
    for the whole sheet (no mixing of box kinds in one median)."""
    inner = carbon_doors(side_px=DOOR_M / 0.02, n=5)
    snapped = [
        e.model_copy(update={"attrs": {**e.attrs, "box_from": "detector"}})
        for e in inner.found.elements
    ]
    for doors in (snapped, [*inner.found.elements[:4], snapped[4]]):
        inner.found = inner.found.model_copy(update={"elements": tuple(doors)})
        on = boxes(inner, on=True)
        assert on.scale.m_per_unit == pytest.approx(0.02)
        assert on.scale.source is not None and CARBON_DOORS not in on.scale.source
        assert without_steps(on) == without_steps(boxes(inner, on=False))
