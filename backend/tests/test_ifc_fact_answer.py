"""Answers from an IFC model's fact sheet: the text the facts give, the fallback in answer.py,
and the adapter that builds a sheet from a (synthetic) IFC file."""

from pathlib import Path

from app.adapters.ifc_model import facts_source
from app.adapters.ifc_model.facts_source import IfcFactSource
from app.core.answering.answer import answer_question
from app.core.answering.facts import FACTS, FirstSheet, answer_from_facts, fact_text
from app.core.answering.model import Prior, Query, Question, Unsupported
from app.core.ifc_facts import Fact, FactSheet
from app.core.ifc_question import parse_ifc_question
from tests.ifc_models import IfcFile, box

FILE = "data/ifc_bench/sample_arc.ifc"


def fact(
    topic: str, subject: str, value: float | str, unit: str | None, storey: str | None = None
) -> Fact:
    return Fact(
        topic=topic,
        subject=subject,
        value=value,
        unit=unit,
        storey=storey,
        discipline="architecture",
        source="test",
    )


SHEET = FactSheet(
    model="sample_arc",
    disciplines=["architecture"],
    facts=[
        fact("project.software", "project", "Modeller 9", None),
        fact("project.schema", "project", "IFC4", None),
        fact("storey.elevation", "EG", 0.0, "m", storey="EG"),
        fact("storey.elevation", "1.OG", 3.0, "m", storey="1.OG"),
        fact("storey.height", "EG", 3.0, "m", storey="EG"),
        fact("space.long_name", "001", "Kitchen", None, storey="EG"),
        fact("space.long_name", "002", "Bedroom", None, storey="EG"),
        fact("space.long_name", "101", "Bedroom", None, storey="1.OG"),
        fact("space.stated_area", "001", 12.5, "m2", storey="EG"),
        fact("space.stated_area", "002", 14.0, "m2", storey="EG"),
        fact("space.stated_area", "101", 16.25, "m2", storey="1.OG"),
        fact("space.stated_area", "all", 42.75, "m2"),  # a sum, not a space
        fact("space.stated_area", "all", 26.5, "m2", storey="EG"),
        fact("space.count", "all", 2, "count", storey="EG"),
        fact("space_function.count", "Bedroom", 2, "count"),
        fact("space_function.stated_area", "Bedroom", 30.25, "m2"),
        fact("wall.count", "all", 5, "count"),
        fact("wall.count", "external", 3, "count"),
        fact("wall.count", "internal", 2, "count"),
        fact("wall.length", "all", 20.0, "m"),
        fact("wall.length", "external", 14.0, "m"),
        fact("wall_type.count", "Brick 300", 3, "count"),
        fact("wall_type.count", "Plaster 100", 2, "count"),
        fact("wall_type.count", "Basic Wall:Plaster 100", 2, "count"),  # Revit's Family:Type
        fact("wall_type.count", "Brick 300 | external", 3, "count"),
        fact("wall_type.count", "Plaster 100 | internal", 2, "count"),
        fact("wall_type.thickness", "Brick 300", 0.3, "m"),
        fact("wall.thickness", "W7", 0.3, "m", storey="EG"),
        fact("slab.count", "all", 2, "count"),
        fact("covering.count", "all", 0, "count"),
        fact("window.count", "all", 4, "count"),
        fact("window_type.count", "W1", 4, "count"),
        fact("window_type.fire_rated_count", "W1", 0, "count"),
        fact("wall.volume", "external", 20.0, "m3"),
        fact("wall.volume.by_material_kind", "insulation", 2.0, "m3"),
        fact("wall.volume.by_material_kind", "masonry", 9.0, "m3"),
        fact("wall.count.by_material_kind", "masonry", 3, "count"),
        fact("wall.count.by_material_kind", "concrete", 3, "count"),
        fact("space.height", "002", 2.6, "m", storey="EG"),
        fact("footing.count", "all", 3, "count"),
        fact("foundation.volume.total", "all", 12.5, "m3"),
        fact("heat_exchanger.count", "all", 3, "count"),
        fact("heat_exchanger.count_in_space", "002", 2, "count"),
        fact("heat_exchanger.space", "Radiator:600:11", "002", None, storey="EG"),
        fact("heat_exchanger.space", "Radiator:600:12", "002", None, storey="EG"),
        fact("heat_exchanger.space", "Radiator:600:13", "101", None, storey="1.OG"),
        fact("slab.volume.by_material_kind", "concrete", 30.0, "m3"),
        fact("slab.volume.by_material_kind", "timber", 4.0, "m3"),
        fact("wall.thickness", "W8", 0.1, "m", storey="EG"),
        fact("wall.type", "W7", "Brick 300", None, storey="EG"),
        fact("wall_type.layer", "Brick 300 | layer 1 | Brick", 0.25, "m"),
        fact("wall_type.layer", "Brick 300 | layer 2 | Plaster", 0.05, "m"),
    ],
)


def text(question: str) -> str:
    query = parse_ifc_question(question)
    assert query is not None
    said = fact_text(query, SHEET)
    assert said is not None
    return said


def test_every_number_is_a_fact() -> None:
    said = text("What is the total length of the exterior walls?")
    assert "Total external walls: 3" in said
    assert "Total length: 14.00 m" in said


def test_types_of_a_part_count_that_part_only() -> None:
    said = text("Which wall types are used on the exterior, with their quantities?")
    assert "- Brick 300: 3 (100.0%)" in said
    assert "Plaster 100" not in said


def test_layers_are_listed_in_order_in_both_units() -> None:
    said = text("What materials are the wall types made of?")
    assert "1. Brick: 250 mm (0.25 m)" in said
    assert "2. Plaster: 50 mm (0.05 m)" in said


def test_spaces_of_a_storey_by_the_storey_the_question_names() -> None:
    said = text("What are the spaces on the ground floor, with their areas?")
    assert (
        "Spaces on Ground floor (EG): 2 spaces, total area 26.50 m²" in said
    )  # the facts' own sums
    assert "Kitchen (Space 001): 12.50 m²" in said
    assert "101" not in said


def test_spaces_named_by_their_use() -> None:
    said = text("How many bedrooms are there?")
    assert "Bedroom: 2 spaces, total area 30.25 m²" in said  # the function's own facts
    assert "Kitchen" not in said
    assert said.startswith("Spaces matching 'bedrooms': 2")


def test_a_storey_the_model_lacks_is_said() -> None:
    assert text("Which spaces are on level 7?").startswith("No storey 'level 7'")


def test_what_the_model_lacks_is_not_available() -> None:
    assert "not available" in text("What is the warranty of the windows?")
    assert text("How many beams are there?").startswith("No beams found in this file")
    said = text("How many electrical components are there?")
    assert said.startswith("This file holds no electrical elements")


def test_each_measure_is_said_once_per_type() -> None:
    said = text("What are the thicknesses and sizes of the wall types?")
    assert said.count("thickness 300 mm") == 1


def test_a_split_says_what_it_is_of() -> None:
    said = text("What percentage of the walls are external?")
    assert "Of all 5 walls: external: 3 (60.0%); internal: 2 (40.0%)" in said


def test_the_largest_names_the_element_and_its_type() -> None:
    said = text("What is the maximum wall thickness?")
    assert "largest 300 mm (0.30 m) (W7, Brick 300)" in said


def test_yes_no() -> None:
    assert text("Are the internal walls external?").startswith("Yes.")  # the sheet counts them
    said = text("Are the internal walls load-bearing?")  # it states no load-bearing count
    assert said.startswith("The file does not say which walls are load-bearing (not available).")


def test_the_project() -> None:
    said = text("Which software and IFC schema were used?")
    assert "Modeller 9" in said
    assert "IFC4" in said


class NoPrior:
    def prior(self, source: str, family: str) -> Prior | None:
        return None


class Refuses:
    def parse(self, text: str) -> Unsupported:
        return Unsupported(reason="free text")


def test_the_fallback_answers_what_the_takeoff_cannot_never_sure() -> None:
    question = Question(id=3, file=FILE, text="How many walls are there?")
    ticks = iter(range(10))
    answer = answer_question(
        question, None, Refuses(), lambda: float(next(ticks)), NoPrior(), facts=lambda: SHEET
    )
    assert answer.method == FACTS
    assert isinstance(answer.answer, str) and "Total walls: 5" in answer.answer
    assert answer.sure is None and answer.confidence is None and answer.cost_usd == 0.0
    assert answer.latency_s == 1.0
    refused = answer_question(question, None, Refuses(), lambda: 0.0, NoPrior())
    assert refused.method == "refused:no-drawing"  # off: as before


class Counts:
    def parse(self, text: str) -> Query:
        return Query(subject="door")


class DoorPrior:
    def prior(self, source: str, family: str) -> Prior | None:
        return Prior(value=4, unit="count", confidence=0.3, n=10)


def test_the_dev_prior_comes_before_the_facts() -> None:
    question = Question(id=4, file=FILE, text="How many doors are there?")
    asked: list[int] = []

    def sheet() -> FactSheet:
        asked.append(1)
        return SHEET

    answer = answer_question(question, {}, Counts(), lambda: 0.0, DoorPrior(), facts=sheet)
    assert answer.answer == 4 and answer.abstain is True  # the prior's number, as before
    assert asked == []  # and the sheet was never built
    answer = answer_question(question, {}, Counts(), lambda: 0.0, NoPrior(), facts=sheet)
    assert answer.method == FACTS and asked == [1]  # no prior: the facts answer


def test_a_broken_fact_refuses_that_question_only() -> None:
    broken = FactSheet(
        model="x", disciplines=["architecture"], facts=[fact("wall.count", "all", "many", "count")]
    )
    question = Question(id=5, file=FILE, text="How many walls are there?")
    answer = answer_question(
        question, None, Refuses(), lambda: 0.0, NoPrior(), facts=lambda: broken
    )
    assert answer.method == "refused:no-drawing"


def test_no_rule_no_fact_answer() -> None:
    assert answer_from_facts(Question(id=1, file=FILE, text="Tell me a joke."), SHEET, 0.0) is None


class Files:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.reads = 0

    def read(self, path: str) -> bytes:
        self.reads += 1
        return self.files[path]


def synthetic() -> bytes:
    model = IfcFile()
    ground = model.storey("Level 0")
    model._file.by_guid(ground).Elevation = 0.0  # facts_arch needs an elevation (ifc-ask report)
    model.element("IfcWall", storey=ground, name="W1", quantities={"Length": 4.0})
    model.element("IfcWall", storey=ground, name="W2", quantities={"Length": 6.0})
    model.space(ground, "1", "Hall", (box(0, 0, 4, 5), 0.0, 2.5))
    return model.ifc()


def test_the_adapter_builds_a_sheet_once_and_keeps_it_on_disk(tmp_path: Path) -> None:
    files = Files({FILE: synthetic()})
    source = IfcFactSource(files, tmp_path)
    sheet = source.facts(FILE)
    assert sheet is not None and sheet.model == "sample_arc"
    query = parse_ifc_question("What is the total length of all walls?")
    assert query is not None
    said = fact_text(query, sheet)
    assert said is not None and "Total walls: 2" in said and "10.00 m" in said
    assert source.facts(FILE) is sheet and files.reads == 1
    again = IfcFactSource(files, tmp_path).facts(FILE)  # from the JSON, not the IFC
    assert again == sheet
    assert IfcFactSource(files).facts("data/x/plan.pdf") is None
    assert [p.suffix for p in tmp_path.iterdir()] == [".json"]  # written whole, no temp left


def test_a_cache_entry_of_older_code_or_broken_is_rebuilt(tmp_path: Path) -> None:
    files = Files({FILE: synthetic()})
    assert IfcFactSource(files, tmp_path).facts(FILE) is not None
    (kept,) = tmp_path.iterdir()
    assert facts_source.CODE in kept.name  # the fact code's version is in the key
    kept.write_text("{truncated", encoding="utf-8")  # a run killed mid-write, an old schema
    assert IfcFactSource(files, tmp_path).facts(FILE) is not None and files.reads == 2


def test_skirting_not_modelled_says_so_and_gives_the_estimate() -> None:
    sheet = SHEET.model_copy(
        update={
            "facts": [
                *SHEET.facts,
                fact("space.baseboard_length", "all", 41.2, "m"),
                fact("space.baseboard_length", "all", 30.0, "m", storey="EG"),
            ]
        }
    )
    query = parse_ifc_question("How many metres of skirting boards do the rooms need?")
    assert query is not None and query.entity == "baseboard"
    said = fact_text(query, sheet)
    assert said is not None
    assert said.startswith("Skirting boards are not modelled in this file")
    assert "not available in the BIM model" in said
    assert "wet rooms excluded: 41.20 m" in said and "- EG: 30.00 m" in said


def test_skirting_modelled_is_read_as_modelled() -> None:
    sheet = SHEET.model_copy(
        update={"facts": [*SHEET.facts, fact("covering.skirting_length", "all", 12.0, "m")]}
    )
    query = parse_ifc_question("What is the total length of the skirting?")
    assert query is not None
    assert fact_text(query, sheet) == "Skirting boards modelled in this file: length: 12.00 m"


def test_the_first_source_with_a_sheet_wins() -> None:
    class Fixed:
        def __init__(self, sheet: FactSheet | None) -> None:
            self.sheet = sheet

        def facts(self, file: str) -> FactSheet | None:
            return self.sheet

    other = SHEET.model_copy(update={"model": "other"})
    assert FirstSheet([Fixed(None), Fixed(SHEET), Fixed(other)]).facts(FILE) == SHEET
    assert FirstSheet([Fixed(None)]).facts(FILE) is None


def test_a_type_under_two_names_is_listed_once_by_its_family_name() -> None:
    said = text("Which wall types are there?")
    assert "- Basic Wall:Plaster 100: 2 (40.0%)" in said
    assert "- Plaster 100:" not in said
    assert said.count("\n- ") == 2


def test_a_part_the_file_does_not_mark_is_said_then_all() -> None:
    said = text("How many load-bearing slabs are there?")
    assert said.startswith("The file does not say which slabs are load-bearing (not available).")
    assert "Total slabs: 2" in said


def test_a_material_the_question_names_gets_its_split() -> None:
    said = text("What is the volume of concrete in the slabs?")
    assert "- concrete: volume 30.00 m³" in said and "timber" not in said


def test_storeys_are_named_by_their_level_and_the_files_name() -> None:
    assert "Spaces on Level 1 (1.OG):" in text(
        "What are all the spaces on level 1, with their areas?"
    )
    said = text("What is the space breakdown by level?")
    assert "Ground floor (EG):" in said and "\nLevel 1 (1.OG)\n" in said


def test_elements_in_a_space_the_question_names() -> None:
    said = text("How many radiators are there in room 002?")
    assert "In space 002: 2" in said and "Radiator:600:12" in said and "600:13" not in said


def test_a_ceiling_height_is_the_rooms_height() -> None:
    assert "Bedroom (Space 002): 14.00 m², height 2.60 m" in text(
        "What is the ceiling height in room 002?"
    )


def test_foundations_get_the_sheets_foundation_totals() -> None:
    assert "Foundations in all: volume 12.50 m³" in text("What is the volume of the foundations?")


def mep(topic: str, subject: str, value: float, unit: str | None = "count") -> Fact:
    return Fact(
        topic=topic, subject=subject, value=value, unit=unit, discipline="plumbing", source="t"
    )


MEP = FactSheet(
    model="demo_mep",
    disciplines=["plumbing", "ventilation"],
    facts=[
        mep("system.count", "all", 3),
        mep("system.count", "Cold Water", 2),
        mep("system.count", "Hot Water", 1),
        mep("port.count", "all", 40),
        mep("port.connected", "all", 30),
        mep("port.per_element", "all", 2.1, "ratio"),
        mep("element.count", "all", 21),
        mep("element.count", "typed", 19),
        mep("category.count", "Duct Accessories", 4),
        mep("category.count", "Ducts", 6),
        mep("category.count", "Mechanical Equipment", 2),
        mep("category.length", "Ducts", 10.0, "m"),
        mep("duct_segment.count", "all", 7),
        mep("duct_segment.count_by_shape", "round", 5),
        mep("duct_segment.length_per_storey", "all", 2.5, "m"),
    ],
)


def mep_text(question: str) -> str:
    query = parse_ifc_question(question)
    assert query is not None
    said = fact_text(query, MEP)
    assert said is not None
    return said


def test_systems_are_counted_per_type_with_the_stated_total() -> None:
    said = mep_text("What plumbing systems are there?")
    assert "Systems: 3" in said and "- Cold Water: 2 systems" in said


def test_connectivity_asks_the_ports() -> None:
    said = mep_text("What is the plumbing distribution network connectivity?")
    assert "Ports: 40\nConnected ports: 30\nNetwork connectivity rate: 75.0%" in said
    assert "ports per element: 2.1" in said and "elements with a type: 19" in said


def test_a_category_the_question_names_is_reported() -> None:
    said = mep_text("How many duct accessories are there?")
    assert "Duct Accessories (category): 4" in said


def test_the_sheets_aggregates_of_the_kind_asked() -> None:
    said = mep_text("How many ducts are there, by shape?")
    assert "Total duct segments: 7" in said
    assert "- round: 5 (71.4%)" in said and "length per storey: 2.50 m" in said
    assert "Ducts (category): 6, length 10.00 m" in said


def test_equipment_with_unit_counts_is_equipment_not_spaces() -> None:
    said = mep_text("What types of mechanical equipment are used, along with unit counts?")
    assert "Mechanical Equipment (category): 2" in said


def test_categories_give_their_share_of_the_typed_elements() -> None:
    said = mep_text("What plumbing components are there, by category?")
    assert "- Ducts: 6 (31.6%)" in said


def test_what_the_file_lacks_opens_with_no_or_says_not_available() -> None:
    assert text("What coverings are used in the building?").startswith("No coverings")
    said = text("What materials are used for the slabs?")
    assert "The file states no material for its slabs (not available)." in said
    said = text("Which window types have fire rating information?")
    assert "No window in this file has fire rating information (not available)." in said
    assert "not available" in mep_text("Which heating systems are installed?")


GLAZED = SHEET.model_copy(
    update={"facts": [*SHEET.facts, fact("window_type.material", "W1", "Glass, double", None)]}
)


def test_the_glazing_type_is_unavailable_only_when_no_window_fact_says_it() -> None:
    query = parse_ifc_question("Which type of glazing do the windows have?")
    assert query is not None
    assert "The file states no glazing for its windows (not available)." in (
        fact_text(query, SHEET) or ""
    )
    said = fact_text(query, GLAZED) or ""
    assert "Glass, double" in said and "not available" not in said


def test_material_lines_are_sorted() -> None:
    said = text("What materials are the walls made of?")
    assert said.index("- concrete: count 3") < said.index("- masonry: count 3")


def test_the_headline_is_the_asked_subject() -> None:
    said = text("What is the volume of insulation in the external walls?")
    assert said.startswith("Walls by material kind:\n- insulation: volume 2.000 m³")


def test_no_opens_only_when_the_sheet_lacks_the_thing_and_its_totals() -> None:
    sheet = FactSheet(
        model="m",
        disciplines=["structural"],
        facts=[
            fact("footing.count", "all", 0, "count"),
            fact("foundation.volume.total", "all", 9.0, "m3"),
        ],
    )
    query = parse_ifc_question("What is the volume of concrete in the foundation?")
    assert query is not None
    said = fact_text(query, sheet) or ""
    assert not said.startswith("No ") and "Foundations in all: volume 9.000 m³" in said
    assert "not available" not in said  # neither the volume of no footings nor their material
    assert not text("Can you provide an analysis of the structural components?").startswith("No")


def storeys(*placed: tuple[str, float]) -> FactSheet:
    facts = [fact("storey.elevation", name, at, "m", storey=name) for name, at in placed]
    facts += [
        fact("space.long_name", f"S{i}", "Office", None, storey=n)
        for i, (n, _) in enumerate(placed)
    ]
    return FactSheet(model="m", disciplines=["architecture"], facts=facts)


def storey_text(question: str, sheet: FactSheet) -> str:
    query = parse_ifc_question(question)
    assert query is not None
    return fact_text(query, sheet) or ""


def test_a_level_number_is_not_the_basements_minus_sign() -> None:
    sheet = storeys(("-1 Base", -1.0), ("00 Street", 0.0), ("01 Upper", 4.5))
    assert "Spaces on Level 1 (01 Upper)" in storey_text("Which spaces are on level 1?", sheet)


def test_the_ground_of_a_file_placed_above_a_datum_is_its_first_numbered_floor() -> None:
    sheet = storeys(("Footings", 10.0), ("Cellar", 13.0), ("1.et", 17.0), ("2.et", 20.0))
    said = storey_text("Which spaces are on the ground level?", sheet)
    assert "Spaces on Ground floor (1.et)" in said
    assert "Spaces on Ground floor (1.et)" in storey_text("Which spaces are on level 1?", sheet)
    said = storey_text("Which spaces are in the underground level?", sheet)
    assert "(Cellar)" in said  # the storey named a basement, not the footings below it


def test_a_storey_the_file_lacks_gives_the_count_of_its_storeys() -> None:
    sheet = storeys(("GROUND FLOOR", 0.0), ("FIRST FLOOR", 4.0))
    said = storey_text("Which spaces are in the basement?", sheet)
    assert said.startswith("No storey 'basement' in this file; it has 2 storeys: GROUND FLOOR")


LEVELS = FactSheet(
    model="m",
    disciplines=["architecture"],
    facts=[
        *storeys(("A", 0.0), ("B", 3.0), ("C", 6.0)).facts[:3],
        fact("space.long_name", "S1", "Office", None, storey="A"),
        fact("space.long_name", "S2", "Office", None, storey="B"),
        fact("building.gross_floor_area", "Building", 100.0, "m2"),
        fact("storey.gross_floor_area", "A", 60.0, "m2", storey="A"),
        fact("storey.gross_floor_area", "B", 40.0, "m2", storey="B"),
        fact("furniture.count", "all", 2, "count"),
        fact("furniture.count", "all", 2, "count", storey="A"),
        fact("furniture_type.count", "Desk", 2, "count"),
        fact("space.stated_area", "S1", 30.0, "m2", storey="A"),
        fact("space.stated_area", "S2", 10.0, "m2", storey="B"),
        fact("space.stated_area", "all", 40.0, "m2"),
        fact("space.stated_area", "all", 30.0, "m2", storey="A"),
        fact("space.stated_area", "all", 10.0, "m2", storey="B"),
    ],
)


def test_a_breakdown_by_level_counts_the_storeys_and_says_the_empty_ones() -> None:
    said = storey_text("What is the space breakdown by level?", LEVELS)
    assert "Spaces on 2 of the file's 3 storeys" in said
    assert "Level 2 (C): 0 spaces" in said
    said = storey_text("How many furniture items are there per floor?", LEVELS)
    assert "- Ground floor (A): 2" in said and "- Level 1 (B): 0" in said


def test_the_gross_floor_area_is_given_per_storey_with_its_share() -> None:
    said = storey_text("What is the building's total gross floor area?", LEVELS)
    assert "Building gross floor area: 100.00 m²" in said
    assert "- Ground floor (A): 60.00 m² (60.0%)" in said


def test_a_storeys_area_gets_its_share_of_the_buildings() -> None:
    said = storey_text("What is the floor area by level?", LEVELS)
    assert "Ground floor (A): total 30.00 m² (75.0%)" in said


def electrical(topic: str, subject: str, value: int, storey: str | None = None) -> Fact:
    return Fact(
        topic=topic,
        subject=subject,
        value=value,
        unit="count",
        storey=storey,
        discipline="electrical",
        source="t",
    )


WIRED = FactSheet(
    model="m",
    disciplines=["electrical"],
    facts=[
        *storeys(("A", 0.0), ("B", 3.0)).facts[:2],
        electrical("element.count", "typed", 10),
        electrical("element.count", "typed", 4, "A"),
        electrical("element.count", "typed", 6, "B"),
        electrical("category.count", "Conduits", 7),
        electrical("category.count", "Conduits", 3, "A"),
        electrical("category.count", "Lighting Fixtures", 1, "A"),
        electrical("category.count", "Conduits", 4, "B"),
        electrical("category.count", "Lighting Fixtures", 2, "B"),
        electrical("light_fixture.count", "all", 3),
        mep("category.count", "Pipes", 1).model_copy(update={"storey": "B"}),
    ],
)


def test_electrical_components_by_level_give_each_storeys_categories_and_share() -> None:
    said = storey_text(
        "What is the distribution of electrical components by building level?", WIRED
    )
    assert "Ground floor (A): 4 components (40.0% of 10)" in said
    assert "  - Conduits: 3 (75.0%)" in said and "  - Conduits: 4 (66.7%)" in said
    said = storey_text("What is the electrical equipment distribution in level 1?", WIRED)
    assert said.startswith("Level 1 (B): 6 components (60.0% of 10)")
    assert "- Pipes: 1 (16.7%)" in said  # of all the storey's typed elements, whatever discipline
