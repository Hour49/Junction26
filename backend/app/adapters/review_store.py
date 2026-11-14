"""The review edits of each drawing on disk (the `ReviewStore` port): one JSON file per drawing,
`<folder>/<drawing id>.json`, replaced whole on every edit. One lock per store serialises the
updates of one process (the API runs one)."""

import json
import threading
from collections.abc import Callable
from pathlib import Path

from app.adapters.paths import inside
from app.core.review.model import ReviewState


class JsonReviewStore:
    def __init__(self, folder: Path) -> None:
        self._folder = folder
        self._lock = threading.Lock()

    def get(self, drawing_id: str) -> ReviewState:
        path = self._path(drawing_id)
        if not path.is_file():
            return ReviewState()
        return ReviewState.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def update(self, drawing_id: str, change: Callable[[ReviewState], ReviewState]) -> ReviewState:
        with self._lock:
            state = change(self.get(drawing_id))
            path = self._path(drawing_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(path)
            return state

    def _path(self, drawing_id: str) -> Path:
        return inside(self._folder, f"{drawing_id}.json")
