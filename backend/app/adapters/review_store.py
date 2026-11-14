"""The review edits of each drawing on disk (the `ReviewStore` port): one JSON file per project and
drawing, `<folder>/<project id>/<drawing id>.json`, replaced whole on every edit; edits made
outside any project are `<folder>/<drawing id>.json` (where every edit went before review state
belonged to the project, so those older files are now that no-project state). One lock per
store serialises the updates of one process (the API runs one)."""

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

    def get(self, project_id: str | None, drawing_id: str) -> ReviewState:
        path = self._path(project_id, drawing_id)
        if not path.is_file():
            return ReviewState()
        return ReviewState.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def update(
        self,
        project_id: str | None,
        drawing_id: str,
        change: Callable[[ReviewState], ReviewState],
    ) -> ReviewState:
        with self._lock:
            state = change(self.get(project_id, drawing_id))
            path = self._path(project_id, drawing_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(path)
            return state

    def _path(self, project_id: str | None, drawing_id: str) -> Path:
        if project_id is None:
            return inside(self._folder, f"{drawing_id}.json")
        return inside(self._folder, f"{project_id}/{drawing_id}.json")
