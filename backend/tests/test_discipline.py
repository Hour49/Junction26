import pytest

from app.core.discipline import (
    discipline_from_census,
    discipline_from_question,
    discipline_from_sheet,
    discipline_from_title,
    system_from_question,
)


def _top(counts: dict[str, int]) -> str:
    return discipline_from_census(counts)[0][0]


@pytest.mark.parametrize(
    ("counts", "top"),
    [
        (
            {"IfcWall": 80, "IfcDoor": 20, "IfcWindow": 30, "IfcSpace": 25, "IfcBeam": 4},
            "architecture",
        ),
        (
            {"IfcWallStandardCase": 40, "IfcSlab": 12, "IfcColumn": 30, "IfcFooting": 10},
            "structural",
        ),
        ({"IfcPipeSegment": 300, "IfcPipeFitting": 200, "IfcSanitaryTerminal": 20}, "plumbing"),
        ({"IfcPipeSegment": 300, "IfcValve": 40, "IfcSpaceHeater": 30}, "heating"),
        ({"IfcDuctSegment": 100, "IfcAirTerminal": 30, "IfcSpace": 20}, "ventilation"),
        ({"IfcCableCarrierSegment": 50, "IfcLightFixture": 60, "IfcOutlet": 40}, "electrical"),
        # IFC2x3: generic flow occurrences follow the specific types
        ({"IfcFlowSegment": 400, "IfcFlowTerminal": 50, "IfcLightFixtureType": 3}, "electrical"),
        ({"IfcBuilding": 40, "IfcWall": 10}, "site"),
    ],
)
def test_census_ranks_the_discipline_the_classes_tell(counts: dict[str, int], top: str) -> None:
    assert _top(counts) == top


def test_census_shares_add_up_and_a_model_carries_several() -> None:
    ranked = discipline_from_census(
        {"IfcPipeSegmentType": 10, "IfcSanitaryTerminalType": 5, "IfcDuctSegmentType": 5}
    )
    assert [d for d, _ in ranked] == ["plumbing", "ventilation"]
    assert sum(share for _, share in ranked) == pytest.approx(1.0)


def test_a_census_with_nothing_telling_says_nothing() -> None:
    assert discipline_from_census({"IfcCartesianPoint": 900, "IfcBuildingElementProxy": 4}) == []


@pytest.mark.parametrize(
    ("question", "discipline", "system"),
    [
        ("What is the total length of water supply piping?", "plumbing", "cold_water"),
        ("What water heating systems are installed?", "plumbing", "hot_water"),
        ("What types of heat recovery units are used?", "ventilation", None),
        ("How long are the supply air ducts on level 2?", "ventilation", "supply_air"),
        ("Wie lang sind die Heizungsrohre im EG?", "heating", "heating"),
        ("Kuinka monta valaisinta on 2. kerroksessa?", "electrical", None),
        ("Are the interior walls load bearing?", "structural", None),
        ("What pipe fitting types are installed?", "plumbing", None),
        ("Which column types are present?", "structural", None),
        ("What is the net floor area of the room 'X' on 'EG', in m²?", "architecture", None),
        ("Hoeveel deuren zijn er op de begane grond?", "architecture", None),
        ("Which MEP systems are installed?", None, None),
        ("How long are the heating and ventilation ducts?", None, "heating"),
        ("Is fire rating information available for windows?", "architecture", None),
        ("What is the project's name?", None, None),
    ],
)
def test_question_discipline_and_system(
    question: str, discipline: str | None, system: str | None
) -> None:
    assert discipline_from_question(question) == discipline
    assert system_from_question(question) == system


@pytest.mark.parametrize(
    ("title", "discipline"),
    [
        ("LVI IV-101 Tasokuva 1. krs", "ventilation"),
        ("ARK pohjapiirustus 1. kerros", "architecture"),
        ("Grundriss EG Heizung", "heating"),
        ("E-201 Lighting plan level 2", "electrical"),
        ("S-101 Foundation plan", "structural"),
        ("HLKS Grundriss OG", "architecture"),  # mixed services: only the floor plan words count
        ("Sheet 3", None),
        ("Heizung und Lüftung EG", None),
    ],
)
def test_title_discipline(title: str, discipline: str | None) -> None:
    assert discipline_from_title(title) == discipline


def test_sheet_kind_reply_gives_the_discipline_without_a_new_call() -> None:
    assert discipline_from_sheet("structural_plan", None, None) == "structural"
    assert discipline_from_sheet("mep_plan", "Sanitär Grundriss EG", None) == "plumbing"
    assert discipline_from_sheet("mep_plan", "Grundriss EG", None) is None
    assert discipline_from_sheet("mep_plan", "PIPING PLAN", "M-101A") is None
    assert discipline_from_sheet("mep_plan", "HVAC services plan", None) is None
    assert discipline_from_sheet("mep_plan", "IV-pohja 1. krs", "IV-101") == "ventilation"
    assert discipline_from_sheet("mep_plan", "Heating and ventilation", None) is None
    assert discipline_from_sheet("architectural_floor_plan", "Heizung EG", None) == "heating"
    assert discipline_from_sheet("architectural_floor_plan", None, "A-101") == "architecture"
    assert discipline_from_sheet("detail", None, None) is None
    # weak title words do not override the kind: a post office, a pump house are floor plans
    kind = "architectural_floor_plan"
    assert discipline_from_sheet(kind, "POST OFFICE - FIRST FLOOR PLAN", None) == "architecture"
    assert discipline_from_sheet(kind, "PUMP HOUSE FLOOR PLAN", None) == "architecture"


@pytest.mark.parametrize(
    ("kind", "title", "number", "discipline"),
    [
        # weak words never pick a discipline on their own, even when the kind says nothing
        ("detail", "POST OFFICE DETAIL", None, None),
        ("detail", "PUMP HOUSE DETAIL", None, None),
        ("detail", "Heizung Detail", None, "heating"),
        ("detail", "Detail 4", "S-301", "structural"),
        # a service room on a floor plan names a room, not a service drawing
        ("architectural_floor_plan", "ELECTRICAL ROOM - FLOOR PLAN", None, "architecture"),
        ("architectural_floor_plan", "Plant room and boiler room", None, "architecture"),
        ("architectural_floor_plan", "Sähköhuone 1. krs", None, "architecture"),
        ("architectural_floor_plan", "Elektroraum EG", None, "architecture"),
        # ... but the room does not hide a service the title also names, nor a sheet code
        ("architectural_floor_plan", "HEATING PLAN - BOILER ROOM", None, "heating"),
        ("architectural_floor_plan", "ELECTRICAL ROOM", "E-101", "electrical"),
    ],
)
def test_only_strong_words_or_codes_name_a_sheet_discipline(
    kind: str, title: str, number: str | None, discipline: str | None
) -> None:
    assert discipline_from_sheet(kind, title, number) == discipline
