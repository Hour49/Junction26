"""The live record of one project being ingested: its files' states and traces, readable from
other threads while the run writes it."""

import logging
import threading

from app.core.errors import NotFoundError
from app.core.ingest.model import (
    ContentKind,
    Entry,
    FileState,
    FileStatus,
    FileTrace,
    ProjectStatus,
    Stage,
    StageTrace,
)

logger = logging.getLogger(__name__)


class Run:
    def __init__(self, status: ProjectStatus, fresh: bool) -> None:
        self.fresh = fresh  # ingest again even what the cache holds
        self.done = threading.Event()
        self.kinds: dict[str, ContentKind] = {}  # by path; written and read by the run only
        self.frame_ms: dict[str, float] = {}  # by path: the EXIF turn and the rectifier
        self._status = status
        self._files: list[FileStatus] = []
        self._stages: dict[str, list[StageTrace]] = {}
        self._index: dict[str, int] = {}  # by path
        self._lock = threading.Lock()

    @property
    def id(self) -> str:
        return self._status.id

    def has(self, path: str) -> bool:
        with self._lock:
            return path in self._index

    def add(self, entry: Entry) -> None:
        with self._lock:
            self._index[entry.path] = len(self._files)
            file_id = f"f{len(self._files) + 1}"
            self._files.append(FileStatus(id=file_id, path=entry.path, size=entry.size))
            self._stages[file_id] = []

    def file(self, path: str) -> FileStatus:
        with self._lock:
            return self._files[self._index[path]]

    def unfinished(self) -> list[str]:
        with self._lock:
            return [file.path for file in self._files if file.state in ("queued", "running")]

    def set(self, path: str, **changes: object) -> None:
        with self._lock:
            at = self._index[path]
            self._files[at] = self._files[at].model_copy(update=changes)

    def stage(
        self,
        path: str,
        stage: Stage,
        did: str,
        ms: float,
        *,
        output: str = "",
        failure: str | None = None,
    ) -> None:
        trace = StageTrace(stage=stage, did=did, ms=ms, output=output, failure=failure)
        self.add_stages(path, [trace])

    def add_stages(self, path: str, traces: list[StageTrace]) -> None:
        if not traces:
            return
        with self._lock:
            at = self._index[path]
            status = self._files[at]
            self._stages[status.id] += traces
            self._files[at] = status.model_copy(
                update={
                    "ms": status.ms + sum(trace.ms for trace in traces),
                    "cost_usd": status.cost_usd + sum(trace.cost_usd for trace in traces),
                    "stage": traces[-1].stage,
                }
            )

    def finish(self, path: str, state: FileState, reason: str) -> None:
        self.set(path, state=state, reason=reason)
        status = self.file(path)
        logger.info(
            "ingest: %s %s %s in %.1f ms: %s", status.path, status.kind, state, status.ms, reason
        )

    def set_project(self, **changes: object) -> None:
        with self._lock:
            self._status = self._status.model_copy(update=changes)

    def status(self) -> ProjectStatus:
        with self._lock:
            counts: dict[FileState, int] = {}
            for status in self._files:
                counts[status.state] = counts.get(status.state, 0) + 1
            cost = sum(status.cost_usd for status in self._files)
            return self._status.model_copy(
                update={"files": tuple(self._files), "counts": counts, "cost_usd": cost}
            )

    def trace(self, file_id: str) -> FileTrace:
        with self._lock:
            if file_id not in self._stages:
                raise NotFoundError(f"project {self._status.id} has no file {file_id}")
            status = self._files[int(file_id[1:]) - 1]
            return FileTrace(
                project_id=self._status.id, file=status, stages=tuple(self._stages[file_id])
            )

    def traces(self) -> dict[str, FileTrace]:
        with self._lock:
            ids = list(self._stages)
        return {file_id: self.trace(file_id) for file_id in ids}
