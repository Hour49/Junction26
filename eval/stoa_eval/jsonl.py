"""Read and write JSON Lines as pydantic models, failing with the file and line on bad input."""

from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel, ValidationError


def iter_jsonl[M: BaseModel](path: Path, model: type[M]) -> Iterator[tuple[int, M]]:
    """(1-based line number, parsed line) for every non-blank line, one line in memory at a time."""
    with path.open(encoding="utf-8") as lines:
        for lineno, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                yield lineno, model.model_validate_json(line)
            except ValidationError as error:
                raise ValueError(f"{path}:{lineno}: {error}") from error


def read_jsonl[M: BaseModel](path: Path, model: type[M]) -> list[tuple[int, M]]:
    return list(iter_jsonl(path, model))


def write_jsonl(path: Path, rows: Iterable[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(row.model_dump_json() + "\n" for row in rows), encoding="utf-8")
