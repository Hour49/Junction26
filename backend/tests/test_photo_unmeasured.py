"""A camera photo of a drawing (`photo_plan`) is not measured (QA R3-B6/A9/C9, T4: a photo of a
book page got 227 m² from a scale on the uncorrected photo, one room 28 m² for ~150 m²). Its
perspective makes the scale differ across the page and its resolution is the camera's, not the
paper's, so no scale is used on it: no m² and no lengths, while counts and areas printed in the
rooms' labels stay. Synthetic."""

from pathlib import Path

import pytest
from test_printed_scale import BAR, DOOR_M, FILE, SHEET, Files, Fixed, Reader, png

from app.adapters.answer_prior import NoPrior
from app.adapters.printed_scale import PrintedScale
from app.adapters.question_templates import TemplateParser
from app.adapters.raster.photo import PhotoUnmeasured
from app.adapters.raster_scale import PriorScale
from app.composition import build_pipeline
from app.core.drawing.model import Drawing, Room
from app.core.pipeline.model import Extracted
from app.core.pipeline.printed import PHOTO_NOTE, PrintedSheet, unmeasured_photo
from app.core.review.ask import ask
from app.core.review.model import ReviewState
from app.settings import Settings

LABELLED = Room(
    id="r9", type="living", page=1, box=(0.5, 0.5, 0.6, 0.6), area_m2=12.5,
    area_status="exact", area_source="printed",
)  # fmt: skip


def scaled(printed: PrintedSheet, dpi: float | None = None) -> Extracted:
    """The sheet through the door estimate and the printed scale, as composition wires them."""
    inner = Fixed(side_px=DOOR_M / 0.02)
    inner.found = inner.found.model_copy(update={"rooms": (*inner.found.rooms, LABELLED)})
    return PrintedScale(PriorScale(inner), Reader(printed), Files(png(dpi))).extract(FILE, SHEET)


@pytest.mark.parametrize(
    "printed",
    [
        PrintedSheet(),  # the doors' estimate (T4: "±17%")
        PrintedSheet(printed_scale="1:200", bars=(BAR,)),  # a bar measured on the photo
        PrintedSheet(printed_scale="1:100"),  # a ratio at the camera's stated 300 dpi
    ],
)
def test_a_photo_keeps_no_scale_and_no_measured_area(printed: PrintedSheet) -> None:
    found = scaled(printed, dpi=300.0)
    assert found.scale.m_per_unit is not None  # what a scan of the same sheet would use
    assert any(room.area_m2 for room in found.rooms if room.area_source != "printed")
    photo = unmeasured_photo(found)
    assert photo.scale.status == "no_scale" and photo.scale.m_per_unit is None
    measured, labelled = photo.rooms
    assert (measured.area_m2, measured.area_status, measured.area_source) == (None, None, None)
    assert labelled == LABELLED  # an area printed in the room's label is no measurement
    assert not [m for m in photo.printed if m.quantity == "scale"]  # no scale conflict either
    assert PHOTO_NOTE in photo.notes
    assert photo.elements == found.elements  # counts stay


def test_only_a_photo_is_left_unmeasured() -> None:
    inner = Fixed(side_px=DOOR_M / 0.02)
    kinds = {"plan.png": "png_plan"}
    kept = PhotoUnmeasured(PriorScale(inner), lambda path: kinds.get(path))
    assert kept.extract(FILE, SHEET).scale.status == "estimated"
    kinds["plan.png"] = "photo_plan"
    assert kept.extract(FILE, SHEET).scale.status == "no_scale"


def test_an_area_asked_on_a_photo_says_a_photo_cant_be_measured() -> None:
    photo = unmeasured_photo(scaled(PrintedSheet(printed_scale="1:200", bars=(BAR,))))
    drawing = Drawing(file=FILE.path, pages=SHEET.pages, scale=photo.scale, rooms=photo.rooms)
    found = ask(
        "What is the total area of the bedrooms?", drawing, parser=TemplateParser(),
        clock=lambda: 0.0, prior=NoPrior(), state=ReviewState(),
    )  # fmt: skip
    assert found.refusal is not None, found.answer
    assert found.refusal.code == "no-scale"
    assert "photo" in found.refusal.text and "can't be measured" in found.refusal.text


def test_the_composite_raster_route_and_the_printed_scale_leave_a_photo_unmeasured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every raster reading that can carry a scale passes `PhotoUnmeasured`: the composite reader
    (door estimate, Carbon's doors) and the printed scale outside it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "plans=one-plan")
    monkeypatch.setenv("RASTER_PRINTED_SCALE", "carbon")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    raster = build_pipeline(Settings(), tmp_path).extractors["raster"]
    chain = []
    while raster is not None:
        chain.append(type(raster).__name__)
        raster = getattr(raster, "_inner", None)
    assert chain.count("PhotoUnmeasured") == 2, chain
    assert chain.index("PhotoUnmeasured") < chain.index("PrintedScale"), chain
