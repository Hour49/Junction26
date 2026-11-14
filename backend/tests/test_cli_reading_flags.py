"""The golden/answer CLI path (Pipeline.answer_questions) gives each page the reading flags ingest
stores, so an answer on a flagged page is never sure there either (review-283 M1: a scanned PDF
read on the raster route came back `sure: true` with DECISIONS_CONFIDENCE and a GATE_POLICY,
while the product's ask never certifies it)."""

import io
import json
from pathlib import Path

import pytest
from PIL import Image
from test_scan_images import DETECTOR, Reader, Session, scan

from app import composition
from app.adapters import raster_detector
from app.adapters.answer_v1 import AnswerV1Writer
from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.composition import build_pipeline
from app.core.answering.model import Question
from app.settings import Settings


def png() -> bytes:
    image = Image.new("RGB", (300, 200), "white")
    image.paste((0, 0, 0), (40, 40, 60, 60))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def door_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str, data: bytes, kind: str
) -> dict:
    """The CLI's answer to "How many doors?" on one file read on the raster route by a detector
    that finds one door, with Gemini Decisions saying 1 for sure and a gate at 0.5 on doors."""
    models = tmp_path / "models" / "C"
    models.mkdir(parents=True)
    facts = {k: DETECTOR[k] for k in ("format", "side", "classes", "element_class")}
    (models / "model.json").write_text(json.dumps(facts))
    (models / "detector.json").write_text(json.dumps(DETECTOR))
    monkeypatch.setattr(composition, "DETECTOR_DIR", tmp_path / "models")
    monkeypatch.setattr(raster_detector, "onnx_session", lambda path: Session())
    monkeypatch.setattr(composition, "decisions_reader", lambda settings: Reader())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=detector:C,plans=detector:C")
    gate = tmp_path / "gate.json"
    gate.write_text(json.dumps({
        "schema": "gate_policy_v1", "part": "val", "split_sha256": "0" * 64,
        "families": {"door": {"threshold": 0.5, "signal": "g1main"}},
    }))  # fmt: skip
    dataset = tmp_path / "dataset"
    (dataset / path).parent.mkdir(parents=True)
    (dataset / path).write_bytes(data)
    settings = Settings(decisions_confidence=True, gate_policy=str(gate))
    pipeline = build_pipeline(settings, dataset, lambda _: kind)
    out = tmp_path / "extraction"
    out.mkdir()
    (sheet,) = pipeline.ingest([path], ExtractionV1Writer(out, {path: "dev"})).sheets
    assert sheet.route == "raster"
    answers = tmp_path / "answers.jsonl"
    pipeline.answer_questions(
        [Question(id=1, file=path, text="How many doors are there?")],
        ExtractionV1Reader(out),
        AnswerV1Writer(answers),
    )
    (answer,) = [json.loads(line) for line in answers.read_text().splitlines()]
    assert answer["answer"] == 1 and answer["confidence"] == 1.0
    return answer


def test_a_plan_image_is_certified_by_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control: the gate certifies an unflagged page on this path."""
    assert door_answer(tmp_path, monkeypatch, "data/plans/plan.png", png(), "png_plan")["sure"]


def test_a_scanned_pdfs_answers_are_never_sure_on_the_cli_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answer = door_answer(tmp_path, monkeypatch, "data/scans/plan.pdf", scan(), "pdf_scan")
    assert answer.get("sure") is None  # a scanned PDF, read as an image: the gate has no verdict
