"""A picture's own legend rows answer a fixture or symbol the question names (QA big services R1,
P4/P8/P9, 2026-11-15): the lane read 6 urinals, 4 washbasins and 5 Brandschutzklappe, but
"urinals" and "washbasins" were no question words, and a fire damper, a legend row no kind
names, is kept as a symbol, so "fire dampers" said "its legend lists no dampers". The count is
the rows whose label names it; a fixture's mounting frame ("Viega ... Urinal-Element") is its
own row of the same fixtures and is not added to it. Never sure, as every picture count."""

from app.core.answering.facts import FACTS, answer_from_facts
from app.core.answering.model import Answer, Question
from app.core.ifc_facts import Fact, FactSheet, Spot
from app.core.picture_facts import Checked, LegendEntry, PictureReading, Sighting, picture_facts

PLUMBING = {  # P-101 / E01 plumbing as the lane read them live (kept sheets bc2a7402, 6859e9df)
    "Urinal UP Druckspüler:Standard": 6,
    "Viega Eco Plus-Urinal-Element, 1130 mm Viega 461843 #davpn1i#:Standard": 6,
    "Waschtisch:60 x 60cm": 4,
    "Viega Eco-Waschtisch-Element, 1130x490 Viega 670986 #33o1lvo#:Standard": 4,
    "WC UP-Spülkasten Betätigung vorne:35 x 60cm": 8,
}
VENTILATION = {  # the ventilation photo (kept sheet fe8619fa)
    "Brandschutzklappe rechteck Flansch:Standard": 5,
    "Schlitzdurchlass Zuluft Decke:1200mm, DN 123": 35,
}


def sheet(rows: dict[str, int], storey: str | None = None) -> FactSheet:
    legend = tuple(
        LegendEntry(label=label, group=None, line=False, box=(0.9, 0.05 * i, 0.92, 0.05 * i + 0.01))
        for i, label in enumerate(rows)
    )
    sightings = tuple(
        Sighting(
            label=label,
            spot=Spot(
                page=1,
                box=(0.01 * j, 0.1 * i, 0.01 * j + 0.005, 0.1 * i + 0.005),
                reader="template",
            ),
        )
        for i, (label, n) in enumerate(rows.items())
        for j in range(n)
    )
    reading = PictureReading(
        reader="template", legend=legend, read=tuple(rows), storey=storey, sightings=sightings
    )
    return picture_facts("d1", Checked(readings=(reading,), agreed={}, disputed=()))


def ask(text: str, rows: dict[str, int], file: str = "set/P-101 plumbing.png") -> Answer:
    answer = answer_from_facts(Question(id=1, file=file, text=text), sheet(rows), 0.0)
    assert answer is not None, text
    return answer


def test_urinals_are_the_rows_naming_urinals_without_their_mounting_frames() -> None:
    answer = ask("How many urinals are on P-101?", PLUMBING)
    assert answer.method == FACTS and answer.sure is False, answer
    said = str(answer.answer)
    assert said.startswith("Total urinals: 6\n"), said
    assert "Urinal UP Druckspüler:Standard: 6" in said
    assert "Not added" in said and "Urinal-Element" in said  # the frame is named, not counted
    assert len(answer.evidence) == 6  # the urinals' own spots, not the frames'


def test_washbasins_one_word_or_two() -> None:
    for text in ("How many washbasins are there?", "How many wash basins are there?"):
        answer = ask(text, PLUMBING)
        assert answer.method == FACTS and answer.sure is False, answer
        assert str(answer.answer).startswith("Total washbasins: 4\n"), answer.answer
        assert len(answer.evidence) == 4


def test_fire_dampers_are_the_symbol_rows_naming_them() -> None:
    for text in ("How many fire dampers are there?", "How many dampers are there?"):
        answer = ask(text, VENTILATION, file="set/L-101 ventilation.jpg")
        assert answer.method == FACTS and answer.sure is False, answer
        said = str(answer.answer)
        assert "5" in said.splitlines()[0] and "dampers" in said.splitlines()[0], said
        assert "Brandschutzklappe rechteck Flansch:Standard: 5" in said
        assert len(answer.evidence) == 5


def test_a_subject_the_legend_does_not_name_is_refused() -> None:
    answer = ask("How many urinals are there?", {"Waschtisch:60 x 60cm": 4})
    assert answer.answer is None and answer.abstain is True and answer.method == "refused:not-read"
    assert "lists no urinals" in str(answer.explanation)
    # a damper that is no fire damper is not one: "fire" must be named too
    answer = ask("How many fire dampers are there?", {"Volumenstromregler Klappe:DN 200": 3})
    assert answer.answer is None and answer.abstain is True and answer.method == "refused:not-read"


def test_a_building_model_s_urinals_are_its_urinal_type() -> None:
    """The same words on an IFC model read its PredefinedType, never the class's total."""

    def count(topic: str, subject: str, n: int) -> Fact:
        return Fact(topic=topic, subject=subject, value=n, unit="count", discipline="plumbing",
                    source="IfcSanitaryTerminal")  # fmt: skip

    facts = [
        count("sanitary_terminal.count", "all", 10),
        count("sanitary_terminal.count_by_predefined_type", "URINAL", 3),
        count("sanitary_terminal.count_by_predefined_type", "WASHHANDBASIN", 4),
    ]
    model = FactSheet(model="m1", disciplines=["plumbing"], facts=facts)
    for text, kind in (("How many urinals are there?", "URINAL 3"),
                       ("How many washbasins are there?", "WASHHANDBASIN 4")):  # fmt: skip
        answer = answer_from_facts(Question(id=1, file="m.ifc", text=text), model, 0.0)
        assert answer is not None and kind in str(answer.answer), (text, answer)
        assert answer.sure is None


def test_a_reading_s_storey_copies_are_not_counted_twice() -> None:
    """picture_facts lists every count sheet-wide and again for the storey the reading names."""
    floored = sheet(PLUMBING, storey="2ND FLOOR")
    for text in ("How many urinals are there?", "How many urinals are on floor 2?"):
        answer = answer_from_facts(Question(id=1, file="set/P-101.png", text=text), floored, 0.0)
        assert answer is not None and answer.sure is False, text
        assert "Total urinals: 6\n" in str(answer.answer), (text, answer.answer)
