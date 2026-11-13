"""File access (the `DrawingFiles` port): files of an unzipped dataset on disk."""

from pathlib import Path

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
