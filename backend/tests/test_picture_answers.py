"""A question answered from a picture's fact sheet (discipline-pictures.md, Outputs and AC-5/AC-7
as the answer path reads them): counts and run lengths of the sheet, by its storey, with the
spots as the answer's evidence; never sure; a class not looked for is refused, not 0."""

from app.core.answering.facts import FACTS, GRAPH_SPREAD, MASK_SPREAD, NOT_READ, answer_from_facts
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


# P-101 E00 plumbing (pics-digitalhub.zip), as the live lane read it at 05:12: four line styles, no
# legend groups, the mask reader's lengths (pics-runs.md "Live run lengths")
P101 = {"S_PWC": 18.863, "S_PWH_": 1.797, "S_Regenwasser": 16.403, "S_Schmutzwasser": 31.41}


def _p101(reader: str = "mask") -> FactSheet:
    legend = tuple(
        LegendEntry(label=label, group=None, line=True, box=(0.8, 0.1 * i, 0.85, 0.1 * i + 0.01))
        for i, label in enumerate(P101)
    )
    runs = PictureReading(
        reader=reader, legend=legend, read=tuple(P101),
        runs=tuple(Run(label=label, size=None, length_m=metres, spots=(_spot(i, reader),))
                   for i, (label, metres) in enumerate(P101.items())),
    )  # fmt: skip
    return picture_facts("p101", Checked(readings=(runs,), agreed={}, disputed=()), "plumbing")


def _ask_p101(text: str, reader: str = "mask") -> Answer:
    answer = answer_from_facts(Question(id=1, file="P-101.png", text=text), _p101(reader), 0.0)
    assert answer is not None, text
    return answer


def test_a_question_naming_a_system_gets_that_systems_length_never_the_sheet_total() -> None:
    """Orchestrator 05:40: on the live P-101 sheet "How long is the rainwater pipe run?" answered
    "Total length: 68.47 m", the sum of all four systems."""
    rain = _ask_p101("How long is the rainwater pipe run?")
    said = str(rain.answer)
    assert said.startswith("S_Regenwasser: 16.40 m") and "68.47" not in said, said
    assert [e.box for e in rain.evidence] == [_spot(2, "mask").box]  # its own run's spot only
    said = str(_ask_p101("What is the total length of the wastewater pipes?").answer)
    assert said.startswith("S_Schmutzwasser: 31.41 m") and "68.47" not in said, said


def test_lengths_per_system_list_each_system() -> None:
    said = str(_ask_p101("What is the total pipe length per system?").answer)
    assert said.splitlines()[:5] == [
        "- S_PWC: 18.86 m",
        "- S_PWH_: 1.80 m",
        "- S_Regenwasser: 16.40 m",
        "- S_Schmutzwasser: 31.41 m",
        "Total length: 68.47 m",
    ], said


def test_a_system_no_run_is_labelled_as_is_said_with_the_runs_there_are() -> None:
    said = str(_ask_p101("How long are the gas pipes?").answer)
    assert said.splitlines()[0] == (
        "No run on this sheet is labelled as gas (not available); its runs by system:"
    ), said
    assert "- S_PWC: 18.86 m" in said and "Total length" not in said


def test_cold_and_hot_water_find_the_en_806_pwc_and_pwh_runs() -> None:
    """pics-runs.md known gap: on the live P-101 "cold water" was said not labelled though S_PWC
    is the potable water cold run (EN 806 PWC; PWH hot). Truth from the model: PWC 18.97 m."""
    cold = str(_ask_p101("How long are the cold water pipes?").answer)
    assert cold.startswith("S_PWC: 18.86 m") and "not available" not in cold, cold
    hot = str(_ask_p101("What is the length of the hot water pipes?").answer)
    assert hot.startswith("S_PWH_: 1.80 m") and "not available" not in hot, hot


def test_a_picture_length_says_it_is_an_estimate_with_the_readers_measured_spread() -> None:
    """Orchestrator 05:40 (2): a deterministic sentence; still Low (method facts, never sure)."""
    mask = _ask_p101("What is the total length of the pipes?")
    assert str(mask.answer).splitlines()[-1] == MASK_SPREAD and mask.sure is False
    assert "18 of 32 clean" in MASK_SPREAD and "0 of 32 scanned" in MASK_SPREAD
    graph = str(_ask_p101("How long is the rainwater pipe run?", reader="graph").answer)
    assert graph.splitlines()[-1] == GRAPH_SPREAD and "21 of 32 clean" in GRAPH_SPREAD
    exact = str(_ask_p101("How long is the rainwater pipe run?", reader="paths").answer)
    assert exact == "S_Regenwasser: 16.40 m"  # a drawn PDF's lines: read exactly, no estimate


def test_heating_pipe_on_a_heating_sheet_whose_styles_name_no_system_is_all_its_runs() -> None:
    """review-652 M1: DigitalHub heating styles (flow/return) carry no system word, so "heating
    pipe" was answered "No run ... labelled as heating"; main gave the total. Heating is the
    sheet's whole discipline, so every run is meant. "Cold water" on plumbing is not (P-101)."""
    styles = {"H_Transport_VL_": 237.6, "H_Transport_RL_": 229.8}
    legend = tuple(
        LegendEntry(label=label, group=None, line=True, box=(0.8, 0.1 * i, 0.85, 0.1 * i + 0.01))
        for i, label in enumerate(styles)
    )
    runs = PictureReading(
        reader="mask", legend=legend, read=tuple(styles),
        runs=tuple(Run(label=label, size=None, length_m=metres, spots=(_spot(i, "mask"),))
                   for i, (label, metres) in enumerate(styles.items())),
    )  # fmt: skip
    sheet = picture_facts("dh", Checked(readings=(runs,), agreed={}, disputed=()), "heating")
    question = Question(id=1, file="H.png", text="How many metres of heating pipe are there?")
    answer = answer_from_facts(question, sheet, 0.0)
    said = str(answer and answer.answer)
    assert said.splitlines()[:3] == [
        "- H_Transport_RL_: 229.80 m",
        "- H_Transport_VL_: 237.60 m",
        "Total length: 467.40 m",
    ], said
    assert "not available" not in said
