"""A photo added to a finished project from the chat (board #203): read alone in the
background as at upload, the project stays done; png or jpeg only."""

import pytest
from conftest import MakeService
from test_ingest_read_as_plan import Gate
from test_ingest_triage import PHOTO, PLAN, SCAN, file_of, zipped

from app.core.errors import InvalidInputError, NotFoundError, UnsupportedFileError
from app.core.review.review import NotAllowedError


def test_an_added_image_is_read_as_a_drawing_and_the_project_stays_done(
    make_service: MakeService,
) -> None:
    gate = Gate()
    ingest = make_service(runner=gate)
    project = ingest.wait(ingest.start("site.zip", zipped({"plan.pdf": PLAN})))
    gate.held = True
    queued = ingest.add_file(project.id, "scan.png", SCAN)
    assert (queued.id, queued.path, queued.state) == ("f2", "scan.png", "queued")
    assert ingest.status(project.id).state == "done"
    with pytest.raises(NotAllowedError, match="still being read"):  # one at a time
        ingest.add_file(project.id, "again.png", SCAN)
    gate.release()
    status = ingest.wait(project.id)
    read = file_of(status, "scan.png")
    assert status.state == "done" and len(status.files) == 2
    assert read.state in ("ready", "flagged") and read.drawing_id is not None
    assert (read.kind, read.route) == ("png_plan", "raster")
    assert file_of(status, "plan.pdf").state in ("ready", "flagged")  # untouched
    stages = [stage.stage for stage in ingest.trace(project.id, read.id).stages]
    assert stages[:3] == ["unpack", "hash", "identify"] and "write" in stages
    assert ingest.drawing_info(read.drawing_id).path == "scan.png"


def test_a_taken_name_gets_a_suffix_and_a_photo_not_of_a_plan_is_set_aside(
    make_service: MakeService,
) -> None:
    ingest = make_service()
    project = ingest.wait(ingest.start("site.zip", zipped({"site.jpg": SCAN})))
    added = ingest.add_file(project.id, "folder/site.jpg", PHOTO)
    assert added.path == "site-2.jpg"
    assert ingest.add_file(project.id, "site.jpg", PHOTO).path == "site-3.jpg"
    photo = file_of(ingest.wait(project.id), "site-2.jpg")
    assert photo.state == "set_aside" and photo.drawing_id is None


def test_only_an_image_for_a_done_project_is_taken(make_service: MakeService) -> None:
    gate = Gate()
    ingest = make_service(runner=gate)
    project = ingest.wait(ingest.start("site.zip", zipped({"plan.pdf": PLAN})))
    with pytest.raises(UnsupportedFileError):
        ingest.add_file(project.id, "plan.pdf", PLAN)
    with pytest.raises(UnsupportedFileError):
        ingest.add_file(project.id, "empty.png", b"")
    with pytest.raises(InvalidInputError, match="not a file name"):
        ingest.add_file(project.id, "..", SCAN)
    with pytest.raises(NotFoundError):
        ingest.add_file("nope", "scan.png", SCAN)
    gate.held = True
    running = ingest.start("other.zip", zipped({"plan.pdf": PLAN}))
    with pytest.raises(NotAllowedError):
        ingest.add_file(running, "scan.png", SCAN)
    gate.release()
