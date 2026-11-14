"""Reading as a floor plan a file triage set aside (decision 0010, board #152 c6876693460): the
one file is read in the background through the usual group, route and readers while the project
stays done; a person's call, never undone."""

from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import MakeService
from test_ingest_triage import PHOTO, PLAN, SCAN, file_of, zipped
from triage_fakes import FakeClassifier, steps

from app.adapters.archive import DiskProjectStore
from app.core.drawing.model import Scale
from app.core.errors import NotFoundError, NotTriagedError
from app.core.ingest.model import FileStatus, FileTrace, ReadAsPlan
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.review.review import NotAllowedError

CALL = ReadAsPlan(by="Ana", at="2026-11-14T12:00:00Z")


class Gate:
    """A runner that runs each job at once, unless held: then it keeps them until released."""

    def __init__(self) -> None:
        self.held = False
        self.jobs: list[Callable[[], None]] = []

    def submit(self, job: Callable[[], None]) -> None:
        if self.held:
            self.jobs.append(job)
        else:
            job()

    def release(self) -> None:
        self.held = False
        while self.jobs:
            self.jobs.pop(0)()

    def close(self) -> None:
        pass


def classifier() -> FakeClassifier:
    return FakeClassifier({SCAN: "other_drawing", PHOTO: "not_drawing"})


def test_a_file_set_aside_by_triage_is_read_as_a_plan_and_the_project_stays_done(
    make_service: MakeService,
) -> None:
    gate = Gate()
    ingest = make_service(runner=gate, triage=steps(classifier()))
    project = ingest.wait(ingest.start("site.zip", zipped({"plan.pdf": PLAN, "scan.png": SCAN})))
    scan = file_of(project, "scan.png")
    assert (scan.state, scan.drawing_id) == ("set_aside", None)
    gate.held = True
    queued = ingest.read_as_plan(project.id, scan.id, CALL)
    assert (queued.state, ingest.status(project.id).state) == ("queued", "done")
    assert queued.triage is not None and queued.triage.read_as_plan == CALL
    with pytest.raises(NotAllowedError, match="still being read"):  # one re-read at a time
        ingest.read_as_plan(project.id, scan.id, CALL)
    with pytest.raises(NotAllowedError):  # and no relevance call while it reads
        ingest.overrule(project.id, scan.id, None)
    gate.release()
    status = ingest.wait(project.id)
    read = file_of(status, "scan.png")
    assert status.state == "done"
    assert read.state in ("ready", "flagged") and read.drawing_id is not None
    assert (read.kind, read.route) == ("png_plan", "raster")
    assert read.triage is not None and read.triage.class_ == "other_drawing"  # the classifier's
    stages = [stage.stage for stage in ingest.trace(project.id, read.id).stages]
    assert stages[:4] == ["unpack", "hash", "identify", "identify"]
    assert {"group", "route", "write"} <= set(stages)
    said = ingest.trace(project.id, read.id).stages[3].did
    assert said == "read as a floor plan, as Ana asked"
    assert ingest.drawing_info(read.drawing_id).path == "scan.png"


def test_a_photo_is_read_as_a_photo_of_a_plan(make_service: MakeService) -> None:
    ingest = make_service(triage=steps(classifier()))
    project = ingest.wait(ingest.start("site.zip", zipped({"site.jpg": PHOTO})))
    photo = file_of(project, "site.jpg")
    assert photo.kind == "photo"
    ingest.read_as_plan(project.id, photo.id, CALL)
    read = file_of(ingest.wait(project.id), "site.jpg")
    assert read.kind == "photo_plan" and read.normalised is not None  # framed now


def test_only_a_file_triage_set_aside_can_be_read_and_only_once(make_service: MakeService) -> None:
    ingest = make_service(triage=steps(classifier()))
    project = ingest.wait(ingest.start("site.zip", zipped({"plan.pdf": PLAN, "scan.png": SCAN})))
    plan, scan = file_of(project, "plan.pdf"), file_of(project, "scan.png")
    with pytest.raises(NotTriagedError):
        ingest.read_as_plan(project.id, plan.id, CALL)
    with pytest.raises(NotFoundError):
        ingest.read_as_plan(project.id, "f99", CALL)
    ingest.read_as_plan(project.id, scan.id, CALL)
    ingest.wait(project.id)
    with pytest.raises(NotAllowedError, match="already"):
        ingest.read_as_plan(project.id, scan.id, CALL)


def test_a_reread_cut_off_by_a_restart_sets_the_file_aside_and_the_project_stays_done(
    make_service: MakeService, tmp_path: Path
) -> None:
    gate = Gate()
    store = DiskProjectStore(tmp_path / "store")
    ingest = make_service(runner=gate, triage=steps(classifier()), store=store)
    project = ingest.wait(ingest.start("site.zip", zipped({"scan.png": SCAN})))
    gate.held = True
    ingest.read_as_plan(project.id, file_of(project, "scan.png").id, CALL)
    restarted = make_service(store=store)  # the job never ran: the server went down
    assert restarted.recover() == [project.id]
    status = restarted.status(project.id)
    scan = file_of(status, "scan.png")
    assert (status.state, scan.state) == ("done", "set_aside")
    assert scan.reason == (
        "not read as a floor plan: the server restarted while it was read as a floor plan"
    )
    # back to triage's set-aside, so a person can ask again (R6-a-1)
    assert scan.triage is not None and scan.triage.read_as_plan is None
    gate.held = False
    queued = restarted.read_as_plan(project.id, scan.id, CALL)
    assert queued.triage is not None and queued.triage.read_as_plan == CALL
    read = file_of(restarted.wait(project.id), "scan.png")
    assert read.state in ("ready", "flagged") and read.drawing_id is not None


class FailingStore(DiskProjectStore):
    """A store whose next read of `path`'s file fails, as a reader that raises would; it keeps
    the file's saved status at that moment."""

    def __init__(self, root: Path, path: str) -> None:
        super().__init__(root)
        self.path, self.fail = path, False
        self.seen: FileStatus | None = None

    def read_file(self, project_id: str, path: str) -> bytes:
        if self.fail and path == self.path:
            self.fail = False
            status, _ = self.load_project(project_id)
            self.seen = next(file for file in status.files if file.path == path)
            raise RuntimeError("the reader broke")
        return super().read_file(project_id, path)


def test_a_failed_reread_keeps_its_reason_and_can_be_asked_again(
    make_service: MakeService, tmp_path: Path
) -> None:
    store = FailingStore(tmp_path / "store", "scan.png")
    ingest = make_service(triage=steps(classifier()), store=store)
    project = ingest.wait(ingest.start("site.zip", zipped({"scan.png": SCAN})))
    scan = file_of(project, "scan.png")
    store.fail = True
    ingest.read_as_plan(project.id, scan.id, CALL)
    status = ingest.wait(project.id)
    assert store.seen is not None  # while it was read, the reason said so (R6-a-5)
    assert (store.seen.state, store.seen.reason) == ("running", "being read as a floor plan")
    failed = file_of(status, "scan.png")
    assert (status.state, failed.state) == ("done", "set_aside")
    assert failed.reason == "not read as a floor plan: RuntimeError"
    assert failed.triage is not None and failed.triage.read_as_plan is None
    ingest.read_as_plan(project.id, scan.id, CALL)  # no 409: it was never read
    read = file_of(ingest.wait(project.id), "scan.png")
    assert read.state in ("ready", "flagged") and read.drawing_id is not None
    assert read.triage is not None and read.triage.read_as_plan == CALL


class Truncated:
    """A raster reader that fails the way a truncated JPEG does (Pillow's OSError inside the
    extract stage, caught by the group), `fails` times, then reads the file."""

    def __init__(self, fails: int) -> None:
        self.fails = fails

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        if self.fails:
            self.fails -= 1
            raise OSError("image file is truncated (0 bytes not processed)")
        return Extracted(method="detector", scale=Scale(status="no_scale"), read=("door",))


def test_a_reread_whose_reader_fails_goes_back_to_triage_and_can_be_asked_again(
    make_service: MakeService,
) -> None:  # R6-c-6: the reader's failure is caught by the group, nothing raises
    reader = Truncated(fails=1)
    ingest = make_service(triage=steps(classifier()), raster=lambda files: reader)
    project = ingest.wait(ingest.start("site.zip", zipped({"site.jpg": PHOTO})))
    photo = file_of(project, "site.jpg")
    ingest.read_as_plan(project.id, photo.id, CALL)
    status = ingest.wait(project.id)
    failed = file_of(status, "site.jpg")
    assert (status.state, failed.state, failed.drawing_id) == ("done", "set_aside", None)
    assert failed.reason == (
        "not read as a floor plan: failed at extract: "
        "OSError: image file is truncated (0 bytes not processed)"
    )
    assert failed.triage is not None and failed.triage.read_as_plan is None
    assert (failed.kind, failed.normalised) == (photo.kind, photo.normalised)  # triage's
    asked = [s for s in ingest.trace(project.id, photo.id).stages if s.did.endswith("Ana asked")]
    assert [s.failure for s in asked] == [
        "at extract: OSError: image file is truncated (0 bytes not processed)"
    ]  # R6-c-10: the screen adds "Failed:"
    ingest.read_as_plan(project.id, photo.id, CALL)  # no 409
    read = file_of(ingest.wait(project.id), "site.jpg")
    assert read.state in ("ready", "flagged") and read.drawing_id is not None
    assert read.kind == "photo_plan" and read.normalised is not None
    assert read.triage is not None and read.triage.read_as_plan == CALL


class Restart:
    """A raster reader during which the server restarts: a new service on the same store
    recovers the project, as at startup, and keeps the file and trace it then shows."""

    def __init__(self, make_service: MakeService, store: DiskProjectStore) -> None:
        self.make_service, self.store = make_service, store
        self.seen: FileTrace | None = None

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        restarted = self.make_service(store=self.store)
        (project_id,) = restarted.recover()
        self.seen = restarted.trace(project_id, "f1")
        return Extracted(method="detector", scale=Scale(status="no_scale"), read=("door",))


def test_a_reread_cut_mid_read_keeps_triages_kind_and_says_it_was_cut(
    make_service: MakeService, tmp_path: Path
) -> None:  # R6-c-9
    store = DiskProjectStore(tmp_path / "store")
    reader = Restart(make_service, store)
    ingest = make_service(triage=steps(classifier()), store=store, raster=lambda files: reader)
    project = ingest.wait(ingest.start("site.zip", zipped({"site.jpg": PHOTO})))
    photo = file_of(project, "site.jpg")
    ingest.read_as_plan(project.id, photo.id, CALL)
    assert reader.seen is not None
    cut = reader.seen.file
    assert (cut.state, cut.kind, cut.normalised) == ("set_aside", "photo", photo.normalised)
    asked = [s for s in reader.seen.stages if s.did.endswith("Ana asked")]
    assert [s.failure for s in asked] == ["the server restarted while it was read as a floor plan"]
