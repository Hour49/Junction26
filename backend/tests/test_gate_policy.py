"""GATE_POLICY: golden's gate.json (gate_policy_v1) turns the answer confidence into `sure`."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from test_answering import (
    FILE,
    Collected,
    DoorParser,
    Drawings,
    FakeConfidence,
    NoPrior,
    drawing,
    rated,
    ticking_clock,
)
from test_raster_composite import PNG, FakeDecisions, FakeVerda, FakeVerdaNoToilet, Sink

from app import composition
from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.adapters.gate_policy import load_gate
from app.composition import build_pipeline
from app.core.answering.answer import answer_question, answer_questions
from app.core.answering.model import Answer, Question
from app.core.errors import InvalidInputError
from app.core.pipeline.takeoff import known_quantities
from app.settings import Settings

SHA = "9c762d68a698dd45a6c1ca4fa7fae39f19199aae470d1b195ed82a873d8c48e9"


def gate_file(tmp_path: Path, **change: object) -> Path:
    val = {"note": "chosen on val, not a guarantee", "answers": 188, "sure": 117, "exact": 116,
           "coverage": 0.62, "bound": 0.96}  # fmt: skip
    doc = {
        "schema": "gate_policy_v1", "generated": "2026-11-14T04:37:50+02:00", "part": "val",
        "split_sha256": SHA, "arm": "region-L1536-R1+swap-S1536+ocr-G4-regpred", "second": None,
        "family_arms": {"room:wc": "ocr/G4-regpred"}, "swap": "S1536", "target": 0.95,
        "source": "data/stoa/exp/ab/gate-x-val.json", "certified": False,
        "families": {
            "toilet": {"signal": "g1main", "threshold": 0.95, "group": "elements", "val": val},
            "door": {"signal": "g1main", "threshold": 0.8, "group": "elements", "val": val},
            "sauna": {"signal": "agree_pb", "threshold": 1.4, "group": "rooms", "val": val},
        },
    }  # fmt: skip
    doc.update(change)
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_the_loader_keeps_the_families_gated_on_the_signal(tmp_path: Path) -> None:
    assert load_gate(gate_file(tmp_path), "g1main") == {"toilet": 0.95, "door": 0.8}
    assert load_gate(gate_file(tmp_path), "agree_pb") == {"sauna": 1.4}


@pytest.mark.parametrize(
    ("change", "why"),
    [
        ({"split_sha256": None}, "no split_sha256"),
        ({"split_sha256": "abc"}, "no split_sha256"),
        ({"part": "test"}, "chosen on val"),
        ({"schema": "answer_policy_v1"}, "gate_policy_v1"),
        ({"families": {"door": {"signal": "g1main", "threshold": "high"}}}, "numeric 'threshold'"),
    ],
)
def test_the_loader_refuses_a_bad_gate(tmp_path: Path, change: dict[str, object], why: str) -> None:
    with pytest.raises(InvalidInputError, match=why):
        load_gate(gate_file(tmp_path, **change), "g1main")


def test_sure_is_the_confidence_at_or_above_the_family_threshold() -> None:
    def sure(value: float | None, sure_at: dict[str, float] | None) -> bool | None:
        question = Question(id=7, file=FILE, text="How many doors?")
        return answer_question(
            question, known_quantities(drawing()), DoorParser(), ticking_clock().__next__,
            NoPrior(), confidence=FakeConfidence(value), sure_at=sure_at,
        ).sure  # fmt: skip

    assert sure(0.81, {"door": 0.8}) is True
    assert sure(0.8, {"door": 0.8}) is True  # at the threshold
    assert sure(0.79, {"door": 0.8}) is False
    assert sure(None, {"door": 0.8}) is False  # gated, but no probability: not sure
    assert sure(0.99, {"toilet": 0.5}) is None  # doors are not gated
    assert sure(0.99, None) is None  # no gate file
    assert rated("How many doors?", drawing(), FakeConfidence(0.99)).sure is None
    assert rated("How many doors?", None, FakeConfidence(0.99)).sure is None  # a refusal


def test_answer_questions_passes_the_gate_on() -> None:
    sink = Collected()
    answer_questions(
        [Question(id=1, file=FILE, text="How many doors?")],
        drawings=Drawings(),
        parser=DoorParser(),
        clock=ticking_clock().__next__,
        sink=sink,
        prior=NoPrior(),
        confidence=FakeConfidence(0.81),
        sure_at={"door": 0.8},
    )
    assert [(a.confidence, a.sure) for a in sink.answers] == [(0.81, True)]


def test_gate_policy_marks_pipeline_answers_sure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_png: Callable[[int, int], bytes]
) -> None:
    """Gemini is 0.99 sure of 1 toilet (FakeDecisions); toilets are gated at 0.95 on g1main."""
    dataset, out = tmp_path / "dataset", tmp_path / "out"
    (dataset / "data" / "cubicasa5k").mkdir(parents=True)
    (dataset / PNG).write_bytes(make_png(40, 30))
    monkeypatch.chdir(tmp_path)
    for name, value in {
        "EXTRACTOR_RASTER": "composite",
        "RASTER_COMPONENTS": "elements=decisions:verda,plans=decisions:verda",
        "VERDA_READER_URL": "https://reader.example", "GEMINI_API_KEY": "test-key",
        "QUESTION_PARSER": "templates", "ANSWER_PRIOR": "none",
        "DECISIONS_CACHE_DIR": str(tmp_path / "cache"), "GATE_POLICY": str(gate_file(tmp_path)),
    }.items():  # fmt: skip
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(composition, "HttpReaderClient", FakeVerdaNoToilet)
    monkeypatch.setattr(composition, "DecisionsClient", FakeDecisions)
    # the fakes' class-level records: other tests count them, so this test keeps its own
    monkeypatch.setattr(FakeDecisions, "built", [])
    monkeypatch.setattr(FakeDecisions, "calls", 0)
    monkeypatch.setattr(FakeVerda, "built", [])
    assert build_pipeline(Settings(), dataset).sure_at is None  # no confidence: nothing to gate
    monkeypatch.setenv("DECISIONS_CONFIDENCE", "true")
    pipeline = build_pipeline(Settings(), dataset)
    assert pipeline.sure_at == {"toilet": 0.95, "door": 0.8}  # sauna is gated on agree_pb
    pipeline.ingest([PNG], ExtractionV1Writer(out, {PNG: "dev"}))
    answers: list[Answer] = []
    question = "How many toilet bowls (WC seats) are drawn on this floor plan?"
    pipeline.answer_questions(
        [Question(id=1, file=PNG, text=question)], ExtractionV1Reader(out), Sink(answers)
    )
    assert [(a.answer, a.confidence, a.sure) for a in answers] == [(1, 0.99, True)]
    assert composition.build_answering(Settings()).sure_at == {"toilet": 0.95, "door": 0.8}
