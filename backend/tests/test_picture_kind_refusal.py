"""A thing the picture lane counts, asked of a sheet that has none (live pics-digitalhub,
2026-11-15): "How many radiators are on H-101?" answered H-101 29 and H-102 34, but the A-101 and
P-101 parts said "I don't count radiators: they are not one of the things the readers count", a
denial the lane's own answers contradict. Such a sheet refuses with what exists: the picture's
facts' own "not read on this picture: its legend lists no ..." when the lane read it, else the
reader text "The reader of this drawing doesn't look for ...". A thing nobody counts keeps its
words."""

from test_levels import POLICY, SCAN, Scored

from app.adapters.answer_prior import NoPrior
from app.adapters.question_templates import TemplateParser
from app.core.ifc_facts import Fact, FactSheet, Spot
from app.core.review.ask import Asked, ask
from app.core.review.model import ReviewState

SPOT = Spot(page=1, box=(0.1, 0.1, 0.12, 0.12), reader="vlm")
P101 = FactSheet(  # the lane read P-101's legend: sanitary rows, no radiator
    model="p101",
    disciplines=["plumbing"],
    facts=[
        Fact(topic="sanitary_terminal.count", subject=subject, value=8, unit="count",
             discipline="plumbing", source="picture:vlm:held", spots=(SPOT,) * 8)
        for subject in ("all", "Waschtisch:60 x 60cm")
    ],
)  # fmt: skip


def asked(text: str, facts: FactSheet | None = None) -> Asked:
    return ask(
        text, SCAN, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=ReviewState(), confidence=Scored(0.9), raster=True, check=POLICY, route="raster",
        facts=None if facts is None else (lambda: facts),
    )  # fmt: skip


def test_a_picture_the_lane_read_says_its_legend_lists_none() -> None:
    found = asked("How many radiators are there?", P101)
    assert found.refusal is not None
    assert "I don't count" not in found.refusal.text, found.refusal.text
    assert found.refusal.text.startswith("Not read on this picture: its legend lists no ")
    assert found.refusal.code == "not-in-drawing"


def test_a_sheet_the_lane_did_not_read_says_its_reader_does_not_look_for_them() -> None:
    for text, noun in (
        ("How many radiators are there?", "radiators"),
        ("How many air terminals are there?", "air terminals"),
        ("How many fire dampers are there?", "fire dampers"),
        ("How many urinals are there?", "urinals"),
    ):
        found = asked(text)
        assert found.refusal is not None
        assert "I don't count" not in found.refusal.text, (text, found.refusal.text)
        assert found.refusal.text.startswith(
            f"The reader of this drawing doesn't look for {noun}, so it has no "
        ), (text, found.refusal.text)
        assert found.refusal.code == "not-read"


def test_a_thing_nobody_counts_keeps_its_words() -> None:
    found = asked("How many chairs are there?")
    assert found.refusal is not None and found.refusal.text.startswith("I don't count chairs")
