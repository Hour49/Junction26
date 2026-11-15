"""A floor-naming question on a picture whose reading has no floor (pic-reg, 2026-11-15, live
pics-digitalhub: "How many radiators are on the ground floor?" on H-101 answered "No storey
'ground floor' in this file; it has 0 storeys: none." though the picture counted 29). The floor
comes from the file name as pairing reads it (E00 is the ground floor); never from a sheet number
("H-101" is no floor 101)."""

from app.core.answering.facts import FACTS, answer_from_facts
from app.core.answering.model import Answer, Question
from app.core.ifc_facts import FactSheet, Spot
from app.core.picture_facts import Checked, LegendEntry, PictureReading, Sighting, picture_facts

H101 = "set/H-101 E00 heating.png"
LEGEND = (LegendEntry(label="Radiator", group="Heating", line=False, box=(0.8, 0.1, 0.82, 0.12)),)


def sheet() -> FactSheet:
    """Six radiators read off a picture whose reading names no floor."""
    spots = [
        Spot(page=1, box=(0.1 * i, 0.5, 0.1 * i + 0.01, 0.51), reader="template") for i in range(6)
    ]
    reading = PictureReading(
        reader="template",
        legend=LEGEND,
        read=("Radiator",),
        storey=None,
        sightings=tuple(Sighting(label="Radiator", spot=spot) for spot in spots),
    )
    return picture_facts("d1", Checked(readings=(reading,), agreed={}, disputed=()))


def ask(text: str, file: str = H101) -> Answer:
    answer = answer_from_facts(Question(id=1, file=file, text=text), sheet(), 0.0)
    assert answer is not None, text
    return answer


def said(answer: Answer) -> str:
    return f"{answer.answer} {answer.explanation}"


def test_the_floor_its_file_name_names_answers_from_the_picture() -> None:
    answer = ask("How many radiators are on the ground floor?")
    assert answer.method == FACTS and answer.sure is False  # Low, never certified
    assert "6" in str(answer.answer) and "E00 by its file name" in str(answer.answer)
    assert len(answer.evidence) == 6


def test_another_floor_is_refused_saying_which_floor_the_picture_is() -> None:
    answer = ask("How many radiators are on the first floor?")
    assert answer.answer is None and answer.abstain is True and answer.method.startswith("refused")
    assert "E00" in said(answer) and "storeys: none" not in said(answer)


def test_a_picture_whose_floor_is_not_stated_is_refused_saying_so() -> None:
    answer = ask("How many radiators are on the ground floor?", file="set/heating scan.png")
    assert answer.answer is None and answer.abstain is True
    assert "floor is not stated" in said(answer) and "storeys: none" not in said(answer)


def test_a_sheet_number_is_no_floor() -> None:
    """storey_number("H-101 E00") is 101: the file's floor is E00, the ground floor, not 101."""
    assert ask("How many radiators are on floor 101?").abstain is True
