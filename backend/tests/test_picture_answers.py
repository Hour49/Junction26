"""A question answered from a picture's fact sheet (discipline-pictures.md, Outputs and AC-5/AC-7
as the answer path reads them): counts and run lengths of the sheet, by its storey, with the
spots as the answer's evidence; never sure; a class not looked for is refused, not 0."""

from app.core.answering.facts import FACTS, NOT_READ, answer_from_facts
from app.core.answering.model import Answer, Question
from app.core.ifc_facts import FactSheet, Spot
from app.core.picture_facts import (
    Checked,
    LegendEntry,
    PictureReading,
    Run,
    Sighting,
    picture_facts,
)

LEGEND = (
    LegendEntry(label="Radiator", group="Heating", line=False, box=(0.8, 0.1, 0.82, 0.12)),
    LegendEntry(label="Heating pipe DN20", group="Heating", line=True, box=(0.8, 0.2, 0.85, 0.21)),
)


def _spot(i: int, reader: str = "template") -> Spot:
    return Spot(page=1, box=(0.1 * i, 0.5, 0.1 * i + 0.01, 0.51), reader=reader)


def _sheet(storey: str | None = "2nd floor") -> FactSheet:
    symbols = PictureReading(
        reader="template", legend=LEGEND, read=("Radiator",), storey=storey,
        sightings=tuple(Sighting(label="Radiator", spot=_spot(i)) for i in range(6)),
    )  # fmt: skip
    runs = PictureReading(
        reader="mask", legend=LEGEND, read=("Heating pipe DN20",), storey=storey,
        runs=(Run(label="Heating pipe DN20", size="DN20", length_m=3.0, spots=(_spot(7, "mask"),)),
              Run(label="Heating pipe DN20", size="DN20", length_m=2.5, spots=(_spot(8, "mask"),))),
    )  # fmt: skip
    return picture_facts("d1", Checked(readings=(symbols, runs), agreed={}, disputed=()))


def _ask(text: str, storey: str | None = "2nd floor") -> Answer:
    answer = answer_from_facts(Question(id=1, file="scan.png", text=text), _sheet(storey), 0.0)
    assert answer is not None, text
    return answer


def test_a_count_answers_from_the_picture_with_its_spots_and_is_never_sure() -> None:
    answer = _ask("How many radiators are there?")
    assert answer.method == FACTS and "6" in str(answer.answer)
    assert answer.sure is False
    assert len(answer.evidence) == 6 and {e.file for e in answer.evidence} == {"scan.png"}
    assert answer.evidence[0].page == 1 and answer.evidence[0].box == _spot(0).box


def test_the_sheet_s_storey_answers_a_storey_question() -> None:
    assert "6" in str(_ask("How many radiators on floor 2?").answer)
    unnamed = _ask("How many radiators are there?", storey=None)
    assert "6" in str(unnamed.answer)


def test_run_lengths_answer_by_kind_and_by_printed_size() -> None:
    answer = _ask("How many metres of heating pipe are there?")
    assert "5.50 m" in str(answer.answer) and len(answer.evidence) == 2
    assert "pipe segments: 0" not in str(answer.answer).lower()  # runs are not a count
    sized = str(_ask("What is the total length of DN20 pipe?").answer)
    assert sized.startswith("Length of DN20: 5.50 m"), sized


def test_a_class_the_picture_was_not_read_for_is_refused_not_zero() -> None:
    answer = _ask("How many sockets are there?")
    assert answer.answer is None and answer.abstain is True
    assert answer.method.startswith("refused") and NOT_READ in (answer.explanation or "")


def test_switches_answer_from_the_switching_devices_the_picture_counted() -> None:
    legend = (LegendEntry(label="M_Lighting Switches:Single Pole", group=None, line=False,
                          box=(0.8, 0.1, 0.82, 0.12)),)  # fmt: skip
    reading = PictureReading(
        reader="template", legend=legend, read=None,
        sightings=tuple(Sighting(label=legend[0].label, spot=_spot(i)) for i in range(6)),
    )  # fmt: skip
    sheet = picture_facts("d1", Checked(readings=(reading,), agreed={}, disputed=()))
    question = Question(id=1, file="scan.png", text="How many switches are there?")
    answer = answer_from_facts(question, sheet, 0.0)
    assert answer is not None and answer.method == FACTS and "6" in str(answer.answer), answer
