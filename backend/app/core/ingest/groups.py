"""Stages 4-10 of project ingest, several drawing groups at a time (`in_flight`).

Groups that read the same source (the sheets of one building and its model) are one lane, read one
after another, so a source is never read by two groups at once; lanes run side by side. A cold
upload is mostly waiting for model calls (Carbon, Gemini), so reading groups at once is what makes
it fast; what each group finds is the same as when they ran one by one.

Each group goes through the pipeline's own `ingest()` (app/core/pipeline/ingest.py) with its
ports wrapped to time every stage per sheet (timing.py). What each file of the group ended as is
stored as an `Outcome` keyed by content (the file's sha256 and its group's, plus the readers),
so the same group uploaded again is reused instead of read again, unless the run is fresh.
"""

import hashlib
import logging
import queue
import threading
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as wait_all
from pathlib import PurePosixPath

from app.core.drawing.model import Drawing, Page
from app.core.ingest.judge import judge, pipeline_stages, reading_flags, with_sheet_flag
from app.core.ingest.model import Normalised, Outcome, SheetKind, StageTrace, split_from
from app.core.ingest.ports import Clock, ProjectStore, Readers
from app.core.ingest.progress import Run
from app.core.ingest.timing import (
    CollectingSink,
    StageClock,
    TimedCounter,
    TimedExtractor,
    TimedPages,
)
from app.core.ingest.triage import sheet_flag
from app.core.pipeline.group import group, key_of
from app.core.pipeline.ingest import FALLBACK_ROUTE, ingest
from app.core.pipeline.model import DrawingFile, DrawingGroup, FileKind, Route
from app.core.pipeline.ports import Extractor, PageReader
from app.core.pipeline.route import route
from app.core.wording import count, route_words

logger = logging.getLogger(__name__)


class Groups:
    def __init__(
        self,
        store: ProjectStore,
        clock: Clock,
        names: Mapping[str, str],
        frames: dict[str, Normalised],
        in_flight: int = 1,
    ) -> None:
        """`frames`: by path, how each image sheet of the run was normalised. `in_flight`: lanes
        of groups read at once (INGEST_GROUPS_IN_FLIGHT)."""
        self._store, self._clock, self._frames = store, clock, frames
        self._in_flight = in_flight
        self._readers = dict(names)
        self._names = sorted(f"{port}={name}" for port, name in names.items())

    def run(
        self,
        run: Run,
        readers: Readers,
        drawings: dict[str, DrawingFile],
        saved: Callable[[], None],
    ) -> None:
        """`saved` is called after each group, on this thread, so the stored status follows the
        run. A group that raises does not stop the others; the first error is raised at the end."""
        groups, sources = _grouped(drawings, readers)
        # Every file's group is known now: publish it before the first group is read, so a poll
        # counts the drawings to expect from the groups, not from the files (QA R4-a-1)
        for members, asked in groups:
            for file in asked:
                run.set(file.path, group=members.key)
        saved()
        finished: queue.SimpleQueue[Exception | None] = queue.SimpleQueue()

        def read(lane: list[tuple[DrawingGroup, list[DrawingFile]]]) -> None:
            for members, asked in lane:
                try:
                    self._group(run, readers, members, asked)
                except Exception as error:  # the run fails, after the other groups
                    finished.put(error)
                else:
                    finished.put(None)

        lanes = _lanes(groups, sources)
        errors: list[Exception] = []
        with ThreadPoolExecutor(self._in_flight, thread_name_prefix="group") as pool:
            for lane in lanes:
                pool.submit(read, lane)
            for _ in groups:
                if (error := finished.get()) is not None:
                    errors.append(error)
                saved()
        if errors:
            raise errors[0]

    def feed(self, run: Run, readers: Readers, saved: Callable[[], None]) -> "Feed":
        """`run` for an upload whose files are still being identified: see `Feed`."""
        return Feed(self._group, self._in_flight, run, readers, saved)

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
            f"{file.sha256}:{'given' if file.path in given else 'found'}"
            + (":page 1" if file.path in run.split else "")  # not a reading of every page
            for file in members.files
        )
        group_key = _hash(*content, *self._names)
        spent = _ms(self._clock, started) / len(asked)
        listed = ", ".join(file.path.rpartition("/")[2] for file in members.files)
        how = f"{route_words(route_name)}, read from {routed.source.path}"
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
                pages=TimedPages(PageOne(readers.pages, frozenset(run.split)), timer),
                extractors=extractors,
                second_counter=TimedCounter(readers.second_counter, timer),
                sink=sink,
                readable=readers.readable,
                scanned=readers.scanned,
                fallback=_fallback(run, readers),
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
            read_on = sheets[file.path].route if file.path in sheets else route_name
            as_image = read_on == FALLBACK_ROUTE and route_name != FALLBACK_ROUTE
            if as_image:
                run.set(file.path, route=read_on)
                run.stage(file.path, "route", FELL_BACK, 0.0, output=read_on)
            if file.path in sheets and drawing is not None:
                carbon_read = readers.carbon_read
                carbon = carbon_read(file.path) if read_on == "raster" and carbon_read else None
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
                    read_on,
                    self._readers.get(read_on),
                    self._frames.get(file.path),
                    carbon,
                    as_image,
                )
                takeoff = sheets[file.path].takeoff
                flags = reading_flags(
                    run.kinds[file.path], self._frames.get(file.path), carbon, as_image
                )
            elif file.path in aside:
                state, reason = "set_aside", aside[file.path]
            elif file == source:
                state, reason = "ready", f"the source {members.key} is read from"
            else:
                state = "ready"
                reason = (
                    f"another rendering of {members.key}; its drawing is read from {source.path}"
                )
            if file.path in run.cut and state != "set_aside":
                last, pages = run.cut[file.path]
                reason += f"; read pages 1-{last} of {pages}; the rest were not read"
            run.add_stages(file.path, stages)
            self._store_outcome(run, file, drawing, keys[file.path], source, read_on,
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
        _finish(run, file.path, outcome)


Found = tuple[DrawingGroup, list[DrawingFile]]  # a group and the files it is read for


def _grouped(
    drawings: Mapping[str, DrawingFile], readers: Readers
) -> tuple[list[Found], dict[str, list[DrawingFile]]]:
    """Stage 4: the groups of `drawings` (in their order) with the files each is read for, and
    the sources found for each file."""
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
    return groups, sources


def _key(path: str) -> str:
    """The group a file at `path` would be in by its own name (`key_of`)."""
    return str(PurePosixPath(path).with_suffix(""))


class Feed:
    """Stages 4-10 while the upload's files are still being identified: a group is read as soon
    as every file that could join it is identified, not once the whole upload is (codecheck,
    2026-11-15: the 10 cold files' groups all waited 17.4 s for the slowest check). What could
    join a group: a file of the same name (`key_of`), a file found as a source of one of its
    files, a later page of a PDF (`<name>#p<n>`, a file of its own). So each group is the group
    `Groups.run` reads. Groups that share a file, a source or a content are read one after
    another in upload order, the later one when the earlier has ended, as `run`'s lanes are.

    A group also waits for an earlier copy of one of its files, so the copy read first is the
    first one uploaded, whichever check ends first.

    The caller (IngestService._unpack) says each file to identify (`pending`, in upload order),
    then what it is (`identified`: its drawing, or None), then `unpacked` when the upload holds
    no more files; `wait` then waits for the groups and raises the first error."""

    def __init__(
        self,
        read: Callable[[Run, Readers, DrawingGroup, list[DrawingFile]], None],
        in_flight: int,
        run: Run,
        readers: Readers,
        saved: Callable[[], None],
    ) -> None:
        """`read`: one group's stages 4-10 (`Groups._group`); `in_flight`: groups read at once."""
        self._read, self._run, self._readers, self._saved = read, run, readers, saved
        self._order: dict[str, int] = {}  # by path: its place in the upload
        self._pending: set[str] = set()
        self._content: dict[str, str] = {}  # by path: its sha256
        self._drawings: dict[str, DrawingFile] = {}
        self._unpacked = False
        self._started: set[str] = set()  # group keys
        self._after: dict[str, Future[None]] = {}  # a path or content -> its latest group's read
        self._sources: dict[str, Sequence[str]] = {}  # by path, the finder's answer
        self._finished: queue.SimpleQueue[Exception | None] = queue.SimpleQueue()
        self._reads = 0
        self._pool = ThreadPoolExecutor(in_flight, thread_name_prefix="group")
        self._lock = threading.Lock()

    def pending(self, path: str, sha256: str) -> None:
        with self._lock:
            self._order.setdefault(path, len(self._order))
            self._content[path] = sha256
            self._pending.add(path)

    def identified(self, path: str, drawing: DrawingFile | None) -> None:
        with self._lock:
            self._pending.discard(path)
            if drawing is not None:
                self._drawings[path] = drawing
            self._release()

    def unpacked(self) -> None:
        with self._lock:
            self._unpacked = True
            self._release()

    def wait(self) -> None:
        """Every group read, `saved` called after each; the first error raised after them all."""
        with self._lock:
            assert self._unpacked and not self._pending, "wait() before every file was identified"
            reads = self._reads
        errors: list[Exception] = []
        for _ in range(reads):  # as each group ends, so the stored status follows the run
            if (error := self._finished.get()) is not None:
                errors.append(error)
            self._saved()
        self.close()
        if errors:
            raise errors[0]

    def close(self) -> None:
        """Wait for the groups already started (the upload failed before every file was in)."""
        self._pool.shutdown(wait=True)

    def _sources_of(self, path: str) -> Sequence[str]:
        if path not in self._sources:
            self._sources[path] = self._readers.finder.sources(path)
        return self._sources[path]

    def _waits_for(self, path: str, members: DrawingGroup) -> bool:
        """Whether `members`'s group waits for the file at `path`, not identified yet: it could
        join the group, or it is an earlier copy of one of its files (read first, as in upload
        order, so the later copy is the one that reuses its reading)."""
        if self._could_join(path, members):
            return True
        return any(
            self._content[path] == file.sha256 and self._order[path] < self._order[file.path]
            for file in members.files
            if file.path in self._order
        )

    def _could_join(self, path: str, members: DrawingGroup) -> bool:
        """Whether the file at `path`, not identified yet, could be in `members`'s group."""
        if _key(path) == members.key:
            return True
        if any(path in self._sources_of(file.path) for file in members.files):
            return True
        return path.lower().endswith(".pdf") and members.key.startswith(f"{_key(path)}#p")

    def _release(self) -> None:
        """Start every group no file still to identify could join (under the lock)."""
        if not self._unpacked:
            return
        drawings = dict(sorted(self._drawings.items(), key=lambda item: self._order[item[0]]))
        groups, _ = _grouped(drawings, self._readers)
        ready = [
            (members, asked)
            for members, asked in groups
            if members.key not in self._started
            and not any(self._waits_for(path, members) for path in self._pending)
        ]
        if not ready:
            return
        for members, asked in ready:  # published before it is read (QA R4-a-1)
            for file in asked:
                self._run.set(file.path, group=members.key)
        self._saved()
        for found in ready:
            self._start(found)

    def _start(self, found: Found) -> None:
        members, asked = found
        files = members.files  # with the sources found for them (`group`)
        keys = {f"path {file.path}" for file in files} | {f"sha256 {file.sha256}" for file in files}
        earlier = {self._after[key] for key in keys if key in self._after}

        def read() -> None:
            wait_all(earlier)  # submitted before this one, so already running or done
            try:
                self._read(self._run, self._readers, members, asked)
            except Exception as error:  # the run fails, after the other groups
                self._finished.put(error)
            else:
                self._finished.put(None)

        started = self._pool.submit(read)
        for key in keys:
            self._after[key] = started
        self._started.add(members.key)
        self._reads += 1


def _lanes[G: tuple[DrawingGroup, list[DrawingFile]]](
    groups: Sequence[G], sources: Mapping[str, list[DrawingFile]]
) -> list[list[G]]:
    """The groups as lanes, in upload order: groups that share a file or a source (a building's
    sheets and its model, whose parsed model the readers keep) are one lane, and so are groups
    with a file of the same content, so the later one reuses what the first stored."""
    lane_of: dict[str, int] = {}  # a path or a content hash -> its lane's number
    lanes: list[list[G]] = []
    for found in groups:
        members, asked = found
        files = [
            *members.files,
            *(source for file in asked for source in sources.get(file.path, [])),
        ]
        paths = {f"path {file.path}" for file in files} | {
            f"sha256 {file.sha256}" for file in files
        }
        joined = sorted({lane_of[path] for path in paths if path in lane_of})
        if not joined:
            lanes.append([])
            joined = [len(lanes) - 1]
        into = joined[0]
        for other in joined[1:]:  # this group links two lanes: one lane, in upload order
            lanes[into] += lanes[other]
            lanes[other] = []
        lanes[into].append(found)
        for path, at in list(lane_of.items()):
            if at in joined:
                lane_of[path] = into
        for path in paths:
            lane_of[path] = into
    order = {id(found): at for at, found in enumerate(groups)}
    return [sorted(lane, key=lambda found: order[id(found)]) for lane in lanes if lane]


FELL_BACK = (
    "the vector reader read nothing (no reading rules for this drawn PDF): VECTOR_FALLBACK read"
    " its page as an image on the raster route"
)


def _scans(run: Run, members: DrawingGroup) -> set[str]:
    """The group's scanned PDFs, as identify called them."""
    return {file.path for file in members.files if run.kinds.get(file.path) == "pdf_scan"}


def _fallback(run: Run, readers: Readers) -> Callable[[str], bool] | None:
    """VECTOR_FALLBACK=raster: whether a file the vector route read nothing of is a drawn PDF it
    has no rules for, which the raster route then reads as the image of its page
    (pipeline/ingest.py `fallback`); None when the fallback is off. Page 1 of an upload only: the
    later pages ingest split off a set (`split_from` its record, not the file's name) stay as the
    vector route reads them, so one upload costs at most one image reading (Carbon on a large
    page: 0.03 to 0.38 USD, median 0.10; an 8-page set read whole was 0.66 USD, think-local r10).
    That reading is paid for even when it finds nothing and is dropped (review-348 N1)."""
    unruled = readers.unruled
    if unruled is None:
        return None
    return lambda path: (
        run.kinds.get(path) == "pdf_vector"
        and split_from(path, run.split) is None
        and unruled(readers.files.read(path))
    )


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
    _finish(run, file.path, outcome)


def _finish(run: Run, path: str, outcome: Outcome) -> None:
    """The file ends as its reading did, flagged when this project's triage doubts the sheet
    (with_sheet_flag): read fresh or reused, the flag follows the triage, not the cache."""
    flag = sheet_flag(run.file(path).triage) if outcome.has_drawing else None
    run.finish(path, *with_sheet_flag(outcome.state, outcome.reason, flag))


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


class PageOne:
    """The pages of each sheet file, but only page 1 of a PDF whose later drawn pages are read as
    files of their own (`<name>#p<n>.pdf`), so the set's drawing does not show them again."""

    def __init__(self, inner: PageReader, split: frozenset[str]) -> None:
        self._inner, self._split = inner, split

    def pages(self, file: DrawingFile) -> tuple[Page, ...]:
        found = self._inner.pages(file)
        return found[:1] if file.path in self._split else found


def _hash(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _sheet_kind(kind: FileKind) -> SheetKind | None:
    match kind:
        case "pdf" | "png" | "jpeg" | "ifc":
            return kind
        case _:
            return None
