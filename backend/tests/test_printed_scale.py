"""RASTER_PRINTED_SCALE: a raster sheet's printed scale (a bar, or a ratio at a resolution the file
states) replaces the scale estimated from its doors, which is kept as the other value of a
`scale` conflict, and printed counts ("SECOND FLOOR = 48 DORMS") stand against the counts read
off the drawing without replacing them. A fake reader stands in for the Carbon call. Synthetic."""

import io
from pathlib import Path

import pytest
from PIL import Image

from app.adapters.printed_scale import PrintedScale, stated_dpi
from app.adapters.raster_scale import PriorScale
from app.core.drawing.model import Drawing, Element, Page, Room, Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.printed import (
    PrintedFact,
    PrintedSheet,
    ScaleBar,
    bar_m_per_px,
    printed_scale,
    ratio_of,
    trusted_dpi,
)
from app.core.pipeline.raster_scale import DOOR_M
from app.core.pipeline.rules import apply_rules
from app.core.pipeline.second_count import measured, second_count
from app.core.pipeline.takeoff import take_off
from app.settings import Settings

PAGE = Page(page=1, width=2000, height=1000, unit="px")
FILE = DrawingFile(path="plan.png", size=1, sha256="0" * 64, kind="png")
SHEET = Sheet(file=FILE, pages=(PAGE,))
# A 5 m bar 250 px long: 0.02 m/px
BAR = ScaleBar(page=1, start=(0.1, 0.9), end=(0.225, 0.9), length_m=5.0, text="0 1 2 5 m")


@pytest.mark.parametrize(
    ("text", "ratio"),
    [
        ("1:200", 200.0),
        ("Scale 1 : 50 @ A1", 50.0),
        ("1:100 (A3)", 100.0),
        ('1/4" = 1\'-0"', 48.0),
        ("1/8 in = 1 ft", 96.0),
        ("1\" = 40'", 480.0),
        ("3/16\u201d = 1\u2019-0\u201d", 64.0),  # typographic quotes, as printed sheets have them
        ("bar", None),
        ("NTS", None),
        (None, None),
        ("Rev 1:0", None),  # 1:0 is no scale
    ],
)
def test_a_printed_ratio_is_read_in_metric_and_imperial(
    text: str | None, ratio: float | None
) -> None:
    assert ratio_of(text) == ratio


def test_only_a_resolution_a_file_states_on_purpose_is_trusted() -> None:
    assert trusted_dpi((150.0124, 150.0124)) == pytest.approx(150.0124)
    assert trusted_dpi((300.0, 300.0)) == 300.0
    for untrusted in ((96.012, 96.012), (72.0, 72.0), (300.0, 150.0), (50.0, 50.0), None):
        assert trusted_dpi(untrusted) is None, untrusted


def test_a_scale_bar_gives_metres_per_pixel_and_a_short_one_none() -> None:
    assert bar_m_per_px(BAR, [PAGE]) == pytest.approx(0.02)
    stub = BAR.model_copy(update={"end": (0.105, 0.9)})  # 10 px
    assert bar_m_per_px(stub, [PAGE]) is None
    assert bar_m_per_px(BAR.model_copy(update={"page": 2}), [PAGE]) is None


def test_a_bar_wins_over_a_ratio_and_a_ratio_needs_a_trusted_resolution() -> None:
    both = PrintedSheet(printed_scale="1:100", bars=(BAR,))
    scale = printed_scale(both, [PAGE], dpi=150.0)
    assert scale is not None and scale.status == "scaled"
    assert scale.m_per_unit == pytest.approx(0.02)  # the bar, not 1:100 at 150 dpi
    assert scale.evidence == ("scale_bar", "scale_text") and scale.text == "1:100"
    ratio = printed_scale(PrintedSheet(printed_scale="1:100"), [PAGE], dpi=150.0)
    assert ratio is not None and ratio.m_per_unit == pytest.approx(100 * 0.0254 / 150)
    assert ratio.evidence == ("scale_text",)
    assert printed_scale(PrintedSheet(printed_scale="1:100"), [PAGE], dpi=None) is None
    assert printed_scale(PrintedSheet(printed_scale="bar"), [PAGE], dpi=150.0) is None


def doors(side_px: float, n: int) -> tuple[Element, ...]:
    """`n` sure doors whose long side is `side_px` on PAGE."""
    w = side_px / PAGE.width
    return tuple(
        Element.model_validate(
            {"id": f"d{i}", "class": "door", "page": 1, "box": (0.1 * i, 0.1, 0.1 * i + w, 0.11),
             "attrs": {"score": 0.9}}
        )
        for i in range(n)
    )  # fmt: skip


SQUARE = ((0.1, 0.1), (0.2, 0.1), (0.2, 0.3), (0.1, 0.3))  # 200 x 200 px


class Fixed:
    """An inner raster reader with a fixed reading: `n` doors of `side_px`, one outlined room."""

    def __init__(self, side_px: float, n: int = 1, bedrooms: int = 1) -> None:
        rooms = [
            Room(id=f"r{i}", type="bedroom", page=1, box=(0.1, 0.1, 0.2, 0.3), polygon=SQUARE)
            for i in range(bedrooms)
        ]
        self.found = Extracted(
            method="detector",
            scale=Scale(status="no_scale"),
            elements=doors(side_px, n),
            rooms=tuple(rooms),
        )

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return self.found


class Reader:
    """Stands in for the Carbon reader: a fixed printed sheet, and how often it was asked."""

    def __init__(self, printed: PrintedSheet) -> None:
        self.printed = printed
        self.calls = 0

    def read(self, source: DrawingFile, sheet: Sheet) -> PrintedSheet:
        self.calls += 1
        return self.printed


class Files:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self, path: str) -> bytes:
        return self.data


def png(dpi: float | None) -> bytes:
    out = io.BytesIO()
    image = Image.new("L", (20, 10), 255)
    image.save(out, "PNG", **({} if dpi is None else {"dpi": (dpi, dpi)}))
    return out.getvalue()


def read(inner: Fixed, printed: PrintedSheet, dpi: float | None = None) -> Extracted:
    """The sheet through the door estimate, then the printed scale, as composition wires them."""
    wrapped = PrintedScale(PriorScale(inner), Reader(printed), Files(png(dpi)))
    return wrapped.extract(FILE, SHEET)


def test_the_printed_bar_replaces_the_door_estimate_and_measures_the_rooms_again() -> None:
    # the UK school sheet's case: one door read 20x too large, so the estimate is 20x off
    found = read(
        Fixed(side_px=DOOR_M / 0.02 * 20), PrintedSheet(printed_scale="1:200", bars=(BAR,))
    )
    assert found.scale.status == "scaled" and found.scale.m_per_unit == pytest.approx(0.02)
    assert found.scale.source == "printed scale bar (one bar)"
    (room,) = found.rooms
    assert room.area_m2 == pytest.approx(200 * 200 * 0.02**2)  # 16 m², not 0.04
    assert (room.area_status, room.area_source) == ("estimated", "geometry_x_scale")
    (entry,) = [c for c in second_count(measured(found), found.printed) if c.quantity == "scale"]
    assert entry.status == "conflict"
    assert [v.method for v in entry.values] == ["detector", "scale_bar"]
    assert entry.values[0].value == pytest.approx(0.02 / 20)  # the estimate is kept, shown
    assert entry.resolution is not None and entry.resolution.value == pytest.approx(0.02)
    assert "printed scale bar over the scale estimated from the doors" in entry.resolution.rule


def test_a_printed_scale_within_ten_percent_of_the_estimate_agrees() -> None:
    found = read(Fixed(side_px=DOOR_M / 0.0215, n=5), PrintedSheet(bars=(BAR,)))  # 7.5% apart
    (entry,) = [c for c in second_count(measured(found), found.printed) if c.quantity == "scale"]
    assert entry.status == "agree" and entry.tolerance == 0.10


def test_a_ratio_is_used_only_at_a_resolution_the_file_states(tmp_path: Path) -> None:
    printed = PrintedSheet(printed_scale="1:100")
    stated = read(Fixed(side_px=40.0), printed, dpi=150.0)
    assert stated.scale.m_per_unit == pytest.approx(
        100 * 0.0254 / 150, rel=1e-3
    )  # PNG keeps px per metre
    assert (
        stated.scale.source is not None
        and "printed scale 1:100 at the image" in stated.scale.source
    )
    default = read(Fixed(side_px=40.0), printed, dpi=96.0)  # a software default: the estimate
    assert default.scale.status == "estimated"
    assert any("1:100: read, not used" in note for note in default.notes)
    assert stated_dpi(b"not an image") is None and stated_dpi(png(None)) is None


def test_a_sheet_with_no_estimate_takes_the_printed_scale_with_no_conflict() -> None:
    found = read(Fixed(side_px=40.0, n=0), PrintedSheet(bars=(BAR,)))  # no door: no estimate
    assert found.scale.status == "scaled"
    assert [m for m in found.printed if m.quantity == "scale"] == []


def test_a_scale_the_reader_measured_itself_is_kept() -> None:
    inner = Fixed(side_px=40.0)
    inner.found = inner.found.model_copy(
        update={"scale": Scale(status="scaled", m_per_unit=0.05, evidence=("scale_bar",))}
    )
    found = read(inner, PrintedSheet(bars=(BAR,)))
    assert found.scale.m_per_unit == 0.05


DORMS = PrintedFact(text="SECOND FLOOR = 48 DORMS", subject="room:bedroom", value=48, unit="count",
                    box=(0.6, 0.9, 0.8, 0.95))  # fmt: skip


def drawing_of(found: Extracted) -> Drawing:
    return Drawing(
        file=FILE.path,
        pages=SHEET.pages,
        scale=found.scale,
        elements=found.elements,
        rooms=found.rooms,
        conflicts=tuple(second_count(measured(found), found.printed)),
        read=found.read,
    )


def test_a_printed_count_stands_against_the_counted_one_and_never_replaces_it() -> None:
    found = read(Fixed(side_px=40.0, bedrooms=80), PrintedSheet(printed_facts=(DORMS,)))
    drawing = drawing_of(found)
    (entry,) = [c for c in drawing.conflicts or () if c.quantity == "room_count"]
    assert entry.subject.ref == "room:bedroom" and entry.status == "conflict"
    assert [(v.value, v.method) for v in entry.values] == [(80, "detector"), (48, "printed_total")]
    assert entry.resolution is None  # no rule decides: a person does
    assert entry.values[1].box == DORMS.box
    quantities = take_off(drawing, apply_rules(drawing.marks_by_quantity()))
    bedrooms = quantities["room:bedroom"]
    assert bedrooms.value == 80 and bedrooms.conflict is not None  # kept, and shown disputed
    assert [v.value for v in bedrooms.conflict.values] == [80, 48]
    assert "printed on the sheet: SECOND FLOOR = 48 DORMS" in found.notes


def test_a_printed_count_of_doors_and_of_all_rooms_is_checked_areas_are_not() -> None:
    facts = (
        PrintedFact(text="12 DOORS", subject="door", value=12, unit="count"),
        PrintedFact(text="3 ROOMS", subject="room", value=3, unit="count"),
        PrintedFact(text="TOTAL 120 m2", subject="floor_area", value=120, unit="m2"),
        PrintedFact(text="2.5 doors", subject="door", value=2.5, unit="count"),
    )
    found = read(Fixed(side_px=40.0, n=3, bedrooms=3), PrintedSheet(printed_facts=facts))
    entries = {(c.quantity, c.subject.ref): c for c in drawing_of(found).conflicts or ()}
    assert entries[("element_count", "door")].status == "conflict"  # 3 read, 12 printed
    assert entries[("room_count", None)].status == "agree"  # 3 and 3
    assert len(entries) == 2


def test_the_setting_is_off_by_default() -> None:
    assert Settings(_env_file=None).raster_printed_scale == "off"  # pyright: ignore[reportCallIssue]
