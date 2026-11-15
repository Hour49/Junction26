"""The picture lane's core (docs/specs/backend/discipline-pictures.md, AC-1..AC-8): hand-written
readings, no image and no dataset file."""

from pathlib import Path

import pytest

from app.core.picture_facts import (
    NO_SCALE,
    LegendEntry,
    PictureReading,
    Run,
    Sighting,
    Spot,
    double_check,
    kind_of,
    level_of_fact,
    picture_facts,
)
from app.core.review.check import CheckPolicy, Counts
from tests.test_architecture import forbidden_imports

HEATER = "Radiator 22-600"
OTHER_HEATER = "Radiator 11-400"
LEGEND = (
    LegendEntry(label=HEATER, group="Heating", line=False, box=(0.9, 0.1, 0.91, 0.11)),
    LegendEntry(label=OTHER_HEATER, group="Heating", line=False, box=(0.9, 0.12, 0.91, 0.13)),
    LegendEntry(label="Logo", group=None, line=False, box=None),
    LegendEntry(label="Heating pipe", group="Heating", line=True, box=None),
)


def _spot(x: float, y: float, reader: str) -> Spot:
    return Spot(page=1, box=(x, y, x + 0.01, y + 0.01), reader=reader)


def _seen(label: str, points: list[tuple[float, float]], reader: str, **kw: float) -> list:
    return [Sighting(label=label, spot=_spot(x, y, reader), **kw) for x, y in points]


def _reading(reader: str, sightings: list, **changes: object) -> PictureReading:
    given: dict[str, object] = {
        "reader": reader,
        "legend": LEGEND,
        "read": None,
        "sightings": tuple(sightings),
        "storey": "2. krs",
    }
    return PictureReading.model_validate(given | changes)


GRID = [(0.05 + 0.08 * i, 0.5) for i in range(10)]


# --- AC-1 kind_of --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "group", "expected"),
    [
        ("Radiator", None, ("space_heater", "heating")),
        ("Heizkörper", None, ("space_heater", "heating")),
        ("lämpöpatteri", None, ("space_heater", "heating")),
        ("Supply air diffuser", None, ("air_terminal", "ventilation")),
        ("Socket outlet 2x", None, ("outlet", "electrical")),
        ("Valve", "Heating", ("valve", "heating")),
        ("Valve", "Cold water", ("valve", "plumbing")),
        ("Logo", None, None),
        ("Main switchboard", None, ("electric_distribution_board", "electrical")),
        ("M_Radiator - Hosted:Readiator - 25", None, ("space_heater", "heating")),  # Revit M_
        ("M_Ball Valve - 50 mm", "Unit A Hydronic Supply In", ("valve", "heating")),
        ("M_Lavatory - Oval:535 mmx485 mm", None, ("sanitary_terminal", "plumbing")),
        ("M_Water Closet - Flush Tank", None, ("sanitary_terminal", "plumbing")),
        ("M_Sink - Island - Single", None, ("sanitary_terminal", "plumbing")),
        (
            "M_Lighting and Appliance Panelboard - 208V MLO:400 A",
            None,
            ("electric_distribution_board", "electrical"),
        ),  # a panel, not a light
    ],
)
def test_kind_of_maps_a_legend_label_to_an_ifc_kind(
    label: str, group: str | None, expected: tuple[str, str] | None
) -> None:
    assert kind_of(label, group) == expected


# --- AC-2, AC-3 double_check ---------------------------------------------------------------------


def test_two_readers_that_match_nine_of_ten_agree_and_dispute_the_rest() -> None:
    first = _reading("vlm", _seen(HEATER, GRID, "vlm"))
    # nine at the same places (a hair off), the tenth somewhere else
    second_points = [(x + 0.001, y) for x, y in GRID[:9]] + [(0.5, 0.9)]
    second = _reading("template", _seen(HEATER, second_points, "template"))

    checked = double_check(first, second)

    assert checked.agreed[HEATER] is True
    places = {(d.box[0], d.box[1]) for d in checked.disputed}
    assert places == {GRID[9], (0.5, 0.9)}
    for place in checked.disputed:
        assert place.mark_id is None
        assert set(place.readers) == {"vlm", "template"}
        assert "nothing" in place.readers.values()
        assert HEATER in place.readers.values()


def test_disputed_places_are_at_most_five_strongest_reader_a_spot_first() -> None:
    scores = [0.1, 0.9, 0.5, 0.7, 0.3, 0.8, 0.2]
    first = _reading(
        "vlm",
        [
            Sighting(label=HEATER, spot=_spot(0.1 * i, 0.2, "vlm"), score=score)
            for i, score in enumerate(scores)
        ],
    )
    second = _reading("template", _seen(HEATER, [(0.5, 0.9)], "template"))

    checked = double_check(first, second)

    assert checked.agreed[HEATER] is False
    assert len(checked.disputed) == 5
    expected = [0.1 * i for i, _ in sorted(enumerate(scores), key=lambda p: -p[1])[:5]]
    assert [d.box[0] for d in checked.disputed] == pytest.approx(expected)


def test_one_reader_agrees_on_nothing_and_disputes_nowhere() -> None:
    first = _reading("vlm", _seen(HEATER, GRID, "vlm"))

    checked = double_check(first, None)

    assert not any(checked.agreed.values())
    assert checked.disputed == ()
    sheet = picture_facts("d1", checked)
    assert sheet.facts
    assert all(fact.source.endswith(":held") for fact in sheet.facts)


# --- AC-4 counts ---------------------------------------------------------------------------------


def test_counts_per_kind_and_per_label_with_one_spot_per_sighting() -> None:
    first = _reading(
        "vlm", _seen(HEATER, GRID[:9], "vlm") + _seen(OTHER_HEATER, [(0.1, 0.8)] * 3, "vlm")
    )
    second = _reading(
        "template",
        _seen(HEATER, GRID[:9], "template") + _seen(OTHER_HEATER, [(0.1, 0.8)] * 3, "template"),
    )

    sheet = picture_facts("drawing-7", double_check(first, second))

    assert sheet.model == "drawing-7"
    assert sheet.disciplines[0] == "heating"  # most facts first; the 0 Logo count is "other"
    by = {(f.topic, f.subject): f for f in sheet.facts}
    total = by[("space_heater.count", "all")]
    assert total.value == 12
    assert total.unit == "count"
    assert total.storey == "2. krs"
    assert total.discipline == "heating"
    assert total.source == "picture:vlm+template"
    assert len(total.spots) == 12
    assert by[("space_heater.count", HEATER)].value == 9
    assert len(by[("space_heater.count", HEATER)].spots) == 9
    assert by[("space_heater.count", OTHER_HEATER)].value == 3
    assert by[("category.count", "Heating")].value == 12


def test_a_label_that_maps_to_no_kind_is_a_symbol_count() -> None:
    first = _reading("vlm", _seen("Logo", [(0.2, 0.2)], "vlm"))
    second = _reading("template", _seen("Logo", [(0.2, 0.2)], "template"))

    facts = picture_facts("d1", double_check(first, second)).facts

    logo = [f for f in facts if f.subject == "Logo"]
    assert [(f.topic, f.value, f.storey) for f in logo] == [
        ("symbol.count", 1, None),  # the sheet's, then its storey's copy (the title's storey)
        ("symbol.count", 1, "2. krs"),
    ]


# --- AC-5 what was read ---------------------------------------------------------------------------


def test_only_what_was_read_has_a_fact_and_zero_needs_both_readers() -> None:
    first = _reading("vlm", _seen(HEATER, GRID[:2], "vlm"), read=(HEATER, OTHER_HEATER))
    second = _reading("template", _seen(HEATER, GRID[:2], "template"), read=(OTHER_HEATER,))

    facts = picture_facts("d1", double_check(first, second)).facts
    by = {(f.topic, f.subject): f for f in facts}

    assert by[("space_heater.count", OTHER_HEATER)].value == 0  # both looked, none found
    assert by[("space_heater.count", OTHER_HEATER)].source == "picture:vlm+template"
    held = by[("space_heater.count", HEATER)]  # only vlm looked for it
    assert held.value == 2
    assert held.source == "picture:vlm:held"
    assert not [f for f in facts if f.subject == "Logo"]  # nobody looked for it


def test_a_label_one_reader_looked_for_and_did_not_find_has_no_fact() -> None:
    first = _reading("vlm", [], read=(HEATER,))
    facts = picture_facts("d1", double_check(first, None)).facts
    assert facts == []


# --- AC-6 runs ------------------------------------------------------------------------------------


def _runs(reader: str, **changes: object) -> PictureReading:
    runs = (
        Run(label="Heating pipe", size="DN20", length_m=9.9, spots=(_spot(0.1, 0.1, reader),)),
        Run(label="Heating pipe", size="DN15", length_m=28.6, spots=(_spot(0.3, 0.1, reader),)),
    )
    return _reading(reader, [], runs=runs, **changes)


def test_runs_give_length_size_length_and_with_length() -> None:
    sheet = picture_facts("d1", double_check(_runs("mask"), _runs("vlm")))
    by = {(f.topic, f.subject, f.system): f for f in sheet.facts}

    length = by[("pipe_segment.length", "all", "Heating")]
    assert (length.value, length.unit) == (pytest.approx(38.5), "m")
    assert length.discipline == "heating"
    assert length.source == "picture:mask+vlm"
    assert len(length.spots) == 2
    assert by[("pipe_segment.size_length", "DN20", "Heating")].value == pytest.approx(9.9)
    assert by[("pipe_segment.with_length", "all", "Heating")].value == 2
    assert by[("pipe_segment.with_length", "all", "Heating")].unit == "count"


@pytest.mark.parametrize(
    ("label", "kind", "discipline"),
    [
        ("Unit A Hydronic Supply In", "pipe_segment", "heating"),
        ("Unit B Domestic Cold Water", "pipe_segment", "plumbing"),
        ("Supply Air", "duct_segment", "ventilation"),
        ("Heating pipe", "pipe_segment", "heating"),
    ],
)
def test_a_line_style_named_by_its_system_is_that_discipline_s_run(
    label: str, kind: str, discipline: str
) -> None:
    legend = (LegendEntry(label=label, group=None, line=True, box=None),)
    run = Run(label=label, size=None, length_m=1.5, spots=(_spot(0.1, 0.1, "mask"),))
    reading = _reading("mask", [], legend=legend, runs=(run,))
    by = {(f.topic, f.subject): f for f in picture_facts("d1", double_check(reading, None)).facts}
    length = by[(f"{kind}.length", "all")]
    assert length.value == pytest.approx(1.5) and length.discipline == discipline


def test_runs_that_differ_by_more_than_ten_percent_are_held() -> None:
    longer = _reading(
        "vlm",
        [],
        runs=(Run(label="Heating pipe", size=None, length_m=50.0, spots=()),),
    )
    checked = double_check(_runs("mask"), longer)
    assert checked.agreed["Heating pipe"] is False
    lengths = [f for f in picture_facts("d1", checked).facts if f.topic == "pipe_segment.length"]
    assert lengths and all(f.source.endswith(":held") for f in lengths)


def test_a_reading_without_a_scale_gives_no_length() -> None:
    sheet = picture_facts("d1", double_check(_runs("mask", notes=(NO_SCALE,)), None))
    assert not [f for f in sheet.facts if f.unit == "m"]


# --- AC-7 levels ----------------------------------------------------------------------------------

NONE_MEASURED = Counts(units=0, exact=0)
POLICY = CheckPolicy(
    thresholds={}, counts={"low": NONE_MEASURED, "medium": NONE_MEASURED, "high": NONE_MEASURED}
)


def _agreed_and_held() -> list:
    first = _reading("vlm", _seen(HEATER, GRID, "vlm") + _seen(OTHER_HEATER, [(0.1, 0.8)], "vlm"))
    second = _reading("template", _seen(HEATER, GRID, "template"))
    facts = {f.subject: f for f in picture_facts("d1", double_check(first, second)).facts}
    return [facts[HEATER], facts[OTHER_HEATER]]


def test_an_unrated_route_is_low_and_a_held_label_is_held() -> None:
    agreed, held = _agreed_and_held()
    level = level_of_fact(POLICY, agreed)
    assert level is not None
    assert (level.level, level.basis) == ("low", "unrated")
    level = level_of_fact(POLICY, held)
    assert level is not None
    assert (level.level, level.basis) == ("low", "held")


def test_a_medium_route_makes_an_agreed_answer_medium_but_not_a_held_one() -> None:
    agreed, held = _agreed_and_held()
    policy = POLICY.model_copy(update={"route_levels": {"picture": "medium"}})
    level = level_of_fact(policy, agreed)
    assert level is not None
    assert (level.level, level.basis) == ("medium", "route")
    level = level_of_fact(policy, held)
    assert level is not None
    assert (level.level, level.basis) == ("low", "held")


# --- AC-8 a pure core -----------------------------------------------------------------------------


def test_picture_facts_imports_no_adapter_image_library_model_reader_or_settings() -> None:
    path = Path(__file__).parent.parent / "app" / "core" / "picture_facts.py"
    source = path.read_text()
    assert forbidden_imports(source, "app.core.picture_facts") == []
    assert "ifcopenshell" not in source


def test_a_radiator_named_with_its_valve_and_german_compound_valves_and_pumps() -> None:
    from app.core.picture_facts import kind_of

    def kind(label: str) -> str | None:
        found = kind_of(label, None)
        return found and found[0]

    # Revit type names from a German services model (rwth-digitalhub): a radiator named with
    # its valve's side is a radiator; valves and pumps are compound words
    assert kind("Heizkörper Plan Ventil Unten:Rechts") == "space_heater"
    assert kind("Schrägsitzventil DN 12 - 50 - Gewinde:ND 25") == "valve"
    assert kind("Absperrventil allgemein - Flansch:Standard") == "valve"
    assert kind("Doppelpumpe DN 32 - 100 - Flansch:DN 50") == "pump"
    assert kind("RLT-Gerät Ventilatorkammer:Ventilatorkammer 1.0") == "fan"  # not a valve
    # unchanged: a radiator's valve is a valve, and the plain names keep their kinds
    assert kind("Radiator valve") == "valve"
    assert kind("Heizkörperventil") == "valve"
    assert kind("M_Radiator - Panel") == "space_heater"
    assert kind("Supply air diffuser") == "air_terminal"


@pytest.mark.parametrize(
    "label",
    [
        "Radiator lockshield valve",
        "Radiator return valve",
        "Radiator angle valve",
        "Valve - Radiator",
        "Valve Radiator Oventrop AV 9",
        "HC_Valve_Radiator_MEPcontent_Oventrop_AV 9_Angle Pattern:DN 15",
        "HC Valve Radiator MEPcontent Oventrop AV 9 Angle Pattern:DN 15",  # OCR'd, no underscores
        "Heizkörper Ventil",
        "Heizkörper-Ventil",
        "Heizkörper Ventil Typ",
        "Heizkörper-Thermostatventil",
        "Radiatorventil",
        "Patteriventtiili",
        "Lämpöpatteri venttiili",
    ],
)
def test_a_valve_named_with_its_radiator_is_a_valve(label: str) -> None:
    found = kind_of(label, None)
    assert found is not None and found[0] == "valve"


def test_only_a_radiator_family_that_names_its_valve_position_is_a_radiator() -> None:
    for label in ("Heizkörper Plan Ventil Unten:Rechts", "Heizkörper Kompakt Ventil Oben:Links"):
        assert kind_of(label, None) == ("space_heater", "heating")
