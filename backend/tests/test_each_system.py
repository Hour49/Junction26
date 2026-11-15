"""Big QA R2 services-second N1 (2026-11-15): on the P-101 plumbing picture "How long is each pipe
system on P-101?" answered only the sheet total, and "How long is each plumbing system?" said
"This file holds no systems", though the sheet lists four. A picture's systems are its runs, so
a length asked per system is their length by system. An IFC model answers from its systems' own
facts as before (review-737 M1: "the heating system" of the sanitary model is no plumbing pipe)."""

import hashlib
from pathlib import Path

import pytest

from app.adapters.ifc_model.facts_source import CODE
from app.core.answering.facts import FACTS, answer_from_facts
from app.core.answering.model import Question
from app.core.ifc_facts import FactSheet, Spot
from app.core.picture_facts import (
    Checked,
    LegendEntry,
    PictureReading,
    Run,
    Sighting,
    picture_facts,
)
from tests.test_picture_answers import _ask_p101, _p101

PER_SYSTEM = [
    "- S_PWC: 18.86 m",
    "- S_PWH_: 1.80 m",
    "- S_Regenwasser: 16.40 m",
    "- S_Schmutzwasser: 31.41 m",
    "Total length: 68.47 m",
]


@pytest.mark.parametrize(
    "text",
    [
        "How long is each pipe system on P-101?",
        "How long is each plumbing system?",
        "What is the length of each piping system?",
    ],
)
def test_each_system_on_a_picture_lists_each_systems_length(text: str) -> None:
    said = str(_ask_p101(text).answer)
    assert said.splitlines()[:5] == PER_SYSTEM, said
    assert "holds no systems" not in said


def test_a_named_system_on_a_picture_is_still_its_own_length() -> None:
    said = str(_ask_p101("How long is the rainwater pipe run?").answer)
    assert said.startswith("S_Regenwasser: 16.40 m") and "68.47" not in said, said


# The DigitalHub v2 services models (Stoa dataset, partner data: never committed) through their
# fact sheets as ingest keeps them; skipped on a machine without them
REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "data/stoa/full/junction-dataset/data/ifc_models"
SHEETS = REPO / "data/cache/facts"


def _model(name: str) -> tuple[str, FactSheet]:
    ifc = MODELS / f"rwth-digitalhub_digitalhub-fm-{name}-v2.ifc"
    if not ifc.is_file():
        pytest.skip("the dataset is not on this machine")
    sheet = SHEETS / f"{hashlib.sha256(ifc.read_bytes()).hexdigest()}-{CODE}.json"
    if not sheet.is_file():
        pytest.skip("the model's fact sheet is not cached on this machine")
    return ifc.name, FactSheet.model_validate_json(sheet.read_text())


def _said(name: str, text: str) -> str:
    file, sheet = _model(name)
    answer = answer_from_facts(Question(id=1, file=file, text=text), sheet, 0.0)
    assert answer is not None, text
    return str(answer.answer)


def test_ifc_the_heating_system_of_the_sanitary_model_is_not_its_plumbing_pipes() -> None:
    """review-737 M1: 301.11 m of plumbing pipe was given as the heating system's length."""
    for text in (
        "What is the total length of the heating system?",
        "How long is each heating system?",
    ):
        said = _said("san", text)
        assert said.startswith("No heating system found"), said
        assert "301.11" not in said


def test_ifc_each_system_of_the_ventilation_model_lists_its_systems() -> None:
    """review-737 S1: "No pipe segments found" on a model with 4 air systems."""
    said = _said("lft", "What is the length of each system?")
    assert "No pipe segments" not in said and "system types:" in said, said


def _radiators_only() -> FactSheet:
    """H-101 as the lane reads it: radiators, no runs."""
    legend = (LegendEntry(label="Radiator", group=None, line=False, box=(0.9, 0.1, 0.92, 0.11)),)
    spots = tuple(
        Sighting(label="Radiator", spot=Spot(page=1, box=(0.1 * i, 0.5, 0.1 * i + 0.01, 0.51),
                                             reader="template"))
        for i in range(3)
    )  # fmt: skip
    reading = PictureReading(reader="template", legend=legend, read=("Radiator",), sightings=spots)
    return picture_facts("h101", Checked(readings=(reading,), agreed={}, disputed=()), "heating")


def _ducts() -> FactSheet:
    """The ventilation photo as the lane reads it: two air systems' duct runs."""
    labels = {"V_Abluft": 91.99, "V_Zuluft": 60.5}
    at = [Spot(page=1, box=(0.1 * i, 0.2, 0.1 * i + 0.05, 0.21), reader="mask") for i in range(2)]
    legend = tuple(
        LegendEntry(label=label, group=None, line=True, box=(0.8, 0.1 * i, 0.85, 0.1 * i + 0.01))
        for i, label in enumerate(labels)
    )
    runs = PictureReading(
        reader="mask", legend=legend, read=tuple(labels),
        runs=tuple(Run(label=label, size=None, length_m=metres,
                       spots=(at[i],))
                   for i, (label, metres) in enumerate(labels.items())),
    )  # fmt: skip
    return picture_facts("vent", Checked(readings=(runs,), agreed={}, disputed=()), "ventilation")


@pytest.mark.parametrize(
    ("sheet", "text"),
    [
        ("h101", "How long is each heating system?"),
        ("h101", "What is the length of each system?"),
    ],
)
def test_a_system_length_the_picture_has_no_runs_for_says_not_available(
    sheet: str, text: str
) -> None:
    """review-737 S3: "This question isn't one I can turn into a count, area, length or volume"
    (untrue for a length) where main said the facts' not-available line."""
    found = _p101() if sheet == "p101" else _radiators_only()
    answer = answer_from_facts(Question(id=1, file="x.png", text=text), found, 0.0)
    assert answer is not None and answer.method == FACTS, answer
    assert "not available" in str(answer.answer), answer


def test_each_system_on_a_duct_picture_lists_its_ducts_by_system() -> None:
    """review-737 S2: "length of each system" went to pipes; the ventilation photo has none."""
    answer = answer_from_facts(
        Question(id=1, file="vent.jpg", text="What is the length of each system?"), _ducts(), 0.0
    )
    assert answer is not None and answer.method == FACTS, answer
    said = str(answer.answer)
    assert said.splitlines()[:2] == ["- V_Abluft: 91.99 m", "- V_Zuluft: 60.50 m"], said


def test_a_system_kind_the_picture_has_no_runs_of_names_the_runs_it_has() -> None:
    """review-741 M1: P-101 "each ventilation system" said "This file holds no systems", though
    the sheet shows 4; it says what "each heating system" says: none labelled so, and its runs."""
    for text, asked in (
        ("How long is each ventilation system?", "ventilation"),
        ("How long is each heating system?", "heating"),
    ):
        said = str(_ask_p101(text).answer)
        assert said.splitlines()[0] == (
            f"No run on this sheet is labelled as {asked} (not available); its runs by system:"
        ), said
        assert "- S_PWC: 18.86 m" in said and "holds no systems" not in said
