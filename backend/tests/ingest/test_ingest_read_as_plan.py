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
from app.core.errors import NotFoundError, NotTriagedError
from app.core.ingest.model import ReadAsPlan
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
    assert scan.reason == "not read as a floor plan: the server restarted during ingest"
