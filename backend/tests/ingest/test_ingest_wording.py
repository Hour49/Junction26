"""The words a person reads in a reason or a trace: counts in the right number, plain scale and
kind words (the machine fields `kind` and `scale.status` are unchanged)."""

from conftest import MakeService

from app.core.ingest.model import ContentKind, FileStatus
from app.core.wording import KIND_WORDS, SCALE_WORDS, count, kind_words
from scripts.make_sample_archive import build_archive


def by_path(files: tuple[FileStatus, ...]) -> dict[str, FileStatus]:
    return {file.path: file for file in files}


def test_count_agrees_with_its_number() -> None:
    assert [count(n, "conflict") for n in (0, 1, 2)] == ["0 conflicts", "1 conflict", "2 conflicts"]
    assert [count(n, "quantity", "quantities") for n in (1, 5)] == ["1 quantity", "5 quantities"]


def test_every_kind_and_scale_status_has_plain_words() -> None:
    from typing import get_args

    assert set(KIND_WORDS) == set(get_args(ContentKind))
    assert all("_" not in words for words in (*KIND_WORDS.values(), *SCALE_WORDS.values()))
    assert kind_words("pdf_vector") == "drawn PDF"


def test_a_trace_reads_in_plain_words(make_service: MakeService) -> None:
    ingest = make_service()
    project = ingest.wait(ingest.start("sample.zip", build_archive()))
    flat_a = by_path(project.files)["plans/flat-a.pdf"]
    stages = {stage.stage: stage for stage in ingest.trace(project.id, flat_a.id).stages}
    assert stages["identify"].output == "drawn PDF"
    assert stages["group"].output == "2 files"
    assert stages["normalise"].output.startswith("1 page, page 1 is")
    assert stages["extract"].output == "7 elements, 5 rooms, 1 plan, scale read from the sheet"
    assert stages["second_count"].output == "5 quantities measured twice, 0 conflicts"
    assert flat_a.reason.endswith("7 elements, 5 rooms, scale read from the sheet")
    flat_b = by_path(project.files)["plans/flat-b.pdf"]
    assert flat_b.reason.startswith("1 conflict between the two methods")
    assert ingest.trace(project.id, flat_b.id).stages[-1].output.endswith("quantities")
    photo = by_path(project.files)["photos/plan-photo.jpg"]
    assert ingest.trace(project.id, photo.id).stages[2].output == "photo of a drawing"
