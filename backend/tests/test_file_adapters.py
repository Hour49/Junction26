"""The adapters that read from disk: dataset files, page sizes, and a golden v2 folder."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from app.adapters.dataset_files import DatasetFiles
from app.adapters.golden_dir import GoldenDir, GoldenFile
from app.adapters.page_sizes import PageSizes
from app.adapters.paths import inside
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


def test_golden_dir_names_the_bad_line_or_the_missing_file(tmp_path: Path) -> None:
    golden = golden_dir(tmp_path / "bad", [{"file": "data/demo/a.png", "split": "train"}], [])
    with pytest.raises(InvalidInputError, match=r"files\.jsonl:1"):
        golden.files()
    with pytest.raises(NotFoundError, match="is this a golden v2 folder"):
        GoldenDir(tmp_path / "empty").questions()
