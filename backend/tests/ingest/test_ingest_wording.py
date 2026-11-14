"""The words a person reads in a reason or a trace: counts in the right number, plain scale and
kind words (the machine fields `kind` and `scale.status` are unchanged)."""

import re

from conftest import MakeService

from app.adapters.rectifier import CLASSICAL, LEARNED
from app.core.drawing.model import ConflictQuantity
from app.core.ingest.judge import reading_flags
from app.core.ingest.model import ContentKind, FileStatus, Normalised
from app.core.pipeline import rules
from app.core.pipeline.model import CountingRule
from app.core.wording import CONFLICT_WORDS, KIND_WORDS, SCALE_WORDS, count, kind_words
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


# QA R4 (R4-a-3, R4-c, 2026-11-14): internal names a person read on screen 2 and in answers.
INTERNAL = re.compile(r"_|\bR\d|UVDoc|dataset")


def test_every_conflict_quantity_has_plain_words(make_service: MakeService) -> None:
    from typing import get_args

    assert set(CONFLICT_WORDS) == set(get_args(ConflictQuantity))
    assert not [words for words in CONFLICT_WORDS.values() if INTERNAL.search(words)]
    ingest = make_service()
    project = ingest.wait(ingest.start("sample.zip", build_archive()))
    reason = by_path(project.files)["plans/flat-b.pdf"].reason
    assert reason.startswith("1 conflict between the two methods (room areas) ("), reason


def test_a_rectified_photo_names_how_in_plain_words() -> None:
    assert not INTERNAL.search(CLASSICAL) and not INTERNAL.search(LEARNED)
    frame = Normalised(rectified=True, width=10, height=10, rectifier=CLASSICAL)
    (flag,) = reading_flags("photo_plan", frame)
    assert flag == "a phone photo, rectified by paper edges: check the paper's corners"


def test_no_counting_rule_text_names_the_dataset() -> None:
    texts = {rule.id: rule.text for rule in vars(rules).values() if isinstance(rule, CountingRule)}
    assert not {key: text for key, text in texts.items() if INTERNAL.search(text)}
    # the rule is still said, where it differs from the question's own wording
    assert "though the question says shafts are left out" in texts["indoor-rooms-total"]
    assert "sauna stoves" in texts["sauna-room-else-stove"]


RAW_ROUTE = re.compile(
    r"\b(vector|raster|bim|cad) (route|reader)\b|^(vector|raster|bim|cad), read from"
)


def test_reasons_and_trace_lines_name_a_route_in_words(make_service: MakeService) -> None:
    """QA R4-a-10: the drawing cards say "drawn PDF route", "image route", "BIM model route"; the
    reasons and trace lines said "read on the vector route", "vector, read from …". The route
    words (ROUTE_WORDS) are the cards'; the field `route` and the stage output keep the id."""
    from typing import get_args

    from app.core.pipeline.model import Route
    from app.core.wording import ROUTE_WORDS

    assert set(ROUTE_WORDS) == set(get_args(Route))
    ingest = make_service()
    project = ingest.wait(ingest.start("sample.zip", build_archive()))
    lines = [file.reason for file in project.files]
    for file in project.files:
        lines += [stage.did for stage in ingest.trace(project.id, file.id).stages]
    raw = [line for line in lines if RAW_ROUTE.search(line)]
    assert raw == []
    flat_a = by_path(project.files)["plans/flat-a.pdf"]
    assert flat_a.reason.startswith("read on the drawn PDF route: ")
    assert flat_a.route == "vector"
    routed = next(s for s in ingest.trace(project.id, flat_a.id).stages if s.stage == "route")
    assert (routed.did, routed.output) == ("drawn PDF route, read from plans/flat-a.pdf", "vector")
    ground = by_path(project.files)["scans/ground-floor.png"]
    assert "no reader for the image route yet" in ground.reason
