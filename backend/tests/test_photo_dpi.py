"""A camera photo's stated resolution is the camera's, not the paper's (QA R3-B6, T4: a photo of
a book page, camera EXIF "300 dpi", printed 1/32" = 1'-0", came back 227 m², one room 28 m² for
~150 m²). So a printed ratio is never turned into metres on a camera photo; the door estimate and
a scale bar measured on the photo stay as they were (the demo phone photos keep their reading).
Synthetic."""

from pathlib import Path

import pytest
from test_printed_scale import BAR, DOOR_M, FILE, SHEET, Files, Fixed, Reader, png

from app.adapters.printed_scale import PrintedScale
from app.adapters.raster_scale import PriorScale
from app.composition import build_pipeline
from app.core.pipeline.model import Extracted
from app.core.pipeline.printed import PrintedSheet
from app.settings import Settings

T4 = PrintedSheet(printed_scale='1/32" = 1\'-0"')  # what the T4 page prints


def read(printed: PrintedSheet, kind: str, dpi: float = 300.0) -> Extracted:
    """The sheet through the door estimate and the printed scale, as composition wires them, its
    file stating `dpi` and identified by ingest as `kind`."""
    inner = Fixed(side_px=DOOR_M / 0.02)
    wrapped = PrintedScale(PriorScale(inner), Reader(printed), Files(png(dpi)), lambda _: kind)
    return wrapped.extract(FILE, SHEET)


@pytest.mark.parametrize("kind", ["photo_plan", "photo"])
def test_a_printed_ratio_is_not_turned_into_metres_at_a_cameras_dpi(kind: str) -> None:
    found = read(T4, kind)
    assert "scale_text" not in found.scale.evidence, found.scale
    assert found.scale.status == "estimated"  # the doors' estimate, as without a printed ratio
    assert any("read, not used" in note for note in found.notes), found.notes


def test_the_same_ratio_at_a_scans_stated_dpi_is_still_used() -> None:
    found = read(T4, "png_plan")
    assert found.scale.status == "scaled" and "scale_text" in found.scale.evidence
    assert found.scale.m_per_unit == pytest.approx(384 * 0.0254 / 300, rel=1e-3)


def test_a_scale_bar_on_a_camera_photo_is_kept_as_on_main() -> None:
    found = read(PrintedSheet(printed_scale="1:200", bars=(BAR,)), "photo_plan")
    assert found.scale.status == "scaled" and found.scale.m_per_unit == pytest.approx(0.02)
    assert "scale_bar" in found.scale.evidence


def test_the_door_estimate_on_a_camera_photo_is_kept_as_on_main() -> None:
    found = read(PrintedSheet(), "photo_plan")
    assert found.scale.status == "estimated" and found.scale.m_per_unit is not None


def test_composition_gives_the_printed_scale_ingests_kinds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RASTER_PRINTED_SCALE", "carbon")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def kinds(path: str) -> str | None:
        return "photo_plan"

    raster = build_pipeline(Settings(), tmp_path, kinds=kinds).extractors["raster"]
    while raster is not None and not isinstance(raster, PrintedScale):
        raster = getattr(raster, "_inner", None)
    assert isinstance(raster, PrintedScale)
    assert raster._kind_of is kinds  # pyright: ignore[reportPrivateUsage]
