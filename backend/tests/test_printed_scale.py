"""RASTER_PRINTED_SCALE: a raster sheet's printed scale (a bar, or a ratio at a resolution the file
states) replaces the scale estimated from its doors, which is kept as the other value of a
`scale` conflict, and printed counts ("SECOND FLOOR = 48 DORMS") stand against the counts read
off the drawing without replacing them. A fake reader stands in for the Carbon call. Synthetic."""

import io
from pathlib import Path
from typing import Literal

import pytest
from PIL import Image
from test_answering import NoPrior

from app.adapters.printed_scale import PrintedScale, stated_dpi
from app.adapters.raster_scale import PriorScale
from app.composition import build_ingest
from app.core.answering.answer import answer_question
from app.core.answering.model import Answer, Query, Question, Unsupported
from app.core.drawing.model import Drawing, Element, MeasuredValue, Page, Room, Scale, Subject
from app.core.pipeline.ingest import ingest
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, Sheet
from app.core.pipeline.printed import (
    PrintedFact,
    PrintedSheet,
    ScaleBar,
    bar_m_per_px,
    fact_measurements,
    imperial_scales,
    printed_scale,
    ratio_of,
    trusted_dpi,
)
from app.core.pipeline.raster_scale import (
    BOX_RATIO,
    DOOR_M,
    LABEL_NOTE,
    LABEL_RANGE,
    label_area_checks,
)
from app.core.pipeline.rules import apply_rules
from app.core.pipeline.second_count import measured, second_count
from app.core.pipeline.takeoff import known_quantities, take_off
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
        ("1:1 000", 1000.0),  # Finnish: a space between the thousands
        ("1:2 000", 2000.0),
        ("1:1\u00a0000", 1000.0),  # a no-break space
        ("1:1,000", 1000.0),
        ("1:1.000", 1000.0),  # German
        ("1:2,5", 2.5),  # a decimal comma, not a thousands group
        ('1 1/2" = 1\'-0"', 8.0),  # a mixed number of inches
        ('1-1/2" = 1\'-0"', 8.0),
        ('1/8" = 1\'-6"', 144.0),  # feet and inches
        # a view, level or sheet number before a fraction is not whole inches
        ('LEVEL 2 1/4" = 1\'-0"', 48.0),
        ('A-301 1/8" = 1\'-0"', 96.0),
        ('FLOOR PLAN 1 1/8" = 1\'-0"', 96.0),
        ('6" = 1\'-0"', 2.0),  # half size
        ('12" = 1\'-0"', None),  # more than 6" of paper to the foot
        ('6" = 0\'-3"', None),  # a drawing larger than the building
    ],
)
def test_a_printed_ratio_is_read_in_metric_and_imperial(
    text: str | None, ratio: float | None
) -> None:
    assert ratio_of(text) == ratio


def test_imperial_scales_lists_each_scale_with_its_text() -> None:
    assert imperial_scales('PLAN 1/8" = 1\'-0"   DETAIL 1 1/2" = 1\' - 0"') == [
        (96.0, '1/8" = 1\'-0"'),
        (8.0, '1 1/2" = 1\' - 0"'),
    ]
    assert imperial_scales("1:100") == []
    assert imperial_scales('LEVEL 2 1/4" = 1\'-0"') == [(48.0, '1/4" = 1\'-0"')]


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


def test_a_ratio_on_a_page_in_points_is_metres_per_point_whatever_the_renders_resolution() -> None:
    """A scanned PDF's page is in points (r10, 2026-11-14: its ratio became metres per pixel of
    the 129 dpi render, so a 47.7 m wide sheet measured 26.6 m and its areas came out x0.31)."""
    paper = Page(page=1, width=39.1 * 72, height=24.5 * 72, unit="pt")
    quarter_inch = PrintedSheet(printed_scale='1/4" = 1\'-0"')
    for dpi in (129.286, 150.0):
        scale = printed_scale(quarter_inch, [paper], dpi=dpi)
        assert scale is not None and scale.m_per_unit is not None
        assert scale.m_per_unit == pytest.approx(48 * 0.0254 / 72)
        assert scale.m_per_unit * paper.width == pytest.approx(48 * 39.1 * 0.0254)
        assert scale.source == "printed scale 1/4\" = 1'-0\" on the page's paper size"
    assert printed_scale(quarter_inch, [paper], dpi=None) is None  # no trusted paper size


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
    # the doors read 1.5x too large, so the estimate is 1.5x off
    found = read(
        Fixed(side_px=DOOR_M / 0.02 * 1.5), PrintedSheet(printed_scale="1:200", bars=(BAR,))
    )
    assert found.scale.status == "scaled" and found.scale.m_per_unit == pytest.approx(0.02)
    assert found.scale.source == "printed scale bar (one bar)"
    (room,) = found.rooms
    assert room.area_m2 == pytest.approx(200 * 200 * 0.02**2)  # 16 m², measured again
    assert (room.area_status, room.area_source) == ("estimated", "geometry_x_scale")
    (entry,) = [c for c in second_count(measured(found), found.printed) if c.quantity == "scale"]
    assert entry.status == "conflict"
    assert [v.method for v in entry.values] == ["detector", "scale_bar"]
    assert entry.values[0].value == pytest.approx(0.02 / 1.5)  # the estimate is kept, shown
    assert entry.resolution is not None and entry.resolution.value == pytest.approx(0.02)
    assert "printed scale bar over the scale estimated from the doors" in entry.resolution.rule
    drawing = drawing_of(found)
    side = take_off(drawing, apply_rules(drawing.marks_by_quantity()))["length:room:bedroom"]
    assert side.value == pytest.approx(200 * 0.02)  # within 2x: a length at the bar is not flagged
    assert side.estimate is None


def test_a_printed_ratio_wins_over_the_door_estimate_too(tmp_path: Path) -> None:
    # 1:100 at 150 dpi is 0.0169 m/px; the doors say 1.5x that
    found = read(Fixed(side_px=DOOR_M / 0.0254), PrintedSheet(printed_scale="1:100"), dpi=150.0)
    assert found.scale.status == "scaled" and "scale_text" in found.scale.evidence
    (entry,) = [c for c in second_count(measured(found), found.printed) if c.quantity == "scale"]
    assert [v.method for v in entry.values] == ["detector", "scale_text"]
    assert entry.resolution is not None
    assert entry.resolution.value == pytest.approx(100 * 0.0254 / 150, rel=1e-3)
    assert "printed scale over the scale estimated from the doors" in entry.resolution.rule


def test_a_bar_more_than_twice_the_estimate_wins_and_flags_what_rests_on_it() -> None:
    # the UK school sheet's case: one door read 20x too large, so the estimate is 20x off
    found = read(
        Fixed(side_px=DOOR_M / 0.02 * 20), PrintedSheet(printed_scale="1:200", bars=(BAR,))
    )
    assert found.scale.status == "scaled" and found.scale.m_per_unit == pytest.approx(0.02)
    (room,) = found.rooms
    assert room.area_m2 == pytest.approx(200 * 200 * 0.02**2)  # measured at the bar
    assert any("1 px = 20 mm) is more than 2x" in note and "1 px = 1 mm" in note
               for note in found.notes)  # fmt: skip
    drawing = drawing_of(found)
    (entry,) = [c for c in drawing.conflicts or () if c.quantity == "scale"]
    assert entry.resolution is not None and entry.resolution.value == pytest.approx(0.02)
    quantities = take_off(drawing, apply_rules(drawing.marks_by_quantity()))
    flagged = (  # every area and length: an estimate, so never certified and Low (review/check.py)
        "measured at the printed scale bar (1 px = 20 mm), which is more than twice the scale "
        "estimated from the doors (1 px = 1 mm), so one of them is misread"
    )
    areas = [q for key, q in quantities.items() if q.unit in ("m2", "m")]
    assert areas and all(q.estimate is not None and flagged in q.estimate for q in areas)
    assert quantities["room:bedroom"].estimate is None  # a count does not rest on the scale


def test_a_ratio_more_than_twice_the_estimate_is_left_to_a_person() -> None:
    # 1:100 at 150 dpi is 0.0169 m/px; one door read 20x too large says 0.001
    inner = Fixed(side_px=DOOR_M / 0.001)
    estimate = PriorScale(inner).extract(FILE, SHEET)
    found = read(inner, PrintedSheet(printed_scale="1:100"), dpi=150.0)
    assert found.scale == estimate.scale  # the estimate stays the sheet's scale
    assert found.rooms == estimate.rooms  # and its areas
    assert any("more than 2x the scale estimated from the doors" in n for n in found.notes)
    (entry,) = [c for c in second_count(measured(found), found.printed) if c.quantity == "scale"]
    assert entry.status == "conflict"
    assert [v.method for v in entry.values] == ["detector", "scale_text"]
    assert entry.resolution is None  # no rule decides: a person does


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


def test_a_sheet_the_reader_found_not_to_scale_stays_so() -> None:
    inner = Fixed(side_px=40.0)
    inner.found = inner.found.model_copy(update={"scale": Scale(status="not_to_scale")})
    found = read(inner, PrintedSheet(bars=(BAR,)))
    assert found.scale.status == "not_to_scale" and found.scale.m_per_unit is None


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


def label_room(id_: str, box: tuple[float, float, float, float], printed: float) -> Room:
    """A room as the Gemini room reader gives it with an area printed in its label."""
    return Room(id=id_, type="other", label=f"{id_.upper()} {printed:g} m²", page=1, box=box,
                area_m2=printed, area_status="exact", area_source="printed")  # fmt: skip


class AreaOf:
    def __init__(self, name: str) -> None:
        self.name = name

    def parse(self, text: str) -> Query | Unsupported:
        return Query(measure="area", subject="room", name=self.name)


def test_label_area_fixes_s1_a_label_area_far_from_its_outline_is_left_to_a_person() -> None:
    """qa-c S1: "KH 97 m²" (its decimal comma lost) on a 3 x 3 m box at a printed scale came
    out 97.0 exact. More than LABEL_RANGE from the outline, both values stand and no rule
    decides; within it the label stands, and so does a label-sized box's."""
    inner = Fixed(side_px=DOOR_M / 0.02)  # the doors agree with the bar: 0.02 m/px
    kh = label_room("kh", (0.30, 0.10, 0.375, 0.25), 97.0)  # 150 x 150 px: 3 x 3 m
    mh = label_room("mh", (0.40, 0.10, 0.475, 0.25), 8.0)  # the same box, a plausible label
    lobby = label_room("lobby", (0.50, 0.10, 0.54, 0.115), 7.4)  # 0.3 m tall: boxes its label
    inner.found = inner.found.model_copy(update={"rooms": (*inner.found.rooms, kh, mh, lobby)})
    found = read(inner, PrintedSheet(printed_scale="1:200", bars=(BAR,)))

    outline = round(150 * 150 * 0.02**2 / BOX_RATIO, 2)
    assert [(m.subject.ref, m.value.value, m.value.method) for m in found.printed
            if m.quantity == "room_area"] == [("kh", 97.0, "printed_label"),
                                              ("kh", outline, "detector")]  # fmt: skip
    said = [note for note in found.notes if note.startswith(LABEL_NOTE)]
    assert said == [  # once: the door estimate's check is replaced by the printed scale's
        f"{LABEL_NOTE}kh prints 97 m², its outline at the sheet's scale is about 8.15 m² (more "
        f"than {LABEL_RANGE:g}x apart): left for a person"
    ]
    drawing = drawing_of(found)
    (entry,) = [c for c in drawing.conflicts or () if c.quantity == "room_area"]
    assert (entry.status, entry.resolution) == ("conflict", None)

    def ask(name: str) -> Answer:
        question = Question(id=1, file=FILE.path, text="How big is it?")
        quantities = known_quantities(drawing)
        return answer_question(question, quantities, AreaOf(name), iter(range(9)).__next__,
                               NoPrior())  # fmt: skip

    disputed = ask("kh 97 m²")
    assert disputed.abstain is True and "no rule decides" in (disputed.explanation or "")
    kept = ask("mh 8 m²")
    assert (kept.answer, kept.abstain, kept.estimate) == (8.0, None, None)
    # the level note: where the value was printed reaches the answer's explanation
    assert kept.explanation == "printed in the room's label"
    assert ask("lobby 7.4 m²").answer == 7.4


def test_label_area_fixes_no_scale_no_check() -> None:
    room = label_room("kh", (0.3, 0.1, 0.375, 0.25), 97.0)
    assert label_area_checks([room], Scale(status="no_scale"), [PAGE]) == ([], [])


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


class Around:
    """What `ingest` needs around the extractor: the PNG's bytes, its page, no sources, no second
    counter of its own, and the drawings it writes."""

    def __init__(self) -> None:
        self.drawings: list[Drawing] = []

    def read(self, path: str) -> bytes:
        return png(None)

    def sources(self, path: str) -> list[str]:
        return []

    def pages(self, file: DrawingFile) -> tuple[Page, ...]:
        return SHEET.pages

    def measure(self, source: DrawingFile, sheet: Sheet) -> list[Measurement]:
        return []

    def write(self, drawing: Drawing) -> None:
        self.drawings.append(drawing)


def test_ingest_checks_the_reading_against_what_the_sheet_prints() -> None:
    around = Around()
    printed = PrintedSheet(bars=(BAR,), printed_facts=(DORMS,))
    reader = PrintedScale(PriorScale(Fixed(side_px=DOOR_M / 0.02 * 1.5, bedrooms=80)),
                          Reader(printed), Files(png(None)))  # fmt: skip
    ingest([FILE.path], files=around, finder=around, pages=around,
           extractors={"raster": reader}, second_counter=around, sink=around)  # fmt: skip
    (drawing,) = around.drawings
    entries = {(c.quantity, c.subject.ref): c for c in drawing.conflicts or ()}
    scale = entries[("scale", None)]
    assert [v.method for v in scale.values] == ["detector", "scale_bar"]
    bedrooms = entries[("room_count", "room:bedroom")]
    assert [(v.value, v.method) for v in bedrooms.values] == [
        (80, "detector"),
        (48, "printed_total"),
    ]


def test_the_setting_is_part_of_the_ingest_reuse_key_only_when_on(tmp_path: Path) -> None:
    def readers(**on: str) -> dict[str, str]:
        key = {"gemini_api_key": "unused"}  # the Carbon client needs one; nothing is called
        settings = Settings(_env_file=None, **key, **on)  # pyright: ignore[reportCallIssue]
        service = build_ingest(settings, tmp_path / "projects", background=False)
        service.close()  # no upload: with the setting on, one would call the model
        return service._names  # pyright: ignore[reportPrivateUsage]

    assert "raster_printed_scale" not in readers()  # the default keeps the keys it had before
    assert readers(raster_printed_scale="carbon")["raster_printed_scale"] == "carbon"


def test_the_setting_is_off_by_default() -> None:
    assert Settings(_env_file=None).raster_printed_scale == "off"  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize(
    "text",
    ["4H+K", "3h+k+s", "2h+kt", "1h+kk", "5H+K+S+SAU", "4 h + k", "Asunto B 12, 3h+k+s 78 m²"],
)
def test_a_flat_type_is_never_a_room_count(text: str) -> None:
    """A Finnish flat type (4H+K: four rooms and a kitchen) names the flat, it does not count the
    rooms drawn (live project d8c0e57b1ac4: 4H+K against 18 rooms read)."""
    assert fact_measurements([PrintedFact(text=text, subject="room", value=4, unit="count")]) == []


def test_a_printed_room_count_that_is_no_flat_type_is_still_a_room_count() -> None:
    (found,) = fact_measurements(
        [PrintedFact(text="4 ROOMS", subject="room", value=4, unit="count")]
    )
    assert (found.quantity, found.value.value) == ("room_count", 4)


def counts(read: float, printed: float, door: bool = False) -> list[Measurement]:
    """A count read and one printed: of all rooms, or of doors."""
    quantity: Literal["room_count", "element_count"] = "element_count" if door else "room_count"
    subject = Subject(kind="class", ref="door") if door else Subject(kind="sheet", ref=None)
    return [
        Measurement(
            quantity=quantity,
            subject=subject,
            value=MeasuredValue(value=read, unit="count", method="plan_drawing"),
        ),
        Measurement(
            quantity=quantity,
            subject=subject,
            value=MeasuredValue(value=printed, unit="count", method="printed_total"),
        ),
    ]


def test_rooms_read_more_than_twice_the_printed_count_keep_the_reading_and_ask_no_person() -> None:
    """18 read, 4 printed: no rule decides, but a printed number that much smaller counts
    something else; the reading is kept and shown, with no card for a person."""
    read, printed = counts(18, 4)
    (entry,) = second_count([read], [printed])
    assert entry.status == "conflict"  # both values stay on the entry
    assert entry.resolution is not None and entry.resolution.value == 18
    assert "more than 2x the other count" in entry.resolution.rule


@pytest.mark.parametrize(
    ("read", "printed", "door"),
    [
        (0, 3, False),  # nothing read
        (6, 5, False),  # within 2x
        (80, 48, False),
        (4, 12, False),  # more printed than read: the reader may have missed rooms
        (3, 12, True),  # doors: the rule is for rooms only
        (18, 4, True),
    ],
)
def test_other_count_pairs_are_left_to_a_person(read: int, printed: int, door: bool) -> None:
    first, second = counts(read, printed, door)
    (entry,) = second_count([first], [second])
    assert entry.status == "conflict" and entry.resolution is None
