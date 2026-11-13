"""The adapters that read from disk: dataset files, page sizes, a golden v2 folder and a
questions file."""

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from app.adapters.dataset_files import DatasetFiles
from app.adapters.golden_dir import GoldenDir, GoldenFile
from app.adapters.page_sizes import PageSizes
from app.adapters.paths import inside
from app.adapters.questions_file import QuestionsFile
from app.core.answering.model import Question
from app.core.drawing.model import Page
from app.core.errors import InvalidInputError, NotFoundError
from app.core.pipeline.model import DrawingFile, FileKind


def test_dataset_files_reads_by_the_dataset_path(tmp_path: Path) -> None:
    (tmp_path / "data" / "demo").mkdir(parents=True)
    (tmp_path / "data" / "demo" / "a.png").write_bytes(b"pixels")
    assert DatasetFiles(tmp_path).read("data/demo/a.png") == b"pixels"


def test_dataset_files_names_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError, match=r"data/demo/missing\.png is not in the dataset"):
        DatasetFiles(tmp_path).read("data/demo/missing.png")


@pytest.mark.parametrize("path", ["../secret.txt", "data/../../secret.txt", "/etc/hostname", ""])
def test_a_path_that_leaves_its_folder_is_refused(tmp_path: Path, path: str) -> None:
    root = tmp_path / "dataset"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("outside")
    with pytest.raises(InvalidInputError, match="not a path inside"):
        DatasetFiles(root).read(path)


def test_inside_allows_a_path_under_the_root(tmp_path: Path) -> None:
    assert inside(tmp_path, "a/b.json") == tmp_path.resolve() / "a" / "b.json"


class Bytes:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self, path: str) -> bytes:
        return self.data


def sheet_file(kind: FileKind) -> DrawingFile:
    return DrawingFile(path=f"data/demo/a.{kind}", size=1, sha256="0" * 64, kind=kind)


def test_page_sizes_of_an_image_are_its_pixels(make_png: Callable[[int, int], bytes]) -> None:
    pages = PageSizes(Bytes(make_png(40, 30))).pages(sheet_file("png"))
    assert pages == (Page(page=1, width=40, height=30, unit="px"),)


def test_page_sizes_of_a_pdf_are_its_pages_in_points(make_pdf: Callable[..., bytes]) -> None:
    pages = PageSizes(Bytes(make_pdf((200, 100), (595, 842)))).pages(sheet_file("pdf"))
    assert pages == (
        Page(page=1, width=200, height=100, unit="pt"),
        Page(page=2, width=595, height=842, unit="pt"),
    )


def test_page_sizes_refuses_a_kind_without_pages() -> None:
    with pytest.raises(ValueError, match="a dxf file has no pages"):
        PageSizes(Bytes(b"0\nSECTION\n")).pages(sheet_file("dxf"))


def golden_dir(root: Path, files: list[dict[str, object]], questions: list[str]) -> GoldenDir:
    (root / "part1_extraction" / "gold").mkdir(parents=True)
    (root / "part2_answering").mkdir()
    (root / "part1_extraction" / "files.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in files), encoding="utf-8"
    )
    (root / "part2_answering" / "questions.jsonl").write_text(
        "".join(line + "\n" for line in questions), encoding="utf-8"
    )
    return GoldenDir(root)


def test_golden_dir_reads_files_with_their_split_and_questions_without_answers(
    tmp_path: Path,
) -> None:
    golden = golden_dir(
        tmp_path,
        [
            {"file": "data/demo/a.png", "source": "demo", "split": "dev", "truth": "elements"},
            {"file": "data/demo/b.pdf", "source": "demo", "split": "eval", "truth": None},
        ],
        [
            json.dumps(
                {
                    "path": "data/demo/a.png",
                    "question": "How many doors?",
                    "answer": 2,
                    "unit": "count",
                    "type": "count",
                    "id": 7,
                }
            ),
            "",
        ],
    )
    assert golden.files() == [
        GoldenFile(file="data/demo/a.png", split="dev"),
        GoldenFile(file="data/demo/b.pdf", split="eval"),
    ]
    assert golden.questions() == [Question(id=7, file="data/demo/a.png", text="How many doors?")]
    assert golden.gold == tmp_path / "part1_extraction" / "gold"


def extras_line(id_: int) -> str:
    """A line as eval's ExtraItem has it; `answer`, `expect` and `why` are the answer key."""
    return json.dumps(
        {
            "path": "data/demo/a.png",
            "question": "Count the doors on this plan.",
            "answer": 2,
            "unit": "count",
            "type": "count",
            "id": id_,
            "kind": "paraphrase",
            "origin_id": 7,
            "expect": {"answer": 2},
            "why": None,
        }
    )


def test_golden_dir_reads_extras_as_questions_and_none_when_the_file_is_absent(
    tmp_path: Path,
) -> None:
    golden = golden_dir(tmp_path, [], [])
    assert golden.extras() == []
    (tmp_path / "part2_answering" / "extras.jsonl").write_text(extras_line(1000001) + "\n")
    assert golden.extras() == [
        Question(id=1000001, file="data/demo/a.png", text="Count the doors on this plan.")
    ]


def test_golden_dir_refuses_an_extras_id_that_could_be_a_dataset_line(tmp_path: Path) -> None:
    golden = golden_dir(tmp_path, [], [])
    (tmp_path / "part2_answering" / "extras.jsonl").write_text(extras_line(1000000) + "\n")
    with pytest.raises(InvalidInputError, match=r"extras\.jsonl:1"):
        golden.extras()


def test_golden_dir_names_the_bad_line_or_the_missing_file(tmp_path: Path) -> None:
    golden = golden_dir(tmp_path / "bad", [{"file": "data/demo/a.png", "split": "train"}], [])
    with pytest.raises(InvalidInputError, match=r"files\.jsonl:1"):
        golden.files()
    with pytest.raises(NotFoundError, match="is this a golden v2 folder"):
        GoldenDir(tmp_path / "empty").questions()


def questions_file(folder: Path, *rows: Mapping[str, object]) -> Path:
    path = folder / "questions.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_a_questions_line_keeps_its_id_and_one_without_gets_its_line_number(tmp_path: Path) -> None:
    """The split's files carry `id`; the dataset's questions.jsonl does not. The answer key
    (`answer`, `unit`, `type`) is not read."""
    path = tmp_path / "questions.jsonl"
    with_id = {"path": "data/demo/a.png", "question": "How many doors?", "answer": 2, "id": 70}
    without = {"path": "data/demo/b.pdf", "question": "How many windows?", "unit": "count"}
    path.write_text(f"{json.dumps(with_id)}\n\n{json.dumps(without)}\n", encoding="utf-8")
    assert QuestionsFile(path).questions() == [
        Question(id=70, file="data/demo/a.png", text="How many doors?"),
        Question(id=3, file="data/demo/b.pdf", text="How many windows?"),
    ]


def test_a_questions_file_with_one_id_twice_is_refused(tmp_path: Path) -> None:
    row = {"path": "data/demo/a.png", "question": "How many doors?"}
    path = questions_file(tmp_path, {**row, "id": 2}, row)  # line 2 has no id, so it is id 2 too
    with pytest.raises(InvalidInputError, match=r"questions\.jsonl:2: id 2 is also .* line 1"):
        QuestionsFile(path).questions()


def test_a_questions_file_names_the_bad_line_or_the_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match=r"questions\.jsonl:1"):
        QuestionsFile(questions_file(tmp_path, {"path": "data/demo/a.png"})).questions()
    with pytest.raises(NotFoundError, match="is not a questions file"):
        QuestionsFile(tmp_path / "absent.jsonl")


def test_the_sealed_side_is_known_by_its_bytes_from_either_manifest(tmp_path: Path) -> None:
    split, other = tmp_path / "split", tmp_path / "other"
    split.mkdir()
    other.mkdir()
    sealed = questions_file(split, {"path": "data/demo/a.png", "question": "How many doors?"})
    digest = hashlib.sha256(sealed.read_bytes()).hexdigest()
    manifest = split / "manifest.json"
    manifest.write_text(json.dumps({"files_sha256": {"eval.jsonl": digest, "dev.jsonl": "0" * 64}}))
    copy = other / "copy.jsonl"
    copy.write_bytes(sealed.read_bytes())
    dev = questions_file(other, {"path": "data/demo/a.png", "question": "How many windows?"})

    assert QuestionsFile(sealed).sealed_by(other) == manifest  # the manifest next to the file
    assert QuestionsFile(copy).sealed_by(split) == manifest  # the split's manifest
    assert QuestionsFile(copy).sealed_by(other) is None  # no split is known there
    assert QuestionsFile(dev).sealed_by(split) is None  # other bytes

    manifest.write_text(json.dumps({"files_sha256": {"dev.jsonl": "0" * 64}}))
    assert QuestionsFile(copy).sealed_by(split) is None  # a manifest that seals nothing


def test_a_split_manifest_that_cannot_be_read_stops_the_check(tmp_path: Path) -> None:
    """A broken manifest must not pass for "not sealed"."""
    path = questions_file(tmp_path, {"path": "data/demo/a.png", "question": "How many doors?"})
    (tmp_path / "manifest.json").write_text('{"files_sha256": "none"}')
    with pytest.raises(InvalidInputError, match=r"manifest\.json"):
        QuestionsFile(path).sealed_by(tmp_path)
