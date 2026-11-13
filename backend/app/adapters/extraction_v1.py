"""extraction_v1 files on disk: the writer (the `DrawingSink` port) and the reader (the
`DrawingSource` port). Contract: eval/schemas/extraction_v1.schema.json, decision record 0004.

The drawing model already has the format's fields; this module adds and removes the envelope:
`schema`, `split` (which side of the sealed split the file is on) and `truth` (`counts` when the
file only states totals, else `elements`). The optional `tables`, `conflicts`, `read` and
`model_objects` (0004's amendments) are written only when the drawing has them.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from app.adapters.paths import inside
from app.core.drawing.model import Drawing
from app.core.errors import InvalidInputError, NotFoundError

SCHEMA = "extraction_v1"
OPTIONAL = ("tables", "conflicts", "read", "model_objects")  # left out of the file when None
Split = Literal["dev", "eval"]


class ExtractionV1Writer:
    """Writes `<folder>/<file without its leading data/>.json`, e.g. the drawing of
    data/swiss_dwellings/x.png goes to <folder>/swiss_dwellings/x.png.json. The extension stays
    in the name because a plan's PDF and PNG are two files with the same stem."""

    def __init__(self, folder: Path, splits: Mapping[str, Split]) -> None:
        self._folder = folder
        self._splits = splits

    def write(self, drawing: Drawing) -> None:
        if drawing.file not in self._splits:
            raise InvalidInputError(f"{drawing.file}: extraction_v1 needs its split (dev or eval)")
        absent = {name for name in OPTIONAL if getattr(drawing, name) is None}
        body = {
            "schema": SCHEMA,
            "file": drawing.file,
            "split": self._splits[drawing.file],
            "truth": "elements" if drawing.counts is None else "counts",
            **drawing.model_dump(mode="json", by_alias=True, exclude={"file", *absent}),
        }
        path = inside(self._folder, drawing.file.removeprefix("data/") + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


class ExtractionV1Reader:
    """Every extraction_v1 JSON under `folder`, found by the `file` it describes (the file names
    differ between the gold and our writer). Folders and files starting with "_" are skipped, as
    eval does."""

    def __init__(self, folder: Path) -> None:
        if not folder.is_dir():
            raise NotFoundError(f"{folder} is not a folder of extraction_v1 files")
        self._paths: dict[str, Path] = {}
        for path in sorted(folder.rglob("*.json")):
            if any(part.startswith("_") for part in path.relative_to(folder).parts):
                continue
            file = _load(path).get("file")
            if not isinstance(file, str):
                raise InvalidInputError(f"{path}: no `file`")
            if file in self._paths:
                raise InvalidInputError(f"{path} and {self._paths[file]} both describe {file}")
            self._paths[file] = path

    def drawing(self, file: str) -> Drawing | None:
        path = self._paths.get(file)
        if path is None:
            return None
        body = _load(path)
        if body.pop("schema", None) != SCHEMA:
            raise InvalidInputError(f"{path}: not an {SCHEMA} file")
        body.pop("split", None)
        if body.pop("truth", None) != "counts":
            body["counts"] = None  # with full lists the counts are derived, as eval does
        try:
            return Drawing.model_validate(body)
        except ValidationError as error:
            raise InvalidInputError(f"{path}: {error}") from error


def _load(path: Path) -> dict[str, Any]:
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InvalidInputError(f"{path}: {error}") from error
    if not isinstance(body, dict):
        raise InvalidInputError(f"{path}: not a JSON object")
    return body
