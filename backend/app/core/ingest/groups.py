"""Stages 4-10 of project ingest, one drawing group at a time.

Each group goes through the pipeline's own `ingest()` (app/core/pipeline/ingest.py) with its
ports wrapped to time every stage per sheet (timing.py). What each file of the group ended as is
stored as an `Outcome` keyed by content (the file's sha256 and its group's, plus the readers),
so the same group uploaded again is reused instead of read again, unless the run is fresh.
"""

import hashlib
import logging
from collections.abc import Callable, Mapping

from app.core.drawing.model import Drawing
from app.core.ingest.judge import judge, pipeline_stages, reading_flags
from app.core.ingest.model import Normalised, Outcome, SheetKind, StageTrace
from app.core.ingest.ports import Clock, ProjectStore, Readers
from app.core.ingest.progress import Run
from app.core.ingest.timing import (
    CollectingSink,
    StageClock,
    TimedCounter,
    TimedExtractor,
    TimedPages,
)
from app.core.pipeline.group import group, key_of
from app.core.pipeline.ingest import ingest
from app.core.pipeline.model import DrawingFile, DrawingGroup, FileKind, Route
from app.core.pipeline.ports import Extractor
from app.core.pipeline.route import route
from app.core.wording import count

logger = logging.getLogger(__name__)


class Groups:
    def __init__(
        self,
        store: ProjectStore,
        clock: Clock,
        names: Mapping[str, str],
        frames: dict[str, Normalised],
    ) -> None:
        """`frames`: by path, how each image sheet of the run was normalised."""
        self._store, self._clock, self._frames = store, clock, frames
        self._readers = dict(names)
        self._names = sorted(f"{port}={name}" for port, name in names.items())

    def run(
        self,
        run: Run,
        readers: Readers,
        drawings: dict[str, DrawingFile],
        saved: Callable[[], None],
    ) -> None:
        """`saved` is called after each group, so the stored status follows the run."""
        sources = {
            path: [drawings[found] for found in readers.finder.sources(path) if found in drawings]
            for path in drawings
        }
        groups = [
            (members, asked)
            for members in group(drawings.values(), sources)
            if (
                asked := [
                    file
                    for file in members.files
                    if file.path in drawings and key_of(file) == members.key
                ]
            )
        ]
        # Every file's group is known now: publish it before the first group is read, so a poll
        # counts the drawings to expect from the groups, not from the files (QA R4-a-1)
        for members, asked in groups:
            for file in asked:
                run.set(file.path, group=members.key)
        saved()
        for members, asked in groups:
            self._group(run, readers, members, asked)
            saved()

    def _group(
        self, run: Run, readers: Readers, members: DrawingGroup, asked: list[DrawingFile]
    ) -> None:
        started = self._clock()
        scans = _scans(run, members)
        routed = route(members, readers.readable, scans)
        scanned = routed.source.path in scans
        route_name = routed.route
        given = {file.path for file in asked}
        content = sorted(
            f"{file.sha256}:{'given' if file.path in given else 'found'}" for file in members.files
        )
        group_key = _hash(*content, *self._names)
        spent = _ms(self._clock, started) / len(asked)
        listed = ", ".join(file.path.rpartition("/")[2] for file in members.files)
        how = f"{route_name}, read from {routed.source.path}"
        if scanned:
            how += " (a scanned PDF: its page is an image, so the raster reader reads it)"
        for file in asked:
            run.set(file.path, group=members.key, route=route_name, source=routed.source.path)
            run.stage(file.path, "group", f"{members.key}: {listed}", spent,
                      output=count(len(members.files), "file"))  # fmt: skip
            run.stage(file.path, "route", how, 0.0, output=route_name)
        keys = {file.path: _hash(file.sha256, group_key)[:16] for file in asked}
        if not run.fresh:
            stored = [self._store.outcome(keys[file.path]) for file in asked]
            if all(outcome is not None for outcome in stored):
                for file, outcome in zip(asked, stored, strict=True):
                    if outcome is not None:
                        _reuse(run, file, members, outcome)
                return
        self._ingest(run, readers, members, asked, keys, route_name)

    def _ingest(
        self,
        run: Run,
        readers: Readers,
        members: DrawingGroup,
        asked: list[DrawingFile],
        keys: Mapping[str, str],
        route_name: Route,
    ) -> None:
        timer = StageClock(self._clock, on_start=lambda stage, path: _live(run, stage, path))
        extractors: dict[Route, Extractor] = {
            name: TimedExtractor(extractor, timer) for name, extractor in readers.extractors.items()
        }
        sink = CollectingSink(timer)
        for file in asked:
            run.set(file.path, state="running")
        try:
            report = ingest(
                [file.path for file in asked],
                files=readers.files,
                finder=readers.finder,
                pages=TimedPages(readers.pages, timer),
                extractors=extractors,
                second_counter=TimedCounter(readers.second_counter, timer),
                sink=sink,
                readable=readers.readable,
                scanned=readers.scanned,
            )
        except Exception as error:  # one bad file must not stop the project
            logger.warning("ingest of %s failed", members.key, exc_info=True)
            _failed(run, asked, timer, f"{type(error).__name__}: {error}")
            return
        sheets = {sheet.file: sheet for sheet in report.sheets}
        aside = {found.path: found.reason for found in report.set_aside}
        source = route(members, readers.readable, _scans(run, members)).source
        for file in asked:
            drawing = sink.drawings.get(file.path)
            stages: list[StageTrace] = []
            takeoff: dict[str, int | float] = {}
            flags: tuple[str, ...] = ()
            if file.path in sheets and drawing is not None:
                stages = pipeline_stages(
                    sheets[file.path].trace,
                    timer.ms.get(file.path, {}),
                    timer.usd.get(file.path, {}),
                )
                stages = _with_frame(
                    stages, self._frames.get(file.path), run.frame_ms.get(file.path, 0.0)
                )
                state, reason = judge(
                    drawing,
                    run.kinds[file.path],
                    route_name,
                    self._readers.get(route_name),
                    self._frames.get(file.path),
                )
                takeoff = sheets[file.path].takeoff
                flags = reading_flags(run.kinds[file.path], self._frames.get(file.path))
            elif file.path in aside:
                state, reason = "set_aside", aside[file.path]
            elif file == source:
                state, reason = "ready", f"the source {members.key} is read from"
            else:
                state = "ready"
                reason = (
                    f"another rendering of {members.key}; its drawing is read from {source.path}"
                )
            run.add_stages(file.path, stages)
            self._store_outcome(run, file, drawing, keys[file.path], source, route_name,
                                state=state, reason=reason, takeoff=takeoff,
                                stages=stages, flags=flags)  # fmt: skip

    def _store_outcome(
        self,
        run: Run,
        file: DrawingFile,
        drawing: Drawing | None,
        key: str,
        source: DrawingFile,
        route_name: Route,
        **found: object,
    ) -> None:
        started = self._clock()
        outcome = Outcome.model_validate(
            {
                "key": key,
                "project_id": run.id,
                "path": file.path,
                "sheet_kind": _sheet_kind(file.kind),
                "route": route_name,
                "source_sha256": source.sha256,
                "source": source.path,
                "has_drawing": drawing is not None,
                "normalised": self._frames.get(file.path),
                **found,
            }
        )
        self._store.save_outcome(outcome, drawing)
        if drawing is not None:
            run.stage(file.path, "write", f"drawing model {key} stored",
                      _ms(self._clock, started),
                      output=count(len(outcome.takeoff), "quantity", "quantities"))  # fmt: skip
        run.set(file.path, takeoff=outcome.takeoff, drawing_id=key if drawing is not None else None)
        run.finish(file.path, outcome.state, outcome.reason)


def _scans(run: Run, members: DrawingGroup) -> set[str]:
    """The group's scanned PDFs, as identify called them."""
    return {file.path for file in members.files if run.kinds.get(file.path) == "pdf_scan"}


def _reuse(run: Run, file: DrawingFile, members: DrawingGroup, outcome: Outcome) -> None:
    """The cache stage, then the stages of the first ingest up to its write, so the file's
    story stays readable and it ends at the stage the first ingest left it at (a file set aside
    at route stays at route); listed with `ms` 0, as this run spent no time on them."""
    source = next(
        (found.path for found in members.files if found.sha256 == outcome.source_sha256), None
    )
    ended = run.file(file.path).stage
    run.stage(file.path, "cache",
              f"seen before as {outcome.path} (project {outcome.project_id}) with the same group "
              "and readers: reused, nothing recomputed; the stages below are from that ingest",
              0.0, output=outcome.state)  # fmt: skip
    replayed = [stage.model_copy(update={"ms": 0.0, "cost_usd": 0.0}) for stage in outcome.stages]
    if outcome.has_drawing:
        did = f"drawing model {outcome.key} stored by that ingest"
        output = count(len(outcome.takeoff), "quantity", "quantities")
        replayed.append(StageTrace(stage="write", did=did, ms=0.0, output=output))
    run.add_stages(file.path, replayed)
    run.set(file.path, reused=True, takeoff=outcome.takeoff, source=source,
            stage=replayed[-1].stage if replayed else ended,
            drawing_id=outcome.key if outcome.has_drawing else None)  # fmt: skip
    run.finish(file.path, outcome.state, outcome.reason)


def _failed(run: Run, asked: list[DrawingFile], timer: StageClock, failure: str) -> None:
    stage, failed_at = timer.running or ("extract", "")
    for file in asked:
        for done, ms in timer.ms.get(file.path, {}).items():
            run.stage(file.path, done, "done", ms)
        if file.path == failed_at:
            run.stage(file.path, stage, "failed", 0.0, failure=failure)
            reason = f"failed at {stage}: {failure}"
        else:
            reason = f"not ingested: {failed_at or 'its group'} failed at {stage}: {failure}"
        run.finish(file.path, "set_aside", reason)


def _live(run: Run, stage: str, path: str) -> None:
    if run.has(path):
        run.set(path, stage=stage)


def _with_frame(stages: list[StageTrace], frame: Normalised | None, ms: float) -> list[StageTrace]:
    """The normalise stage says how an image was brought upright before the pipeline read it,
    and its time includes that (`ms`, taken at identify)."""
    if frame is None:
        return stages
    done: list[str] = []
    if frame.exif not in (None, 1):
        done.append(f"EXIF orientation {frame.exif} applied")
    if frame.rectified and frame.quad is not None:
        corners = ", ".join(f"({x:.2f}, {y:.2f})" for x, y in frame.quad)
        done.append(f"rectified by {frame.rectifier}: paper corners at {corners}")
    said = f"{'; '.join(done)}: {frame.width}x{frame.height} px; " if done else ""
    return [
        stage.model_copy(update={"did": said + stage.did, "ms": stage.ms + ms})
        if stage.stage == "normalise"
        else stage
        for stage in stages
    ]


def _ms(clock: Clock, started: float) -> float:
    return max(0.0, (clock() - started) * 1000)


def _hash(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _sheet_kind(kind: FileKind) -> SheetKind | None:
    match kind:
        case "pdf" | "png" | "jpeg" | "ifc":
            return kind
        case _:
            return None
