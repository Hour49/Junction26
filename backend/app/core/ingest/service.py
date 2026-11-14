"""Project ingest: an upload (a zip or one file) in, every file ends ready, flagged, text only or
set aside with a reason, and a trace per file and stage. Docs: docs/PIPELINE.md section 1, the
interface for the API in .agents/ingest.md.

Stages 1-3 (unpack, hash, identify by content) and an image's frame (EXIF orientation) run here.
Stages 4-10 are the pipeline's own, one drawing group at a time (groups.py). A group whose files
(by content) were ingested before with the same readers is reused, unless the upload is fresh.
"""

import hashlib
import logging
import threading
from collections import deque
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor

from app.core import cost
from app.core.drawing.model import Drawing
from app.core.errors import (
    DomainError,
    InvalidInputError,
    NotFoundError,
    NotTriagedError,
)
from app.core.ingest.groups import Groups
from app.core.ingest.model import (
    DRAWING_KINDS,
    TEXT_KINDS,
    ContentKind,
    DrawingInfo,
    Entry,
    FileState,
    FileStatus,
    FileTrace,
    LaterPage,
    Normalised,
    Overrule,
    Probed,
    ProjectState,
    ProjectStatus,
    ReadAsPlan,
    SheetFile,
    Unavailable,
    page_path,
)
from app.core.ingest.ports import (
    Clock,
    ContentProbe,
    ImageFrame,
    NewId,
    Now,
    ProjectStore,
    Readers,
    Rectifier,
    Runner,
    Unpacker,
)
from app.core.ingest.progress import Run
from app.core.ingest.triage import (
    NOTE_FAILED,
    NOTE_JUDGE_FAILED,
    NOTE_NO_JUDGE,
    NOTE_RUNNING,
    Triaged,
    TriageSteps,
    called_not_plan,
    context_of,
    judged,
    judged_note,
    kind_after,
    overruled,
    plan_kind,
    read_as_plan,
    relevance_of,
    set_aside_reason,
    to_judge,
    triaged,
)
from app.core.pipeline.identify import sniff
from app.core.pipeline.model import DrawingFile
from app.core.review.review import NotAllowedError
from app.core.wording import kind_words

logger = logging.getLogger(__name__)
# Files probed at once (stage 3) while the upload is unpacked. A probe can ask a remote service
# (DECISIONS_KIND: 0.6-2.9 s per drawing image); 4 is the limit the served readers' clients keep.
# Results are applied in upload order, so states and traces are the serial run's.
PROBES_IN_FLIGHT = 4

IMAGE_KINDS = frozenset({"png_plan", "jpeg_plan", "photo_plan"})
RESTARTED = "the server restarted during ingest"
REREAD_CUT = "not read as a floor plan: the server restarted while it was read as a floor plan"


class IngestService:
    def __init__(
        self,
        *,
        unpacker: Unpacker,
        probe: ContentProbe,
        frame: ImageFrame,
        rectifier: Rectifier,
        store: ProjectStore,
        readers: Callable[[str], Readers],
        reader_names: Mapping[str, str],
        runner: Runner,
        clock: Clock,
        now: Now,
        new_id: NewId,
        triage: TriageSteps | None = None,
    ) -> None:
        """`readers(project_id)`: the pipeline's ports over that project's files.
        `reader_names`: which adapter reads each route, shown in the status and part of the
        cache key, so changing a reader re-ingests. `triage`: file triage (decision 0010); None
        is off, ingest as before it existed. It is shown in the status but is not part of the
        cache key: it decides which files are read, not how a plan is read."""
        self._unpacker, self._probe, self._frame, self._store = unpacker, probe, frame, store
        self._rectifier = rectifier
        self._readers, self._names = readers, dict(reader_names)
        self._runner, self._clock, self._now, self._new_id = runner, clock, now, new_id
        self._triage = triage
        self._lock = threading.Lock()
        self._live: dict[str, Run] = {}

    # ---------------------------------------------------------------- the interface

    def start(self, name: str, data: bytes, fresh: bool = False) -> str:
        """Queues the upload and returns its project id at once. `fresh`: ingest every file
        again, even what the cache holds (the stored outcomes are replaced)."""
        if not data:
            raise InvalidInputError(f"{name}: the upload is empty")
        status = ProjectStatus(
            id=self._new_id(),
            name=name,
            state="queued",
            created_at=self._now(),
            readers={**self._names, **self._shown()},
        )
        run = Run(status, fresh)
        with self._lock:
            self._live[run.id] = run
        self._save(run)
        self._runner.submit(lambda: self._run(run, name, data))
        return run.id

    def status(self, project_id: str) -> ProjectStatus:
        run = self._running(project_id)
        return run.status() if run is not None else self._store.load_project(project_id)[0]

    def projects(self) -> tuple[ProjectStatus, ...]:
        """Every project, newest first."""
        found = [self.status(project_id) for project_id in self._store.project_ids()]
        return tuple(sorted(found, key=lambda status: (status.created_at, status.id), reverse=True))

    def trace(self, project_id: str, file_id: str) -> FileTrace:
        run = self._running(project_id)
        if run is not None:
            return run.trace(file_id)
        traces = self._store.load_project(project_id)[1]
        if file_id not in traces:
            raise NotFoundError(f"project {project_id} has no file {file_id}")
        return traces[file_id]

    def traces(self, project_id: str) -> tuple[FileTrace, ...]:
        """The trace of every file of the project, in the order the upload lists them."""
        run = self._running(project_id)
        found = run.traces() if run is not None else self._store.load_project(project_id)[1]
        return tuple(found[file_id] for file_id in sorted(found, key=lambda key: int(key[1:])))

    def drawing(self, drawing_id: str) -> Drawing:
        return self._store.drawing(drawing_id)

    def drawing_info(self, drawing_id: str) -> DrawingInfo:
        outcome = self._store.outcome(drawing_id)
        if outcome is None or not outcome.has_drawing or outcome.sheet_kind is None:
            raise NotFoundError(f"no drawing {drawing_id}")
        return DrawingInfo(
            drawing_id=drawing_id,
            project_id=outcome.project_id,
            path=outcome.path,
            kind=outcome.sheet_kind,
            route=outcome.route,
            source=outcome.source,
            normalised=outcome.normalised,
            flags=outcome.flags,
        )

    def sheet(self, drawing_id: str) -> SheetFile:
        """The sheet as the pipeline read it: an image is normalised (EXIF applied), so its
        page size, every box and the served page are in one frame."""
        info = self.drawing_info(drawing_id)
        if info.kind == "ifc":
            raise NotFoundError(f"drawing {drawing_id} is a building model: it has no page")
        return SheetFile(
            drawing_id=drawing_id,
            path=info.path,
            kind=info.kind,
            route=info.route,
            source=info.source,
            data=self._store.read_file(info.project_id, info.path),
            normalised=info.normalised,
        )

    def upload_bytes(self, project_id: str, file_id: str) -> bytes:
        """The file as it was uploaded, before any normalising."""
        path = self.trace(project_id, file_id).file.path
        return self._store.read_upload(project_id, path)

    def wait(self, project_id: str, timeout: float | None = None) -> ProjectStatus:
        """Blocks until the project is finished (for tests and the CLI, not for routes)."""
        run = self._running(project_id)
        if run is not None and not run.done.wait(timeout):
            raise TimeoutError(f"project {project_id} still running after {timeout} s")
        return self.status(project_id)

    def recover(self) -> list[str]:
        """At startup: a project the store says is queued or running was cut off by a restart.
        It becomes failed, its unfinished files set aside, so no screen polls it for ever. A
        done project's file cut off while it was read again as a floor plan is set aside, back to
        triage's call so a person can ask again, and the project stays done. Returns the ids it
        marked. Call before the first `start`."""
        marked: list[str] = []
        for project_id in self._store.project_ids():
            status, traces = self._store.load_project(project_id)
            cut = status.state in ("queued", "running")
            unfinished = any(file.state in ("queued", "running") for file in status.files)
            if not (cut or unfinished) or self._running(project_id):
                continue
            files = tuple(
                file.model_copy(update=_cut(file, cut))
                if file.state in ("queued", "running")
                else file
                for file in status.files
            )
            traces = {
                key: trace.model_copy(update={"file": files[int(key[1:]) - 1]})
                for key, trace in traces.items()
            }
            counts: dict[FileState, int] = {}
            for file in files:
                counts[file.state] = counts.get(file.state, 0) + 1
            update: dict[str, object] = {"files": files, "counts": counts}
            if cut:
                update |= {"state": "failed", "error": RESTARTED}
            self._store.save_project(status.model_copy(update=update), traces)
            marked.append(project_id)
        return marked

    def read_as_plan(self, project_id: str, file_id: str, call: ReadAsPlan) -> FileStatus:
        """A person says a file triage set aside is a floor plan (decision 0010): it is read as
        one in the background, alone, through the usual group, route and readers, while the
        project stays done. Returns the file as queued; poll the project for the rest."""
        with self._lock:
            if project_id in self._live:
                raise NotAllowedError(f"project {project_id} is still being read; try again")
            status, traces = self._store.load_project(project_id)
            if status.state != "done":
                raise NotAllowedError(f"project {project_id} is {status.state}, not done")
            if file_id not in traces:
                raise NotFoundError(f"project {project_id} has no file {file_id}")
            file = traces[file_id].file
            if file.triage is None or not called_not_plan(file):
                raise NotTriagedError(
                    f"file {file_id} was not set aside by triage as not a floor plan"
                )
            if file.triage.read_as_plan is not None:
                raise NotAllowedError(
                    f"file {file_id} was read as a floor plan already "
                    f"({file.triage.read_as_plan.by})"
                )
            run = Run.resumed(status, traces)
            triage = read_as_plan(file.triage, call)
            reason = "queued to be read as a floor plan"
            run.set(file.path, triage=triage, state="queued", reason=reason)
            self._live[project_id] = run
        queued = run.file(file.path)
        self._save(run)
        self._runner.submit(lambda: self._reread(run, file.path, call))
        return queued

    def overrule(self, project_id: str, file_id: str, overrule: Overrule | None) -> FileStatus:
        """A person's call on a triaged file's relevance (decision 0010), kept in the project's
        status so every view of the file shows it; None takes it back. Only in a finished
        project, for any file triage called not a floor plan, described and judged or not, so a
        person can settle every `unrelated_file` issue."""
        with self._lock:
            if project_id in self._live:
                raise NotAllowedError(f"project {project_id} is still being ingested")
            status, traces = self._store.load_project(project_id)
            if status.state != "done":
                raise NotAllowedError(f"project {project_id} is {status.state}, not done")
            if file_id not in traces:
                raise NotFoundError(f"project {project_id} has no file {file_id}")
            file = traces[file_id].file
            if overrule is None and (file.triage is None or file.triage.overruled is None):
                return file  # nothing to take back: unchanged
            if file.triage is None or not called_not_plan(file):
                raise NotTriagedError(
                    f"file {file_id} was not set aside by triage as not a floor plan"
                )
            changed = file.model_copy(update={"triage": overruled(file.triage, overrule)})
            files = tuple(changed if found.id == file_id else found for found in status.files)
            traces[file_id] = traces[file_id].model_copy(update={"file": changed})
            self._store.save_project(status.model_copy(update={"files": files}), traces)
        return changed

    def close(self) -> None:
        self._runner.close()

    # ---------------------------------------------------------------- the run

    def _run(self, run: Run, name: str, data: bytes) -> None:
        started = self._clock()
        state: ProjectState = "done"
        error: str | None = None
        run.set_project(state="running", started_at=self._now())
        try:
            frames: dict[str, Normalised] = {}
            drawings = self._unpack(run, name, data, frames)
            self._save(run)
            if drawings:
                groups = Groups(self._store, self._clock, self._names, frames)
                groups.run(run, self._readers(run.id), drawings, lambda: self._save(run))
        except DomainError as failure:
            state, error = "failed", str(failure)
        except Exception as failure:  # a bug: the project says so instead of hanging
            logger.exception("ingest of project %s failed", run.id)
            state, error = "failed", f"{type(failure).__name__}: {failure}"
        if error is not None:
            for path in run.unfinished():
                run.finish(path, "set_aside", f"not ingested: {error}")
        self._judge(run, failed=error is not None)
        ms = (self._clock() - started) * 1000
        run.set_project(state=state, error=error, ms=ms, finished_at=self._now())
        self._save(run)
        with self._lock:
            del self._live[run.id]
        run.done.set()
        logger.info("ingest: project %s %s in %.0f ms", run.id, state, ms)

    def _unpack(
        self, run: Run, name: str, data: bytes, frames: dict[str, Normalised]
    ) -> dict[str, DrawingFile]:
        """Stages 1-3 for every file. Returns the drawing files by path, for the pipeline."""
        drawings: dict[str, DrawingFile] = {}
        first_of: dict[str, str] = {}  # sha256 -> the first path with that content
        entries = self._unpacker.entries(name, data)
        # Probed ahead in a bounded window, identified in upload order.
        probing: deque[tuple[str, bytes, Future[tuple[Probed, float, float, Triaged]]]] = deque()

        def identify_next() -> None:
            path, read, probed = probing.popleft()
            found = self._identify(run, path, read, probed, first_of, frames)
            if found is not None:
                drawings[path] = found
            if probed.exception() is None:  # a failed probe was set aside by `_identify`
                for page in probed.result()[0].pages:
                    run.split.add(path)
                    self._page_file(run, path, page, first_of, frames, drawings)

        with ThreadPoolExecutor(PROBES_IN_FLIGHT, thread_name_prefix="probe") as pool:
            while True:
                started = self._clock()
                entry = next(entries, None)
                if entry is None:
                    break
                unpacked = self._ms(started)
                if run.has(entry.path):
                    entry = Entry(
                        path=entry.path, size=entry.size, refused="a second file at a path"
                    )
                run.add(entry)
                if entry.data is None:
                    reason = entry.refused or "not read"
                    run.stage(entry.path, "unpack", "refused", unpacked, failure=reason)
                    run.finish(entry.path, "set_aside", reason)
                    continue
                started = self._clock()
                self._store.put_file(run.id, entry.path, entry.data)
                run.stage(entry.path, "unpack", f"path checked, {entry.size} bytes",
                          unpacked + self._ms(started), output=entry.path)  # fmt: skip
                probing.append((entry.path, entry.data, pool.submit(self._probed, entry.data)))
                if len(probing) >= PROBES_IN_FLIGHT:
                    identify_next()
            while probing:
                identify_next()
        return drawings

    def _page_file(
        self,
        run: Run,
        path: str,
        page: LaterPage,
        first_of: dict[str, str],
        frames: dict[str, Normalised],
        drawings: dict[str, DrawingFile],
    ) -> None:
        """A later drawn page of the PDF at `path`, unpacked as a file of its own
        (`<name>#p<n>.pdf`, its own group) and identified like any file of the upload."""
        started = self._clock()
        named = page_path(path, page.number)
        if run.has(named):
            run.add(Entry(path=named, size=len(page.data), refused="a second file at a path"))
            run.stage(named, "unpack", "refused", 0.0, failure="a second file at a path")
            run.finish(named, "set_aside", "a second file at a path")
            return
        run.add(Entry(path=named, size=len(page.data), data=page.data))
        self._store.put_file(run.id, named, page.data)
        run.stage(named, "unpack", f"page {page.number} of {path}, as a PDF of its own",
                  self._ms(started), output=named)  # fmt: skip
        probed: Future[tuple[Probed, float, float, Triaged]] = Future()
        probed.set_result(self._probed(page.data))
        found = self._identify(run, named, page.data, probed, first_of, frames)
        if found is not None:
            drawings[named] = found

    def _probed(self, data: bytes) -> tuple[Probed, float, float, Triaged]:
        """Stage 3's probe, then triage's classifier and describer (decision 0010), their time
        and the model calls they paid for, on a probing thread."""
        started, spent = self._clock(), cost.spent()
        probed = self._probe.probe(data)
        found = Triaged(None, "")
        if self._triage is not None:
            found = triaged(self._triage, data, probed, sniff(data))
        return probed, self._ms(started), cost.spent() - spent, found

    def _identify(
        self,
        run: Run,
        path: str,
        data: bytes,
        probing: Future[tuple[Probed, float, float, Triaged]],
        first_of: dict[str, str],
        frames: dict[str, Normalised],
    ) -> DrawingFile | None:
        started = self._clock()
        sha256 = hashlib.sha256(data).hexdigest()
        copy = first_of.setdefault(sha256, path)
        same = f", same content as {copy}" if copy != path else ""
        run.stage(path, "hash", f"sha256 {sha256[:12]}{same}", self._ms(started), output=sha256)
        run.set(path, sha256=sha256)
        started = self._clock()
        try:
            probed, identified, paid, found = probing.result()
            probed = kind_after(probed, found.triage, sniff(data))
            not_plan = found.triage is not None and found.triage.class_ != "floor_plan"
            framed = None
            if probed.kind in IMAGE_KINDS and not not_plan:  # timed as the normalise stage
                framing = self._clock()
                framed = self._upright(data, probed.kind)
                run.frame_ms[path] = self._ms(framing)
        except Exception as error:  # one unreadable file must not stop the project
            logger.warning("identifying %s failed", path, exc_info=True)
            failure = f"{type(error).__name__}: {error}"
            run.stage(path, "identify", "failed", self._ms(started), failure=failure)
            run.finish(path, "set_aside", f"failed at identify: {failure}")
            return None
        file_format = sniff(data)
        if framed is not None:
            upright, frames[path] = framed
            run.set(path, normalised=frames[path])
            if upright is not data:  # the pipeline reads, and the API serves, the upright image
                self._store.put_upload(run.id, path, data)
                self._store.put_file(run.id, path, upright)
                data = upright
        did = f"{probed.did}; {found.said}" if found.said else probed.did
        run.stage(path, "identify", did, identified, output=kind_words(probed.kind), cost_usd=paid)
        run.set(path, kind=probed.kind, triage=found.triage)
        run.kinds[path] = probed.kind
        if found.triage is not None and not_plan:  # kept, described, not read (decision 0010)
            run.finish(path, "set_aside", set_aside_reason(found.triage))
        elif probed.kind in TEXT_KINDS:
            run.finish(path, "text_only", probed.did)
        elif probed.kind not in DRAWING_KINDS or file_format is None:
            run.finish(path, "set_aside", probed.did)
        else:
            return DrawingFile(path=path, size=len(data), sha256=sha256, kind=file_format)
        return None

    def _upright(self, data: bytes, kind: ContentKind) -> tuple[bytes, Normalised] | None:
        """Stage 6 for an image, once: the EXIF turn, then the rectifier on the upright image.
        The result is the frame the page size, every box and the served page are in."""
        framed = self._frame.normalise(data)
        if framed is None:
            return None
        upright, normalised = framed
        found = self._rectifier.rectify(upright, kind)
        if found is None:
            return framed
        return found.data, normalised.model_copy(
            update={
                "rectified": True,
                "quad": found.quad,
                "width": found.width,
                "height": found.height,
                "rectifier": found.method,
            }
        )

    def _reread(self, run: Run, path: str, call: ReadAsPlan) -> None:
        """Reads one file of a finished project as a floor plan: framed as an image, then its
        group, route and readers as at upload. A failure sets the file aside with its reason;
        the project stays done."""
        started = self._clock()
        run.set(path, state="running", reason="being read as a floor plan")
        self._save(run)
        try:
            data = self._store.read_file(run.id, path)
            file = run.file(path)
            file_format = sniff(data)
            kind = plan_kind(file.kind, file_format)
            if kind is None or file_format is None or kind not in DRAWING_KINDS:
                found = kind_words(file.kind or "unknown")
                raise InvalidInputError(f"a file read as {found} can't be read as a floor plan")
            frames: dict[str, Normalised] = {}
            if kind in IMAGE_KINDS:
                framed = self._upright(data, kind)
                if framed is not None:
                    upright, frames[path] = framed
                    run.set(path, normalised=frames[path])
                    if upright is not data:
                        self._store.put_upload(run.id, path, data)
                        self._store.put_file(run.id, path, upright)
                        data = upright
            run.stage(path, "identify", f"read as a floor plan, as {call.by} asked",
                      self._ms(started), output=kind_words(kind))  # fmt: skip
            run.set(path, kind=kind)
            run.kinds[path] = kind
            drawing = DrawingFile(
                path=path, size=len(data), sha256=hashlib.sha256(data).hexdigest(), kind=file_format
            )
            groups = Groups(self._store, self._clock, self._names, frames)
            groups.run(run, self._readers(run.id), {path: drawing}, lambda: self._save(run))
        except DomainError as failure:
            self._unread(run, path, f"not read as a floor plan: {failure}")
        except Exception as failure:  # a bug: the file says so, the project stays done
            logger.exception("reading %s of project %s as a floor plan failed", path, run.id)
            self._unread(run, path, f"not read as a floor plan: {type(failure).__name__}")
        finally:
            self._save(run)
            with self._lock:
                del self._live[run.id]
            run.done.set()

    def _unread(self, run: Run, path: str, reason: str) -> None:
        """A re-read that failed: the file is set aside with its reason and back to triage's
        call (no `read_as_plan`), so a person can ask again."""
        triage = run.file(path).triage
        if triage is not None:
            run.set(path, triage=read_as_plan(triage, None))
        run.finish(path, "set_aside", reason)

    def _judge(self, run: Run, failed: bool) -> None:
        """Triage step 3, once every file is finished: each described file (and, for a judge
        that reads no description, each undescribed one) judged against the project's plans,
        names and other descriptions. A file that can't be judged gets a note saying why;
        nothing stops the project. `failed`: the run failed, so nothing is judged."""
        if self._triage is None:
            return
        files = run.status().files
        waiting = [
            file for file in files if file.triage is not None and file.triage.note == NOTE_RUNNING
        ]
        judge = self._triage.judge
        if failed or judge is None:
            for file in waiting:
                assert file.triage is not None
                note = NOTE_FAILED if failed else NOTE_NO_JUDGE
                run.set(file.path, triage=judged(file.triage, None, note))
            return
        drawings = {
            file.drawing_id: self._store.drawing(file.drawing_id)
            for file in files
            if file.drawing_id is not None
        }
        context = context_of(run.status().name, files, drawings)
        for file in to_judge(files, judge):
            assert file.triage is not None
            spent = cost.spent()
            try:
                found = relevance_of(
                    judge, file.triage.class_, file.triage.description, context, file.path
                )
            except Exception:  # one file's judging must not stop the project
                logger.warning("judging the relevance of %s failed", file.path, exc_info=True)
                note = judged_note(file.triage, NOTE_JUDGE_FAILED)
                run.set(file.path, triage=judged(file.triage, None, note))
                continue
            paid = cost.spent() - spent  # counted in the file's and the project's cost
            if isinstance(found, Unavailable):
                note = judged_note(file.triage, f"not judged: {found.note}")
                triage = judged(file.triage, None, note)
            else:
                triage = judged(file.triage, found, judged_note(file.triage, None))
            run.set(file.path, triage=triage, cost_usd=file.cost_usd + paid)

    def _shown(self) -> dict[str, str]:
        return {} if self._triage is None else {"triage": self._triage.name}

    # ---------------------------------------------------------------- helpers

    def _running(self, project_id: str) -> Run | None:
        with self._lock:
            return self._live.get(project_id)

    def _ms(self, started: float) -> float:
        return max(0.0, (self._clock() - started) * 1000)

    def _save(self, run: Run) -> None:
        self._store.save_project(run.status(), run.traces())


def _cut(file: FileStatus, ingesting: bool) -> dict[str, object]:
    """What `recover` changes on a file a restart cut off: during ingest, or while it was read
    again as a floor plan (then it is back to triage's call)."""
    if ingesting:
        return {"state": "set_aside", "reason": f"not ingested: {RESTARTED}"}
    triage = None if file.triage is None else read_as_plan(file.triage, None)
    return {"state": "set_aside", "reason": REREAD_CUT, "triage": triage}
