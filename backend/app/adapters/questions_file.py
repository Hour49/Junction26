"""A questions file in the dataset's format: the dataset's own questions.jsonl, or one side of
the sealed split (data/stoa/split/dev.jsonl, eval/README.md). One JSON object per line; only
`path`, `question` and `id` are read, never the answer.

The eval side of the split is sealed: it is scored only at a milestone. `sealed_by` tells that
file from any other by its bytes, so a copy under another name is found too.
"""

import hashlib
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.adapters.golden_dir import numbered_rows
from app.core.answering.model import Question
from app.core.errors import InvalidInputError, NotFoundError

SPLIT_MANIFEST, SEALED_SIDE = "manifest.json", "eval.jsonl"


class _Row(BaseModel):
    path: str
    question: str
    id: int | None = Field(default=None, ge=1)  # the split's files carry the dataset line number


class _SplitManifest(BaseModel):
    files_sha256: dict[str, str] = {}


class QuestionsFile:
    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise NotFoundError(f"{path} is not a questions file")
        self._path = path

    def questions(self) -> list[Question]:
        """A line's id is its own `id`, else its line number (the dataset's questions.jsonl has
        no ids, and a question's id is its line there)."""
        questions: list[Question] = []
        lines: dict[int, int] = {}
        for number, row in numbered_rows(self._path, _Row):
            id_ = number if row.id is None else row.id
            if id_ in lines:
                raise InvalidInputError(
                    f"{self._path}:{number}: id {id_} is also the id of line {lines[id_]}"
                )
            lines[id_] = number
            questions.append(Question(id=id_, file=row.path, text=row.question))
        return questions

    def sealed_by(self, split_dir: Path) -> Path | None:
        """The split manifest that lists this file's bytes as its sealed eval side, or None. Both
        the split in `split_dir` and a split in the file's own folder are looked at."""
        digest = hashlib.sha256(self._path.read_bytes()).hexdigest()
        for folder in dict.fromkeys((split_dir.resolve(), self._path.resolve().parent)):
            manifest = folder / SPLIT_MANIFEST
            if manifest.is_file() and _sealed_digest(manifest) == digest:
                return manifest
        return None


def _sealed_digest(manifest: Path) -> str | None:
    try:
        split = _SplitManifest.model_validate_json(manifest.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise InvalidInputError(f"{manifest}: {error}") from error
    return split.files_sha256.get(SEALED_SIDE)
