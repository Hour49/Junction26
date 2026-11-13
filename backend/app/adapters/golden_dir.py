"""A golden v2 folder as `stoa_eval select-plans` writes it (eval/README.md, "Golden set v2"):

    part1_extraction/files.jsonl      the drawing files, each with its split
    part1_extraction/gold/            their extraction_v1 gold
    part2_answering/questions.jsonl   every question on those files
    part2_answering/extras.jsonl      optional: questions Stoa didn't write (reworded,
                                      unanswerable, estimate and conflict lines), ids from 1000001

Only the fields the pipeline needs are read. The golden answers are never loaded, and neither
are an extras line's `expect` and `why`, which are its answer key.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.core.answering.model import Question
from app.core.errors import InvalidInputError, NotFoundError

EXTRA_ID_MIN = 1_000_001  # as eval/stoa_eval/models.py: above every dataset line number


class GoldenFile(BaseModel):
    file: str
    split: Literal["dev", "eval"]


class _QuestionRow(BaseModel):
    id: int
    path: str
    question: str


class _ExtraRow(_QuestionRow):
    id: int = Field(ge=EXTRA_ID_MIN)


class GoldenDir:
    def __init__(self, root: Path) -> None:
        self._root = root
        self.gold = root / "part1_extraction" / "gold"

    def files(self) -> list[GoldenFile]:
        return _rows(self._root / "part1_extraction" / "files.jsonl", GoldenFile)

    def questions(self) -> list[Question]:
        rows = _rows(self._root / "part2_answering" / "questions.jsonl", _QuestionRow)
        return [Question(id=row.id, file=row.path, text=row.question) for row in rows]

    def extras(self) -> list[Question]:
        """The questions of extras.jsonl, or none when the folder has no such file."""
        path = self._root / "part2_answering" / "extras.jsonl"
        if not path.is_file():
            return []
        return [
            Question(id=row.id, file=row.path, text=row.question) for row in _rows(path, _ExtraRow)
        ]


def _rows[Row: BaseModel](path: Path, row: type[Row]) -> list[Row]:
    if not path.is_file():
        raise NotFoundError(f"{path} is missing: is this a golden v2 folder?")
    return [found for _, found in numbered_rows(path, row)]


def numbered_rows[Row: BaseModel](path: Path, row: type[Row]) -> list[tuple[int, Row]]:
    """Every non-empty line of a JSONL file as a `row`, with its 1-based line number."""
    rows: list[tuple[int, Row]] = []
    with path.open(encoding="utf-8") as lines:
        for number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                rows.append((number, row.model_validate_json(line)))
            except ValidationError as error:
                raise InvalidInputError(f"{path}:{number}: {error}") from error
    return rows
