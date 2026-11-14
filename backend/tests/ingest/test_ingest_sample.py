"""The sample archive (scripts/make_sample_archive.py) through ingest: every file ends as the
script's docstring says, and a second upload of the same bytes is not read again."""

from collections.abc import Callable

from conftest import MakeService

from app.core.ingest.model import FileStatus
from scripts.make_sample_archive import build_archive, sample_files

# path -> (content kind, end state); the script's docstring says why each one ends so
EXPECTED = {
    "plans/flat-a.pdf": ("pdf_vector", "ready"),
    "plans/flat-a.png": ("png_plan", "ready"),
    "plans/flat-b.pdf": ("pdf_vector", "flagged"),
    "scans/ground-floor.png": ("png_plan", "flagged"),
    "scans/ground-floor-copy.png": ("png_plan", "flagged"),
    "photos/plan-photo.jpg": ("photo_plan", "flagged"),
    "photos/site.jpg": ("photo", "set_aside"),
    "model/house.ifc": ("ifc", "ready"),
    "cad/detail.dxf": ("dxf", "set_aside"),
    "docs/specification.pdf": ("pdf_text", "text_only"),
    "docs/notes.txt": ("text", "text_only"),
}


def by_path(files: tuple[FileStatus, ...]) -> dict[str, FileStatus]:
    return {file.path: file for file in files}


def test_the_archive_is_the_same_bytes_on_every_run() -> None:
    assert build_archive() == build_archive()
    assert set(sample_files()) == set(EXPECTED)


def test_every_file_of_the_sample_ends_as_the_script_says(make_service: MakeService) -> None:
    ingest = make_service()
    status = ingest.status(ingest.start("sample-project.zip", build_archive()))
    assert status.state == "done" and status.error is None
    files = by_path(status.files)
    assert {path: (file.kind, file.state) for path, file in files.items()} == EXPECTED
    assert all(file.reason for file in status.files)
    assert status.counts == {"ready": 3, "flagged": 4, "set_aside": 2, "text_only": 2}
    assert [file.id for file in status.files] == [f"f{n}" for n in range(1, 12)]


def test_each_file_says_why_it_ends_where_it_does(make_service: MakeService) -> None:
    ingest = make_service()
    files = by_path(ingest.status(ingest.start("sample.zip", build_archive())).files)
    reason: Callable[[str], str] = lambda path: files[path].reason  # noqa: E731
    assert reason("plans/flat-a.pdf").startswith("read on the drawn PDF route: 7 elements, 5 rooms")
    assert reason("plans/flat-b.pdf").startswith("1 conflict between the two methods (room areas)")
    assert "no reader for the image route yet" in reason("scans/ground-floor.png")
    assert "a phone photo, read without perspective correction" in reason("photos/plan-photo.jpg")
    assert reason("photos/site.jpg").startswith("a photo, not of a drawing")
    assert reason("cad/detail.dxf").startswith("no PDF, PNG or JPEG in its group")
    assert reason("model/house.ifc") == "read on the BIM model route: 12 model objects"
    # the PNG of a sheet is grouped with its PDF and read from it
    png = files["plans/flat-a.png"]
    assert (png.group, png.route, png.source) == ("plans/flat-a", "vector", "plans/flat-a.pdf")
    assert files["plans/flat-a.pdf"].takeoff["door"] == 2


def test_an_exact_copy_in_the_same_upload_is_not_read_twice(make_service: MakeService) -> None:
    ingest = make_service()
    status = ingest.status(ingest.start("sample.zip", build_archive()))
    files = by_path(status.files)
    first, copy = files["scans/ground-floor.png"], files["scans/ground-floor-copy.png"]
    assert (first.reused, copy.reused) == (False, True)
    assert copy.drawing_id == first.drawing_id is not None
    hashed = ingest.trace(status.id, copy.id).stages[1]
    assert hashed.did.endswith("same content as scans/ground-floor.png")
