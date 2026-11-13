"""Read and write JSON Lines as pydantic models, failing with the file and line on bad input."""

from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ValidationError


def read_jsonl[M: BaseModel](path: Path, model: type[M]) -> list[tuple[int, M]]:
    """(1-based line number, parsed line) for every non-blank line."""
    rows: list[tuple[int, M]] = []
    with path.open(encoding="utf-8") as lines:
        for lineno, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                rows.append((lineno, model.model_validate_json(line)))
            except ValidationError as error:
                raise ValueError(f"{path}:{lineno}: {error}") from error
    return rows


def write_jsonl(path: Path, rows: Iterable[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(row.model_dump_json() + "\n" for row in rows), encoding="utf-8")
