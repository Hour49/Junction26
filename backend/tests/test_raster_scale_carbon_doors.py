"""SCALE_CARBON_DOORS=on (app/adapters/raster_scale/carbon_doors.py): a raster sheet whose detector
found no door takes the door estimate from the Carbon reader's door boxes, in the composition's
shape CarbonDoorScale(CarbonThings(PriorScale(shipped), carbon)). Synthetic."""

from pathlib import Path
from typing import Any

import pytest
from test_raster_composite import FILE, SHEET, Fake, element

from app.adapters.carbon import CarbonThings
from app.adapters.carbon.contract import SOURCE
from app.adapters.raster_scale import PriorScale
from app.adapters.raster_scale.carbon_doors import NO_DOOR, CarbonDoorScale
from app.composition import build_ingest, build_pipeline
from app.core.drawing.model import Element, Room
from app.core.errors import InvalidInputError
from app.core.pipeline.printed import CARBON_DOORS_REFUSED
from app.core.pipeline.raster_scale import CARBON_DOOR_M, SPREAD_FEW, SPREAD_MANY
from app.core.pipeline.steps import without_steps
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
    assert found.notes[-1].startswith("scale estimate: a door is about 1.069 m wide")


def test_without_carbon_doors_the_sheet_stays_refused() -> None:
    inner = things(Fake(rooms=[LIVING]), Fake(elements=[element("window", (0.1, 0.1, 0.2, 0.2))]))
    found = CarbonDoorScale(inner).extract(FILE, SHEET)
    assert without_steps(found) == without_steps(inner.extract(FILE, SHEET))
    assert found.scale.status == "no_scale" and NO_DOOR in found.notes


def test_a_detector_door_keeps_priorscale_s_estimate_unchanged() -> None:
    detector = Fake(elements=[element("door", (0.1, 0.1, 0.3, 0.2))], rooms=[LIVING])
    inner = things(detector, Fake(elements=[carbon_door((0.1, 0.1, 0.5, 0.5))]))
    found = CarbonDoorScale(inner).extract(FILE, SHEET)
    assert without_steps(found) == without_steps(inner.extract(FILE, SHEET))


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
    assert rows(off, on, gold) == []  # a source without the door width it used is not scored
    on["a"]["scale"]["source"] = "a door is about 0.794 m wide; " + on["a"]["scale"]["source"]
    assert rows(off, on, gold) == [("a", "no_scale", pytest.approx(0.1), 0.158, 0.794)]


def test_carbon_doors_on_m1_the_script_prints_the_signed_error_and_the_width_that_zeroes_it() -> (
    None
):
    """codecheck M1: Carbon's boxes include the swing, so the scale is about 14.5% low on golden;
    integ pastes the fitted CARBON_DOOR_M."""
    from scripts.carbon_door_scale import fit, rows

    page = [{"width": 1000}]
    source = "a door is about 0.794 m wide; median of 3 doors the Carbon reader found"
    gold = {f: {"pages": page, "scale": {"m_per_unit": 0.01}} for f in "abc"}
    on = {f: {"pages": page, "scale": {"m_per_unit": m, "uncertainty": 0.158, "source": source}}
          for f, m in (("a", 0.0080), ("b", 0.00855), ("c", 0.0110))}  # fmt: skip
    found = rows({}, on, gold)
    assert [round(error, 4) for _, _, error, _, _ in found] == [-0.2, -0.145, 0.1]  # signed
    width = fit(found)
    assert width == pytest.approx(0.794 / 0.855)
    again = [(1 + error) * width / 0.794 - 1 for _, _, error, _, _ in found]
    assert sorted(again)[1] == pytest.approx(0.0)  # the fitted width zeroes the median


def test_carbon_doors_on_s1_doors_snapped_to_unsure_detector_doors_are_left_out() -> None:
    """codecheck S1: a detector with only doors under MIN_DOOR_SCORE also gets PriorScale's
    no-door note, and CarbonThings snaps Carbon's doors onto those boxes: the median would mix
    an opening with Carbon's swing boxes, and "the detector found none" would be false."""
    unsure = element("door", (0.10, 0.10, 0.15, 0.12), score=0.2)  # 2 px: an opening
    shipped = Fake(elements=[unsure], rooms=[LIVING])
    carbon = Fake(elements=[carbon_door((0.05, 0.05, 0.30, 0.30)),  # holds it: snapped, left out
                            carbon_door((0.50, 0.50, 0.75, 0.60)),  # 10 px
                            carbon_door((0.60, 0.10, 0.80, 0.30))])  # 8 px # fmt: skip
    found = CarbonDoorScale(things(shipped, carbon)).extract(FILE, SHEET)
    assert found.scale.m_per_unit == pytest.approx(CARBON_DOOR_M / 9)  # 8 and 10 px only
    assert "2 doors the Carbon reader found (the detector found no door it is sure of)" in (
        found.scale.source or ""
    )


def test_carbon_doors_on_s2_a_non_carbon_door_is_not_counted() -> None:
    other = element("door", (0.0, 0.0, 0.9, 0.9)).model_copy(update={"attrs": {"reader": "x"}})

    class Mixed:  # a reading with a door that is not Carbon's (a later wrapper's, say)
        def extract(self, source: Any, sheet: Any) -> Any:
            found = things(Fake(rooms=[LIVING]), Fake(elements=[carbon_door((0.1, 0.1, 0.3, 0.3))]))
            got = found.extract(source, sheet)
            return got.model_copy(update={"elements": (*got.elements, other)})

    found = CarbonDoorScale(Mixed()).extract(FILE, SHEET)
    assert found.scale.m_per_unit == pytest.approx(CARBON_DOOR_M / 8)  # the 36 px door is not


def test_carbon_doors_on_s2_only_priorscale_s_no_door_refusal_is_replaced() -> None:
    # doors not read at all: another refusal, which Carbon's doors do not answer
    shipped = Fake(rooms=[LIVING], read=["room"])
    inner = things(shipped, Fake(elements=[carbon_door((0.1, 0.1, 0.3, 0.3))]))
    found = CarbonDoorScale(inner).extract(FILE, SHEET)
    assert found.scale.status == "no_scale"
    assert without_steps(found) == without_steps(inner.extract(FILE, SHEET))


def test_carbon_doors_on_s2_the_band_is_the_widest_with_five_doors_or_more() -> None:
    doors = [carbon_door((0.1 * i, 0.1, 0.1 * i + 0.2, 0.3)) for i in range(5)]
    found = CarbonDoorScale(things(Fake(rooms=[LIVING]), Fake(elements=doors))).extract(FILE, SHEET)
    assert found.scale.uncertainty == SPREAD_FEW != SPREAD_MANY


def test_carbon_doors_on_s2_the_composition_wraps_carbon_s_things_and_names_it_in_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from ingest.test_ingest_carbon import carbon_settings

    def built(**on: str) -> tuple[object, dict[str, str]]:
        monkeypatch.delenv("SCALE_CARBON_DOORS", raising=False)
        env = {"CARBON_READER": "large", "RASTER_SCALE": "priors", **on}
        settings = carbon_settings(monkeypatch, tmp_path, **env)
        raster = build_pipeline(settings, tmp_path).extractors["raster"]
        ingest = build_ingest(settings, tmp_path / "projects", background=False)
        ingest.close()
        return raster._inner, ingest._names  # pyright: ignore[reportAttributeAccessIssue, reportPrivateUsage]

    wrapped, names = built(SCALE_CARBON_DOORS="on")
    assert isinstance(wrapped, CarbonDoorScale) and names["scale_carbon_doors"] == "on"
    plain, names = built()
    assert isinstance(plain, CarbonThings) and "scale_carbon_doors" not in names


def printed_then(printed: Any, dpi: float | None = None) -> Any:
    """The sheet read as composition wires it, the printed scale outside the Carbon door scale."""
    from test_printed_scale import Files, Reader, png

    from app.adapters.printed_scale import PrintedScale

    carbon = Fake(elements=[carbon_door((0.1, 0.1, 0.3, 0.3)), carbon_door((0.5, 0.5, 0.75, 0.6))])
    inner = CarbonDoorScale(things(Fake(rooms=[LIVING]), carbon))
    return PrintedScale(inner, Reader(printed), Files(png(dpi))).extract(FILE, SHEET)


@pytest.mark.parametrize("text", ['1/4" = 1\'-0"', "bar"])
def test_carbon_doors_refuse_a_printed_scale_that_could_not_be_read_is_not_replaced(
    text: str,
) -> None:
    from app.core.pipeline.printed import PrintedSheet

    found = printed_then(PrintedSheet(printed_scale=text))  # no trusted dpi, no bar measured
    assert found.scale.status == "no_scale" and found.scale.m_per_unit is None
    assert found.rooms[0].area_m2 is None and found.rooms[0].area_status is None
    assert CARBON_DOORS_REFUSED in found.notes
    assert not any("the Carbon reader found" in note for note in found.notes)


def test_carbon_doors_refuse_no_printed_scale_keeps_the_door_scale() -> None:
    from app.core.pipeline.printed import PrintedSheet

    found = printed_then(PrintedSheet())
    assert found.scale.status == "estimated"
    assert "2 doors the Carbon reader found" in (found.scale.source or "")
    assert found.rooms[0].area_m2 is not None
    assert CARBON_DOORS_REFUSED not in found.notes


def test_carbon_doors_refuse_a_printed_scale_that_was_read_wins() -> None:
    from app.core.pipeline.printed import PrintedSheet, ScaleBar

    bar = ScaleBar(page=1, start=(0.1, 0.9), end=(0.9, 0.9), length_m=5.0, text="0 5 m")  # 32 px
    found = printed_then(PrintedSheet(printed_scale="1:100", bars=(bar,)))
    assert found.scale.status == "scaled" and "printed scale bar" in (found.scale.source or "")
    assert found.rooms[0].area_status == "estimated" and found.rooms[0].area_m2 is not None
    assert CARBON_DOORS_REFUSED not in found.notes
