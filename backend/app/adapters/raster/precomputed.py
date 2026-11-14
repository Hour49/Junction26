"""Component readers of the raster composite that run no model.

`PrecomputedExtractor` gives what an experiment arm already wrote: a folder of extraction_v1
files, one per image (data/stoa/exp/<track>/<arm>/<image>.json, found by their `file`), so any
combination of arms is scored end to end without running a model. A sheet is found by its
dataset path, else by its content: an upload keeps no dataset path, so among the dataset files
the arm has a file for, the ones of the sheet's size are hashed (once, then cached) and the one
with the sheet's sha256 is used, as app/adapters/credits.py finds dataset files. A sheet found
neither way was not read by that arm: `read` is empty, so its classes stay unknown. So is a file
that states only totals (`truth: counts`, as the gold of an eval-split image does): it places no
item, and reading its empty lists as "nothing found" would give zeros.

`WholePagePlan` says the sheet is one plan that fills the page (most CubiCasa sheets are: 3,044
of the 3,828 dev images).
"""

import hashlib
import json
import threading
from pathlib import Path

from app.adapters.extraction_v1 import ExtractionV1Reader
from app.core.drawing.model import Drawing, Plan, Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class PrecomputedExtractor:
    """`dataset`: the folder the arm's `file` paths are relative to (the Stoa dataset); None
    matches by path only."""

    def __init__(self, folder: Path, dataset: Path | None = None) -> None:
        self._folder = folder
        self._drawings = ExtractionV1Reader(folder)
        self._dataset = dataset
        self._lock = threading.Lock()  # uploads are ingested in background threads
        self._by_size: dict[int, list[str]] | None = None
        self._sha: dict[str, str] = {}

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        drawing, how = self._drawings.drawing(sheet.file.path), None
        if drawing is None and (twin := self._same_content(sheet.file)) is not None:
            drawing, how = self._drawings.drawing(twin), f"matched by content to {twin}"
        if drawing is None or drawing.counts is not None:
            why = "no file" if drawing is None else "only totals (truth: counts)"
            return Extracted(
                method="other",
                scale=Scale(status="no_scale"),
                read=(),
                notes=(f"{why} for this sheet in {self._folder}",),
            )
        return _as_found(drawing, () if how is None else (how,))

    def _same_content(self, file: DrawingFile) -> str | None:
        """The arm's dataset file with the same bytes as `file`, if there is one."""
        if self._dataset is None:
            return None
        with self._lock:
            for path in self._index().get(file.size, []):
                if path not in self._sha:
                    self._sha[path] = _sha256(self._dataset / path)
                if self._sha[path] == file.sha256:
                    return path
        return None

    def _index(self) -> dict[int, list[str]]:
        """The arm's files that are in the dataset, by size (built on the first miss)."""
        if self._by_size is None:
            assert self._dataset is not None
            base = self._dataset.resolve()
            by_size: dict[int, list[str]] = {}
            for json_path in sorted(self._folder.rglob("*.json")):
                if any(p.startswith("_") for p in json_path.relative_to(self._folder).parts):
                    continue
                file = json.loads(json_path.read_text(encoding="utf-8")).get("file")
                target = (base / file).resolve() if isinstance(file, str) else None
                if target is not None and target.is_relative_to(base) and target.is_file():
                    by_size.setdefault(target.stat().st_size, []).append(file)
            self._by_size = by_size
        return self._by_size


def _as_found(drawing: Drawing, notes: tuple[str, ...]) -> Extracted:
    return Extracted(
        method="other",
        scale=drawing.scale,
        plans=drawing.plans,
        elements=drawing.elements,
        rooms=drawing.rooms,
        read=drawing.read,
        notes=(*drawing.notes, *notes),
    )


class WholePagePlan:
    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return Extracted(
            method="other",
            scale=Scale(status="no_scale"),
            plans=(Plan(id="p1", page=1, box=(0.0, 0.0, 1.0, 1.0)),),
            read=(),
            notes=("one plan, the whole page",),
        )
