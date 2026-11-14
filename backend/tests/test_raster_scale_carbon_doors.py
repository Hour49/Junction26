"""SCALE_CARBON_DOORS=on (app/adapters/raster_scale/carbon_doors.py): a raster sheet whose detector
found no door takes the door estimate from the Carbon reader's door boxes, in the composition's
shape CarbonDoorScale(CarbonThings(PriorScale(shipped), carbon)). Synthetic."""

from pathlib import Path

import pytest
from test_raster_composite import FILE, SHEET, Fake, element

from app.adapters.carbon import CarbonThings
from app.adapters.carbon.contract import SOURCE
from app.adapters.raster_scale import PriorScale
from app.adapters.raster_scale.carbon_doors import NO_DOOR, CarbonDoorScale
from app.composition import build_pipeline
from app.core.drawing.model import Element, Room
from app.core.errors import InvalidInputError
from app.core.pipeline.raster_scale import CARBON_DOOR_M, SPREAD_FEW
from app.settings import Settings

LIVING = Room(id="r1", type="living", page=1, box=(0.0, 0.0, 0.5, 0.5))


def carbon_door(box: tuple[float, float, float, float]) -> Element:
    return Element.model_validate(
        {"id": "c", "class": "door", "page": 1, "box": box, "attrs": {"reader": SOURCE}}
    )


def things(shipped: Fake, carbon: Fake) -> CarbonThings:
    return CarbonThings(PriorScale(shipped), carbon, lambda _: True)


def test_no_detector_door_and_carbon_doors_give_an_estimate_from_carbon_s() -> None:
    carbon = Fake(elements=[carbon_door((0.1, 0.1, 0.3, 0.3)), carbon_door((0.5, 0.5, 0.75, 0.6))])
    found = CarbonDoorScale(things(Fake(rooms=[LIVING]), carbon)).extract(FILE, SHEET)
    assert found.scale.status == "estimated"
    assert found.scale.m_per_unit == pytest.approx(CARBON_DOOR_M / 9)  # median of 8 and 10 px
    assert found.scale.uncertainty == SPREAD_FEW  # the widest band, whatever the door count
    assert "2 doors the Carbon reader found" in (found.scale.source or "")
    assert found.rooms[0].area_status == "estimated" and found.rooms[0].area_m2 is not None
    assert NO_DOOR not in found.notes
    assert found.notes[-1].startswith("scale estimate: a door is about 0.794 m wide")


def test_without_carbon_doors_the_sheet_stays_refused() -> None:
    inner = things(Fake(rooms=[LIVING]), Fake(elements=[element("window", (0.1, 0.1, 0.2, 0.2))]))
    found = CarbonDoorScale(inner).extract(FILE, SHEET)
    assert found == inner.extract(FILE, SHEET)
    assert found.scale.status == "no_scale" and NO_DOOR in found.notes


def test_a_detector_door_keeps_priorscale_s_estimate_unchanged() -> None:
    detector = Fake(elements=[element("door", (0.1, 0.1, 0.3, 0.2))], rooms=[LIVING])
    inner = things(detector, Fake(elements=[carbon_door((0.1, 0.1, 0.5, 0.5))]))
    assert CarbonDoorScale(inner).extract(FILE, SHEET) == inner.extract(FILE, SHEET)


def test_the_setting_needs_priors_and_carbon_s_things(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert Settings(_env_file=None).scale_carbon_doors == "off"  # pyright: ignore[reportCallIssue]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("SCALE_CARBON_DOORS", "on")
    monkeypatch.setenv("RASTER_SCALE", "priors")
    with pytest.raises(InvalidInputError, match="SCALE_CARBON_DOORS=on needs"):
        build_pipeline(Settings(_env_file=None), tmp_path)  # pyright: ignore[reportCallIssue]


def test_the_measure_script_scores_only_sheets_scaled_from_carbon_s_doors() -> None:
    from scripts.carbon_door_scale import rows

    page = [{"width": 1000}]
    gold = {f: {"file": f, "pages": page, "scale": {"m_per_unit": 0.01}} for f in ("a", "b")}
    on = {
        "a": {"pages": page, "scale": {"m_per_unit": 0.011, "uncertainty": 0.158,
                                        "source": "median of 3 doors the Carbon reader found"}},
        "b": {"pages": page, "scale": {"m_per_unit": 0.02, "source": "3 detected doors"}},
    }  # fmt: skip
    off = {"a": {"scale": {"status": "no_scale"}}}
    assert rows(off, on, gold) == [("a", "no_scale", pytest.approx(0.1), 0.158)]
