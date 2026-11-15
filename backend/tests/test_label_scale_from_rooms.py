"""LABEL_SCALE=on: the areas printed in room labels give a raster sheet's scale (photos the
rectifier straightened, scans with only the door estimate). Synthetic rooms on a 1000 x 1000 px
page at 1 cm a pixel."""

import math

import pytest

from app.adapters.raster_scale.label import LabelScale
from app.core.drawing.model import Drawing, Page, Room, Scale
from app.core.pipeline.label_scale import (
    LABEL_SOURCE,
    MIN_BAND,
    MIN_ROOMS,
    label_scale,
    with_label_scale,
)
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.raster_scale import BOX_RATIO, LABEL_NOTE
from app.core.pipeline.takeoff import label_disputed

PAGE = Page(page=1, width=1000, height=1000, unit="px")
M = 0.01  # m per px


def room(i: int, side: float, label_m2: float | None, polygon: bool = True) -> Room:
    """A square room of `side` (page fraction) at column i, its label printing `label_m2`."""
    x0, y0 = 0.05 + 0.2 * (i % 4), 0.05 + 0.2 * (i // 4)
    box = (x0, y0, x0 + side, y0 + side)
    poly = ((x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side))
    printed = {"area_m2": label_m2, "area_status": "exact", "area_source": "printed"}
    return Room(
        id=f"r{i}", type="bedroom", page=1, box=box, polygon=poly if polygon else None,
        **(printed if label_m2 is not None else {}),
    )  # fmt: skip


def exact(side: float) -> float:
    """The area a room of `side` prints at M."""
    return (side * 1000 * M) ** 2


@pytest.mark.parametrize(
    ("rooms", "want"),
    [
        # three exact labels: the scale itself
        ([room(i, 0.15, exact(0.15)) for i in range(3)], M),
        # two are too few (MIN_ROOMS)
        ([room(i, 0.15, exact(0.15)) for i in range(2)], None),
        # a lost decimal comma (10x the area) is dropped, the other three give the scale
        ([*(room(i, 0.15, exact(0.15)) for i in range(3)), room(3, 0.15, 10 * exact(0.15))], M),
        # the comma slip leaves two: too few
        ([*(room(i, 0.15, exact(0.15)) for i in range(2)), room(3, 0.15, 10 * exact(0.15))], None),
        # rooms without a printed area say nothing
        ([*(room(i, 0.15, None) for i in range(5)), room(5, 0.1, exact(0.1))], None),
        # box rooms: the box is BOX_RATIO larger than the outline
        ([room(i, 0.15, exact(0.15) / BOX_RATIO, polygon=False) for i in range(3)], M),
        # a label-sized box (under MIN_BOX_M2 at the scale) boxes the label: not counted
        (
            [
                *(room(i, 0.15, exact(0.15)) for i in range(2)),
                room(2, 0.005, exact(0.005) / BOX_RATIO, polygon=False),
            ],
            None,
        ),
    ],
)
def test_label_scale_is_the_median_of_the_rooms_scales(rooms: list[Room], want: float | None):
    scale = label_scale(rooms, [PAGE])
    if want is None:
        assert scale is None
        return
    assert scale is not None and scale.m_per_unit is not None
    assert scale.m_per_unit == pytest.approx(want)
    assert scale.status == "estimated"
    assert scale.source is not None and scale.source.startswith(LABEL_SOURCE)
    assert scale.uncertainty == pytest.approx(MIN_BAND)  # exact labels: no spread, the floor


def test_the_band_follows_the_rooms_spread():
    # five rooms, labels 0.7x..1.3x their outline area: a spread above the floor
    factors = (0.7, 0.85, 1.0, 1.15, 1.3)
    rooms = [room(i, 0.15, f * exact(0.15)) for i, f in enumerate(factors)]
    scale = label_scale(rooms, [PAGE])
    assert scale is not None and scale.uncertainty is not None and scale.m_per_unit is not None
    assert scale.m_per_unit == pytest.approx(M)
    spread = 1.4826 * 0.5 * math.log(1.15)  # the MAD of log m_i: half the log of the area factor
    assert scale.uncertainty == pytest.approx(max(MIN_BAND, math.expm1(1.2533 * spread / 5**0.5)))
    assert "5 room labels" in (scale.source or "")


def found(scale: Scale, rooms: list[Room]) -> Extracted:
    return Extracted(method="detector", scale=scale, rooms=tuple(rooms))


LABELLED = [*(room(i, 0.15, exact(0.15)) for i in range(3)), room(3, 0.1, None)]


def door(m_per_unit: float) -> Scale:
    source = "a door is about 0.794 m wide; median of 4 detected doors"
    return Scale(status="estimated", m_per_unit=m_per_unit, source=source, uncertainty=0.158)


def test_a_sheet_without_a_scale_takes_the_label_scale_and_its_rooms_their_areas():
    out = with_label_scale(found(Scale(status="no_scale"), LABELLED), [PAGE])
    assert out.scale.m_per_unit == pytest.approx(M)
    unlabelled = next(r for r in out.rooms if r.id == "r3")
    assert unlabelled.area_m2 == pytest.approx(exact(0.1), rel=0.01)
    assert unlabelled.area_source == "geometry_x_estimate"
    assert [r.area_m2 for r in out.rooms[:3]] == [exact(0.15)] * 3  # labels kept as read
    assert any(LABEL_SOURCE in note for note in out.notes)
    assert out.printed == ()  # no estimate before: no scale conflict


def test_a_door_estimate_inside_the_bands_stays():
    before = found(door(M * 1.1), LABELLED)  # 10%: the bands (16% and 8%) overlap
    assert with_label_scale(before, [PAGE]) == before


def test_a_door_estimate_outside_the_bands_is_replaced_and_kept_as_a_conflict_value():
    estimated = found(door(M * 1.8), LABELLED)
    estimated = estimated.model_copy(
        update={"rooms": (*LABELLED[:3], LABELLED[3].model_copy(update={
            "area_m2": 99.0, "area_status": "estimated", "area_source": "geometry_x_estimate"}))}
    )  # fmt: skip
    out = with_label_scale(estimated, [PAGE])
    assert out.scale.m_per_unit == pytest.approx(M)
    assert next(r for r in out.rooms if r.id == "r3").area_m2 == pytest.approx(exact(0.1), rel=0.01)
    values = {(m.quantity, m.value.method): m.value.value for m in out.printed}
    assert values == {
        ("scale", "detector"): M * 1.8,
        ("scale", "printed_label"): out.scale.m_per_unit,
    }


@pytest.mark.parametrize(
    "scale",
    [
        Scale(status="scaled", m_per_unit=M * 2, source="scale bar"),
        Scale(status="not_to_scale"),
    ],
)
def test_a_printed_scale_is_never_replaced(scale: Scale):
    before = found(scale, LABELLED)
    assert with_label_scale(before, [PAGE]) == before


def test_a_room_far_from_the_label_scale_is_still_a_conflict():
    rooms = [*(room(i, 0.15, exact(0.15)) for i in range(4)), room(4, 0.15, 10 * exact(0.15))]
    out = with_label_scale(found(Scale(status="no_scale"), rooms), [PAGE])
    assert out.scale.m_per_unit == pytest.approx(M)
    assert [n for n in out.notes if n.startswith(LABEL_NOTE + "r4 ")]


def test_the_sheet_wide_label_check_is_skipped_on_the_label_scale():
    """Circularity: the labels agree with the scale made from them. A label scale off by 2x
    (only possible through a bug, so built by hand) still says nothing."""
    rooms = tuple(LABELLED)
    labels = Scale(status="estimated", m_per_unit=M * 2, source=f"{LABEL_SOURCE} 3 room labels")
    doors = labels.model_copy(update={"source": "a door is about 0.794 m wide"})
    drawing = Drawing.model_validate(
        {"file": "f.png", "pages": [PAGE.model_dump()], "scale": doors.model_dump(), "rooms": [
            r.model_dump() for r in rooms]}
    )  # fmt: skip
    assert label_disputed(drawing) is not None  # #620 on the door estimate
    assert label_disputed(drawing.model_copy(update={"scale": labels})) is None


class Inner:
    def __init__(self, extracted: Extracted) -> None:
        self.extracted = extracted

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return self.extracted


SOURCE = DrawingFile(path="data/x/a.jpg", size=1, sha256="0" * 64, kind="jpeg")
SHEET = Sheet(file=SOURCE, pages=(PAGE,))


@pytest.mark.parametrize(
    ("kind", "rectified", "applied"),
    [
        ("png_plan", False, True),  # a scan
        ("pdf_scan", False, True),
        ("photo_plan", True, True),  # a photo the rectifier straightened
        ("photo_plan", False, False),  # perspective: no one global scale
        ("photo", False, False),
        (None, False, True),  # the CLI's probe found no kind: not a photo
    ],
)
def test_label_scale_applies_to_scans_and_rectified_photos(
    kind: str | None, rectified: bool, applied: bool
):
    reader = LabelScale(
        Inner(found(Scale(status="no_scale"), LABELLED)),
        lambda path: kind,
        lambda path: rectified,
    )
    scale = reader.extract(SOURCE, SHEET).scale
    assert (scale.status == "estimated") is applied


def test_min_rooms_matches_the_sheet_wide_check():
    from app.core.pipeline.takeoff import LABEL_SCALE_ROOMS

    assert MIN_ROOMS == LABEL_SCALE_ROOMS


def test_always_replaces_a_door_estimate_inside_the_bands():
    out = with_label_scale(found(door(M * 1.1), LABELLED), [PAGE], always=True)
    assert out.scale.m_per_unit == pytest.approx(M)
    assert {m.value.method for m in out.printed} == {"detector", "printed_label"}


@pytest.mark.parametrize(("name", "wrapped"), [("off", False), ("on", True), ("always", True)])
def test_label_scale_off_leaves_the_raster_reader_as_it_is(name: str, wrapped: bool):
    from app.composition import _labelled  # pyright: ignore[reportPrivateUsage]
    from app.settings import Settings

    inner = Inner(found(Scale(status="no_scale"), LABELLED))
    reader = _labelled(Settings(label_scale=name), inner, lambda p: None, lambda p: False)  # type: ignore[arg-type]
    assert (reader is not inner) is wrapped


@pytest.mark.parametrize("door_factor", [1.8, 2.5, 0.3])  # 2.5x and 0.3x: over ESTIMATE_RANGE
def test_the_scale_conflict_is_decided_for_the_label_scale(door_factor: float):
    from app.core.pipeline.second_count import measured, second_count

    out = with_label_scale(found(door(M * door_factor), LABELLED), [PAGE])
    (entry,) = [c for c in second_count(measured(out), out.printed) if c.quantity == "scale"]
    assert entry.status == "conflict"
    assert entry.resolution is not None
    assert entry.resolution.value == out.scale.m_per_unit
    assert "room labels" in entry.resolution.rule


def test_label_scale_is_part_of_the_ingest_reuse_key(tmp_path):
    from app.composition import build_ingest
    from app.settings import Settings

    def names(value: str) -> dict[str, str]:
        settings = Settings(label_scale=value)  # type: ignore[arg-type]
        ingest = build_ingest(settings, tmp_path / value, background=False)
        ingest.close()
        return ingest._names  # pyright: ignore[reportPrivateUsage]

    assert "label_scale" not in names("off")  # the default keeps its cache keys
    assert names("on")["label_scale"] == "on"
