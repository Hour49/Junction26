"""IngestService: the hash cache and fresh runs, status and trace while it runs, a failing
stage, a restart, and what the API reads (drawing info, uploads, project list)."""

import io
import json
import threading
import zipfile
from pathlib import Path

import pytest
from conftest import MakeService
from test_vector_pdf import swiss_sheet

from app.adapters.archive import ThreadRunner
from app.core.drawing.model import Scale
from app.core.errors import InvalidInputError, NotFoundError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from scripts.make_sample_archive import build_archive, png_bytes, raster_plan


def zipped(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return buffer.getvalue()


PLAN = swiss_sheet().pdf()  # one copy of the bytes: pdfium writes a new file ID each time


def drawn_pdf() -> bytes:
    return PLAN


def test_a_second_upload_reuses_every_file_and_its_trace_keeps_the_first_story(
    make_service: MakeService,
) -> None:
    ingest = make_service()
    first = ingest.status(ingest.start("a.zip", build_archive()))
    again = ingest.status(ingest.start("b.zip", build_archive()))
    drawn = [file for file in again.files if file.drawing_id is not None]
    assert drawn and all(file.reused for file in drawn)
    assert [file.drawing_id for file in first.files] == [file.drawing_id for file in again.files]
    pdf = next(file for file in again.files if file.path == "plans/flat-a.pdf")
    stages = [stage.stage for stage in ingest.trace(again.id, pdf.id).stages]
    assert stages[:5] == ["unpack", "hash", "identify", "group", "route"]
    assert stages[5] == "cache"
    assert stages[6:] == ["normalise", "extract", "second_count", "takeoff", "write"]  # the first's
    assert pdf.stage == "write" and pdf.state == "ready"  # where its first ingest ended


def test_a_reused_file_ends_at_the_stage_its_first_ingest_ended_at(
    make_service: MakeService,
) -> None:
    """The ingest screen counts files by their last stage: reuse does not move a file (QA R2,
    #14 c6871874309). A set-aside DXF stays where it was set aside, not under cache."""
    ingest = make_service()
    first = ingest.status(ingest.start("a.zip", build_archive()))
    again = ingest.status(ingest.start("b.zip", build_archive()))
    assert [(file.path, file.stage, file.state) for file in again.files] == [
        (file.path, file.stage, file.state) for file in first.files
    ]
    dxf = next(file for file in again.files if file.path == "cad/detail.dxf")
    assert (dxf.reused, dxf.stage, dxf.state) == (True, "route", "set_aside")
    written = ingest.trace(again.id, next(f.id for f in again.files if f.path == "model/house.ifc"))
    assert written.stages[-1].stage == "write" and written.stages[-1].ms == 0.0


def test_a_fresh_upload_reads_everything_again(make_service: MakeService) -> None:
    ingest = make_service()
    ingest.start("a.zip", build_archive())
    fresh = ingest.status(ingest.start("b.zip", build_archive(), fresh=True))
    assert not any(
        file.reused for file in fresh.files if file.path != "scans/ground-floor-copy.png"
    )
    pdf = next(file for file in fresh.files if file.path == "plans/flat-a.pdf")
    assert "cache" not in [stage.stage for stage in ingest.trace(fresh.id, pdf.id).stages]


def test_the_same_drawing_under_another_name_gets_the_same_id(make_service: MakeService) -> None:
    ingest = make_service()
    one = ingest.status(ingest.start("plan.pdf", drawn_pdf())).files[0]
    two = ingest.status(ingest.start("renamed.pdf", drawn_pdf())).files[0]
    assert (one.reused, two.reused) == (False, True)
    assert two.drawing_id is not None and one.drawing_id == two.drawing_id
    assert ingest.drawing(two.drawing_id).file == "plan.pdf"  # as first ingested


def test_a_change_of_reader_is_not_served_from_the_cache(
    make_service: MakeService, tmp_path: Path
) -> None:
    ingest = make_service()
    ingest.start("plan.pdf", drawn_pdf())
    other = make_service()
    other._names = {"raster": "another"}  # what build_ingest takes from the settings
    assert not other.status(other.start("plan.pdf", drawn_pdf())).files[0].reused


class Blocking:
    """A raster reader that waits until the test lets it go, to look at a running project."""

    def __init__(self) -> None:
        self.entered, self.release = threading.Event(), threading.Event()

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self.entered.set()
        assert self.release.wait(10)
        return Extracted(method="detector", scale=Scale(status="no_scale"), read=("door",))


def test_status_and_trace_are_readable_while_it_runs(make_service: MakeService) -> None:
    reader = Blocking()
    ingest = make_service(runner=ThreadRunner(), raster=lambda files: reader)
    try:
        project = ingest.start("scan.png", png_bytes(raster_plan()))
        assert reader.entered.wait(10)
        status = ingest.status(project)
        assert status.state == "running"
        (file,) = status.files
        assert (file.state, file.stage) == ("running", "extract")
        # the pipeline's stages join the trace when the drawing's group is done
        assert [stage.stage for stage in ingest.trace(project, "f1").stages][-1] == "route"
        stored = json.loads((Path("projects") / project / "project.json").read_text())
        assert stored["status"]["state"] == "running"
        reader.release.set()
        done = ingest.wait(project, timeout=10)
    finally:
        reader.release.set()
        ingest.close()
    assert done.state == "done" and done.files[0].state == "ready"
    assert done.files[0].stage == "write"
    stages = [stage.stage for stage in ingest.trace(project, "f1").stages]
    assert stages[-5:] == ["normalise", "extract", "second_count", "takeoff", "write"]
    assert done.cost_usd == 0.0 and done.files[0].cost_usd == 0.0


class Failing:
    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        raise ValueError("the reader broke")


def test_a_stage_that_fails_sets_its_file_aside_and_the_rest_go_on(
    make_service: MakeService,
) -> None:
    ingest = make_service(raster=lambda files: Failing())
    upload = zipped({"scan.png": png_bytes(raster_plan()), "plan.pdf": drawn_pdf()})
    status = ingest.status(ingest.start("mixed.zip", upload))
    assert status.state == "done"
    scan, plan = status.files
    assert scan.state == "set_aside"
    assert scan.reason == "failed at extract: ValueError: the reader broke"
    assert ingest.trace(status.id, scan.id).stages[-1].failure == "ValueError: the reader broke"
    assert plan.state == "ready"
    # a failure is not cached: the next upload tries again
    again = make_service()
    assert not again.status(again.start("scan.png", png_bytes(raster_plan()))).files[0].reused


def test_unsafe_entries_are_listed_set_aside_and_the_rest_is_ingested(
    make_service: MakeService,
) -> None:
    ingest = make_service()
    upload = zipped({"../escape.pdf": drawn_pdf(), "plans/plan.pdf": drawn_pdf(),
                     "bomb.txt": b"0" * (4 * 2**20)})  # fmt: skip
    status = ingest.status(ingest.start("bad.zip", upload))
    files = {file.path: file for file in status.files}
    assert files["../escape.pdf"].state == "set_aside"
    assert files["../escape.pdf"].reason.startswith("unsafe path")
    assert files["../escape.pdf"].sha256 is None
    assert "zip bomb" in files["bomb.txt"].reason
    assert files["plans/plan.pdf"].state == "ready"
    assert not (Path("escape.pdf")).exists() and not (Path("projects") / "escape.pdf").exists()


def test_an_unreadable_zip_fails_the_project_with_the_reason(make_service: MakeService) -> None:
    ingest = make_service()
    broken = zipped({"a.txt": b"x"})[:-30]  # the central directory cut off
    status = ingest.status(ingest.start("broken.zip", broken))
    assert status.state == "done"  # not a readable archive: one file, set aside
    assert [file.kind for file in status.files] == ["unknown"]
    with pytest.raises(InvalidInputError):
        ingest.start("empty.zip", b"")


def test_a_restart_marks_a_running_project_failed(make_service: MakeService) -> None:
    reader = Blocking()
    root = Path("projects")
    ingest = make_service(root, runner=ThreadRunner(), raster=lambda files: reader)
    project = ingest.start("scan.png", png_bytes(raster_plan()))
    assert reader.entered.wait(10)  # the process "dies" here: the store says running
    restarted = make_service(root)
    assert restarted.recover() == [project]
    status = restarted.status(project)
    trace = restarted.trace(project, "f1")
    assert make_service(root).recover() == []
    reader.release.set()
    ingest.close()
    assert (status.state, status.error) == ("failed", "the server restarted during ingest")
    assert status.files[0].state == "set_aside"
    assert status.files[0].reason == "not ingested: the server restarted during ingest"
    assert trace.file.state == "set_aside"


def test_projects_are_listed_newest_first(make_service: MakeService) -> None:
    ingest = make_service()
    first = ingest.start("one.pdf", drawn_pdf())
    second = ingest.start("two.txt", b"notes")
    assert [status.id for status in ingest.projects()] == [second, first]


def test_drawing_info_says_route_and_source_and_a_model_has_no_sheet(
    make_service: MakeService,
) -> None:
    ingest = make_service()
    status = ingest.status(ingest.start("sample.zip", build_archive()))
    files = {file.path: file for file in status.files}
    png = files["plans/flat-a.png"]
    assert png.drawing_id is not None
    info = ingest.drawing_info(png.drawing_id)
    assert (info.kind, info.route, info.source) == ("png", "vector", "plans/flat-a.pdf")
    sheet = ingest.sheet(png.drawing_id)
    assert (sheet.kind, sheet.route, sheet.source) == ("png", "vector", "plans/flat-a.pdf")
    model = files["model/house.ifc"].drawing_id
    assert model is not None
    assert ingest.drawing_info(model).kind == "ifc"
    assert ingest.drawing(model).pages == ()
    with pytest.raises(NotFoundError, match="no page"):
        ingest.sheet(model)
    with pytest.raises(NotFoundError):
        ingest.drawing_info("0" * 16)
    with pytest.raises(NotFoundError):
        ingest.trace(status.id, "f99")
    with pytest.raises(NotFoundError):
        ingest.status("nope")


def test_drawing_info_carries_how_a_photo_was_read_and_a_reuse_keeps_it(
    make_service: MakeService,
) -> None:
    """R3-qa4-1: the photo flag judge() wrote into the file's reason was lost on the way to the
    answer; the drawing's info now carries it (a clean sheet has none), also when reused."""
    ingest = make_service()
    for name in ("a.zip", "b.zip"):
        status = ingest.status(ingest.start(name, build_archive()))
        files = {file.path: file for file in status.files}
        photo, png = files["photos/plan-photo.jpg"], files["plans/flat-a.png"]
        assert photo.state == "flagged" and photo.drawing_id is not None
        flags = ingest.drawing_info(photo.drawing_id).flags
        assert flags == ("a phone photo, read without perspective correction",)
        assert flags[0] in photo.reason
        assert png.drawing_id is not None and ingest.drawing_info(png.drawing_id).flags == ()


def test_a_dxf_with_no_reader_does_not_take_its_plan_away_from_the_vector_reader(
    make_service: MakeService,
) -> None:
    ingest = make_service()  # EXTRACTOR_CAD=hello, as by default
    dxf = b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n"
    status = ingest.status(ingest.start("swiss.zip", zipped({"a/p.pdf": PLAN, "a/p.dxf": dxf})))
    files = {file.path: file for file in status.files}
    assert (files["a/p.pdf"].state, files["a/p.pdf"].route) == ("ready", "vector")
    assert (files["a/p.dxf"].state, files["a/p.dxf"].route) == ("ready", "vector")
    assert files["a/p.dxf"].reason == "another rendering of a/p; its drawing is read from a/p.pdf"
