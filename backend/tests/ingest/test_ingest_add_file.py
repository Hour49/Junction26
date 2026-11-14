"""A photo added to a finished project from the chat (board #203): read alone in the
background as at upload, the project stays done; png or jpeg only."""

import io

import pytest
from conftest import MakeService
from evidence_fakes import FakeKinds
from PIL import Image
from test_ingest_evidence_scope import ELEVATION, KINDS, on
from test_ingest_read_as_plan import Gate
from test_ingest_triage import PHOTO, PLAN, SCAN, file_of, zipped

from app.core.errors import InvalidInputError, NotFoundError, UnsupportedFileError
from app.core.ingest.model import ProjectStatus
from app.core.review.review import NotAllowedError


class Indexed:
    """An evidence index that keeps the statuses it was given."""

    def __init__(self) -> None:
        self.statuses: list[ProjectStatus] = []

    def update(self, status: ProjectStatus) -> None:
        self.statuses.append(status)


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


def test_an_added_picture_gets_its_evidence_and_is_indexed_alone(
    make_service: MakeService,
) -> None:
    """EVIDENCE_SCOPE=all_non_plan: the added picture is asked its kind and described for the
    index like an upload's, the files already there are not asked (nor charged) again, and the
    index gets the project with it."""
    kinds, index = FakeKinds(KINDS), Indexed()
    ingest = make_service(evidence_steps=on(kinds), evidence=index)
    files = {"plan.pdf": PLAN, "elevation.pdf": ELEVATION}
    project = ingest.wait(ingest.start("site.zip", zipped(files)))
    before = file_of(project, "elevation.pdf").evidence
    asked = len(kinds.asked)
    ingest.add_file(project.id, "detail.png", SCAN)
    status = ingest.wait(project.id)
    added = file_of(status, "detail.png").evidence
    assert added is not None and added.indexed and added.kind == "detail"
    assert kinds.asked[asked:] == [SCAN]
    assert file_of(status, "elevation.pdf").evidence == before
    assert index.statuses[-1] == status


def tiff_of(*pages: bytes) -> bytes:
    images = [Image.open(io.BytesIO(page)).convert("L") for page in pages]
    buffer = io.BytesIO()
    images[0].save(buffer, "TIFF", save_all=True, append_images=images[1:], compression="tiff_lzw")
    return buffer.getvalue()


def test_an_added_tiff_is_a_sheet_per_page_and_a_webp_one_sheet(make_service: MakeService) -> None:
    ingest = make_service()
    project = ingest.wait(ingest.start("site.zip", zipped({"plan.pdf": PLAN})))
    queued = ingest.add_file(project.id, "scan.tif", tiff_of(SCAN, SCAN))
    assert queued.path == "scan.png"
    status = ingest.wait(project.id)
    assert [file.path for file in status.files] == ["plan.pdf", "scan.png", "scan#p2.png"]
    assert all(file_of(status, path).kind == "png_plan" for path in ("scan.png", "scan#p2.png"))
    buffer = io.BytesIO()
    Image.open(io.BytesIO(SCAN)).save(buffer, "WEBP", lossless=True)
    assert ingest.add_file(project.id, "p.webp", buffer.getvalue()).path == "p.png"
    ingest.wait(project.id)


def test_a_broken_tiff_is_refused_with_its_reason(make_service: MakeService) -> None:
    ingest = make_service()
    project = ingest.wait(ingest.start("site.zip", zipped({"plan.pdf": PLAN})))
    with pytest.raises(UnsupportedFileError, match="cannot be read"):
        ingest.add_file(project.id, "bad.tif", b"II*\x00" + b"\x00" * 16)
