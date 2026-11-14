"""Projects on disk (the `ProjectStore` port), under one root (`data/projects/`, gitignored):

    <project id>/project.json        the status and every file's trace
    <project id>/files/<path>        the files the pipeline reads, at their path in the archive
    <project id>/uploads/<path>      the upload's bytes of a file normalised before reading (an
                                     image turned upright by its EXIF orientation)
    outcomes/<key>.json              what ingest made of a file in its group, by content
    drawings/<drawing id>.json       the drawing model (the extraction_v1 fields)

Every JSON file is written to a temporary name and renamed, so a reader never sees half of one.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.adapters.paths import inside
from app.adapters.whole_file import write_whole
from app.core.drawing.model import Drawing
from app.core.errors import NotFoundError
from app.core.ingest.model import FileTrace, Outcome, ProjectStatus


class DiskProjectStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def files_dir(self, project_id: str) -> Path:
        return inside(self._root, project_id) / "files"

    def put_file(self, project_id: str, path: str, data: bytes) -> None:
        target = inside(self.files_dir(project_id), path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def read_file(self, project_id: str, path: str) -> bytes:
        target = inside(self.files_dir(project_id), path)
        if not target.is_file():
            raise NotFoundError(f"project {project_id} has no file {path}")
        return target.read_bytes()

    def put_upload(self, project_id: str, path: str, data: bytes) -> None:
        target = inside(inside(self._root, project_id) / "uploads", path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def read_upload(self, project_id: str, path: str) -> bytes:
        kept = inside(inside(self._root, project_id) / "uploads", path)
        return kept.read_bytes() if kept.is_file() else self.read_file(project_id, path)

    def project_ids(self) -> list[str]:
        if not self._root.is_dir():
            return []
        return sorted(found.parent.name for found in self._root.glob("*/project.json"))

    def save_project(self, status: ProjectStatus, traces: Mapping[str, FileTrace]) -> None:
        body = {
            "status": status.model_dump(mode="json"),
            "traces": {key: trace.model_dump(mode="json") for key, trace in traces.items()},
        }
        _write(inside(self._root, status.id) / "project.json", body)

    def load_project(self, project_id: str) -> tuple[ProjectStatus, dict[str, FileTrace]]:
        body = _read(inside(self._root, project_id) / "project.json", f"project {project_id}")
        traces = {key: FileTrace.model_validate(trace) for key, trace in body["traces"].items()}
        return ProjectStatus.model_validate(body["status"]), traces

    def outcome(self, key: str) -> Outcome | None:
        path = inside(self._root, f"outcomes/{key}.json")
        return Outcome.model_validate(_read(path, key)) if path.is_file() else None

    def save_outcome(self, outcome: Outcome, drawing: Drawing | None) -> None:
        if drawing is not None:  # first, so an outcome never names a drawing that is not there
            body = drawing.model_dump(mode="json", by_alias=True)
            _write(inside(self._root, f"drawings/{outcome.key}.json"), body)
        _write(inside(self._root, f"outcomes/{outcome.key}.json"), outcome.model_dump(mode="json"))

    def drawing(self, drawing_id: str) -> Drawing:
        body = _read(inside(self._root, f"drawings/{drawing_id}.json"), f"drawing {drawing_id}")
        return Drawing.model_validate(body)


def _write(path: Path, body: Any) -> None:
    write_whole(path, json.dumps(body, ensure_ascii=False) + "\n")


def _read(path: Path, what: str) -> Any:
    if not path.is_file():
        raise NotFoundError(f"no {what}")
    return json.loads(path.read_text(encoding="utf-8"))
