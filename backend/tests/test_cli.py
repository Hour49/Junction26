"""`python -m app.cli golden` on a synthetic golden v2 folder with two drawing files: what lands in
the run folder is what eval/ scores."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.cli import main

SCHEMAS = Path(__file__).parents[2] / "eval" / "schemas"
PNG, PDF = "data/demo/a.png", "data/demo/b.pdf"
GOLD_OF_PNG: dict[str, Any] = {
    "schema": "extraction_v1",
    "file": PNG,
    "split": "dev",
    "truth": "elements",
    "pages": [{"page": 1, "width": 40, "height": 30, "unit": "px"}],
    "scale": {"status": "no_scale"},
    "plans": [],
    "elements": [
        {"id": "e1", "class": "door", "page": 1, "box": [0.1, 0.2, 0.3, 0.4]},
        {"id": "e2", "class": "door", "page": 1, "box": [0.5, 0.5, 0.6, 0.6]},
    ],
    "rooms": [],
}


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMAS / name).read_text(encoding="utf-8")))


@pytest.fixture
def run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_png: Callable[[int, int], bytes],
    make_pdf: Callable[..., bytes],
) -> Callable[..., int]:
    """Builds the dataset and the golden folder under tmp_path; returns the CLI call."""
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    dataset, golden = tmp_path / "dataset", tmp_path / "golden"
    (dataset / "data" / "demo").mkdir(parents=True)
    (dataset / PNG).write_bytes(make_png(40, 30))
    (dataset / PDF).write_bytes(make_pdf((200, 100)))
    (golden / "part1_extraction" / "gold" / "demo").mkdir(parents=True)
    (golden / "part2_answering").mkdir()
    files = [
        {"file": PNG, "source": "demo", "split": "dev", "truth": "elements"},
        {"file": PDF, "source": "demo", "split": "eval", "truth": None},  # no gold for this one
    ]
    questions = [
        {"id": 7, "path": PNG, "question": "How many doors?", "answer": 2, "unit": "count"},
        {"id": 8, "path": PNG, "question": "Combien de portes ?", "answer": 2, "unit": "count"},
        {"id": 9, "path": PDF, "question": "How many windows?", "answer": 4, "unit": "count"},
    ]
    (golden / "part1_extraction" / "files.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in files), encoding="utf-8"
    )
    (golden / "part2_answering" / "questions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in questions), encoding="utf-8"
    )
    (golden / "part1_extraction" / "gold" / "demo" / "a.json").write_text(
        json.dumps(GOLD_OF_PNG), encoding="utf-8"
    )

    def call(drawings: str, out: Path) -> int:
        places = ["--golden-dir", str(golden), "--dataset", str(dataset), "--out", str(out)]
        return main(["golden", *places, "--drawings", drawings])

    return call


def answers_of(out: Path) -> dict[int, dict[str, Any]]:
    lines = [json.loads(line) for line in (out / "answers.jsonl").read_text().splitlines()]
    for line in lines:
        validator("answer_v1.schema.json").validate(line)
    return {line["id"]: line for line in lines}


def test_pipeline_run_writes_an_extraction_per_file_and_an_answer_per_question(
    run: Callable[..., int], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "runs" / "hello"
    assert run("pipeline", out) == 0

    written = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert written == [
        "answers.jsonl",
        "extraction/demo/a.png.json",
        "extraction/demo/b.pdf.json",
        "ingest.json",
    ]
    png = json.loads((out / "extraction/demo/a.png.json").read_text())
    pdf = json.loads((out / "extraction/demo/b.pdf.json").read_text())
    for body in (png, pdf):
        validator("extraction_v1.schema.json").validate(body)
        assert (body["elements"], body["rooms"], body["plans"]) == ([], [], [])
        assert body["scale"]["status"] == "no_scale"
    assert (png["file"], png["split"], png["pages"]) == (
        PNG,
        "dev",
        [{"page": 1, "width": 40.0, "height": 30.0, "unit": "px"}],
    )
    assert (pdf["file"], pdf["split"], pdf["pages"]) == (
        PDF,
        "eval",
        [{"page": 1, "width": 200.0, "height": 100.0, "unit": "pt"}],
    )

    answers = answers_of(out)
    assert sorted(answers) == [7, 8, 9]
    assert {answer["answer"] for answer in answers.values()} == {None}
    assert {answer["method"] for answer in answers.values()} == {"refused:unsupported-question"}

    report = json.loads((out / "ingest.json").read_text())
    assert [(sheet["file"], sheet["route"]) for sheet in report["sheets"]] == [
        (PNG, "raster"),
        (PDF, "vector"),
    ]
    assert report["set_aside"] == []
    printed = capsys.readouterr().out
    assert "ingest: 2 drawing models" in printed
    assert "answering: 3 answers" in printed


def test_gold_run_answers_from_the_part1_gold_and_writes_no_extraction(
    run: Callable[..., int], tmp_path: Path
) -> None:
    out = tmp_path / "runs" / "hello-gold"
    assert run("gold", out) == 0

    assert sorted(path.name for path in out.iterdir()) == ["answers.jsonl"]
    answers = answers_of(out)
    # The hello-world parser understands no question; the PDF has no gold drawing at all.
    assert {id_: answer["method"] for id_, answer in answers.items()} == {
        7: "refused:unsupported-question",
        8: "refused:unsupported-question",
        9: "refused:no-drawing",
    }
    assert {answer["answer"] for answer in answers.values()} == {None}


def test_a_run_folder_that_is_not_empty_is_refused(
    run: Callable[..., int], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "runs" / "taken"
    out.mkdir(parents=True)
    (out / "answers.jsonl").write_text("an earlier run\n")
    assert run("gold", out) == 1
    assert "is not empty" in capsys.readouterr().err
    assert (out / "answers.jsonl").read_text() == "an earlier run\n"


def test_a_file_missing_from_the_dataset_stops_the_run_with_its_name(
    run: Callable[..., int], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "dataset" / PDF).unlink()
    assert run("pipeline", tmp_path / "runs" / "broken") == 1
    assert f"{PDF} is not in the dataset" in capsys.readouterr().err
