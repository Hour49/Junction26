"""The trace says what the pipeline really did (detail's audit of the real demo run, project
117d844b5e60, 2026-11-15): no model or prompt ids in its words, a cached reply says so, the
judge step names the set-aside files it does not weigh, and a sheet read anyway is not headlined
"a floor plan". Wording only: nothing used for answers changes. Synthetic."""

import threading

from test_printed_scale import FILE, SHEET, Files, Fixed, png
from triage_fakes import FakeClassifier, FakeDescriber, steps

from app.adapters.carbon import THINGS, _carbon_step
from app.adapters.printed_scale import PrintedScale
from app.core import cost
from app.core.evidence.step import CAD
from app.core.ingest.model import Classified, FileStatus, Probed, Relevance, Sheet, Triage
from app.core.ingest.steps import judge_step
from app.core.ingest.triage import NOTE_PLAN, triaged
from app.core.pipeline.model import DrawingFile
from app.core.pipeline.printed import PrintedSheet
from app.core.pipeline.steps import Span, timed

IMAGE = b"site photo"
PROBED = Probed(kind="photo_plan", did="a photo")
SPAN = Span(at_ms=0, ms=1, cost_usd=0, faults=0)


def sheet(kind: str, kind_words: str, decision: str) -> Sheet:
    return Sheet.model_validate(
        {"kind": kind, "kind_words": kind_words, "decision": decision,
         "takeoff_possible": False, "confidence": 1.0, "title": None, "sheet_number": None,
         "printed_scale": None, "advanced": False, "advanced_why": None,
         "seen": "a brown rectangle on green and blue", "model": "gemini-4-carbon"}
    )  # fmt: skip


class DoubtClassifier:
    """The sheet kind called it not a drawing, a doubt under SHEET_KIND_SET_ASIDE=false: read as
    a floor plan, P(plan) 0 (site.jpg in the demo run)."""

    def classify(self, image: bytes, probed: Probed) -> Classified:
        return Classified.model_validate(
            {"class": "floor_plan", "p_plan": 0.0, "method": "Gemini sheet kind (cached reply)",
             "sheet": sheet("not_a_drawing", "not a drawing", "doubt")}
        )  # fmt: skip


def test_a_sheet_read_anyway_says_what_decided_it_not_a_floor_plan() -> None:
    found = triaged(steps(DoubtClassifier()), IMAGE, PROBED, "jpeg")  # type: ignore[arg-type]
    assert found.said == (
        "triage: read as a floor plan, but flagged: the sheet kind calls it not a drawing "
        "(P(plan) 0.00, Gemini sheet kind (cached reply))"
    )


def test_a_plain_floor_plan_keeps_its_short_line() -> None:
    found = triaged(steps(FakeClassifier({})), IMAGE, PROBED, "jpeg")
    assert found.said == "triage: a floor plan (P(plan) 0.97, fake classifier)"


def test_the_plan_note_speaks_for_triage_only_as_the_index_may_describe_it() -> None:
    # site.jpg: "it is read, so it is not described or judged", then the evidence index
    # described it (its own sheet-kind call): the note is about triage's step alone
    found = triaged(steps(DoubtClassifier()), IMAGE, PROBED, "jpeg")  # type: ignore[arg-type]
    assert found.triage is not None and found.triage.note == NOTE_PLAN
    assert NOTE_PLAN == "read as a floor plan, so triage does not describe or judge it"


def test_a_described_file_names_no_describer_model_in_its_line() -> None:
    classifier = FakeClassifier({IMAGE: "not_drawing"})
    describer = FakeDescriber({IMAGE: ("a garden", ())})
    found = triaged(steps(classifier, describer), IMAGE, PROBED, "jpeg")
    assert found.said.endswith("; described as a garden")
    assert "fake describer" not in found.said  # the id stays in `description.model`
    assert found.triage is not None and found.triage.description is not None
    assert found.triage.description.model == "fake describer"


def file(path: str, state: str, triage: Triage | None = None) -> FileStatus:
    return FileStatus.model_validate(
        {"id": path, "path": path, "size": 1, "state": state, "triage": triage}
    )


def test_the_judge_step_names_a_file_set_aside_by_anything_but_triage() -> None:
    # the demo run: "0 files judged" beside cad/detail.dxf, set aside by the CAD route
    files = [file("plans/a.pdf", "ready"), file("cad/detail.dxf", "set_aside")]
    assert judge_step(files, SPAN).did == (
        "0 files judged; cad/detail.dxf is set aside, but not by triage, so the judge does not "
        "weigh it"
    )


def test_the_judge_step_lists_a_few_such_files_and_counts_the_rest() -> None:
    files = [file(f"cad/{n}.dxf", "set_aside") for n in range(5)]
    assert judge_step(files, SPAN).did == (
        "0 files judged; 5 files are set aside, but not by triage, so the judge does not weigh "
        "them: cad/0.dxf, cad/1.dxf, cad/2.dxf and 2 more"
    )


def test_a_file_triage_set_aside_and_judged_is_not_named_again() -> None:
    relevance = Relevance(verdict="unrelated", why="Unrelated.", judge="rules")
    called = Triage.model_validate(
        {"class": "not_drawing", "p_plan": 0.03, "method": "m", "relevance": relevance}
    )
    files = [file("photos/cat.jpg", "set_aside", called)]
    assert judge_step(files, SPAN).did == "1 file judged: 1 unrelated"


def test_cache_hits_count_per_thread_and_are_carried_back() -> None:
    def on_another_thread() -> None:
        carried = cost.Carry()
        worker = threading.Thread(target=lambda: carried.run(lambda: cost.hit(2)))
        worker.start()
        worker.join()
        carried.hand_back()

    _, span = timed(on_another_thread)
    assert span.cached == 2
    _, none = timed(lambda: None)
    assert none.cached == 0


def test_a_carbon_step_whose_replies_were_cached_says_so() -> None:
    cached = Span(at_ms=0, ms=15.7, cost_usd=0, faults=0, cached=2)
    assert _carbon_step(THINGS, cached, {"door": 2}).did == "2 doors; 2 replies from the cache"
    assert _carbon_step(THINGS, SPAN, {"door": 2}).did == "2 doors"


class CachedReader:
    """A printed reader whose one reply came from the cache."""

    def read(self, source: DrawingFile, sheet: object) -> PrintedSheet:
        cost.hit()
        return PrintedSheet()


def test_the_printed_scale_step_says_its_reply_was_cached() -> None:
    reader = PrintedScale(Fixed(side_px=40), CachedReader(), Files(png(300.0)))  # type: ignore[arg-type]
    found = reader.extract(FILE, SHEET)
    (step,) = [s for s in found.steps if s.id == "printed_scale"]
    assert step.did.endswith("; 1 reply from the cache"), step.did


def test_a_cad_file_says_why_it_is_not_in_the_index() -> None:
    assert CAD == "a CAD drawing: the evidence index does not read DXF or SVG files"
