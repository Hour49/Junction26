"""Files of an unzipped dataset on disk: file access (the `DrawingFiles` port) and the building
model a plan sheet was rendered from (the `SourceFinder` port)."""

from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from app.adapters.paths import inside
from app.core.errors import NotFoundError


class DatasetFiles:
    """Reads a file by the path the dataset's questions.jsonl gives it (`data/<source>/<name>`),
    relative to the dataset root."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def read(self, path: str) -> bytes:
        target = inside(self._root, path)
        if not target.is_file():
            raise NotFoundError(f"{path} is not in the dataset at {self._root}")
        return target.read_bytes()


SHEET_OF_MODEL = "_plan-"  # <model>_plan-<number>-<storey>.pdf is a plan sheet of <model>.ifc


class DatasetSheetModels:
    """The IFC model next to a plan sheet rendered from it. The dataset names the sheets of
    `<model>.ifc` `<model>_plan-<number>-<storey>.pdf`, each with an SVG twin of the same name
    whose shapes carry the model's GlobalIds. The model is a source for the sheet only when
    that twin is there: without it nothing ties the model's objects to the page, and the sheet
    is better read on its own."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def sources(self, path: str) -> Sequence[str]:
        sheet = PurePosixPath(path)
        model_name, marker, _ = sheet.stem.rpartition(SHEET_OF_MODEL)
        if sheet.suffix.lower() != ".pdf" or not marker or not model_name:
            return ()
        model, twin = sheet.with_name(f"{model_name}.ifc"), sheet.with_suffix(".svg")
        if all(inside(self._root, str(found)).is_file() for found in (model, twin)):
            return (str(model),)
        return ()
