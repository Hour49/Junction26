"""Decision 0018: the steps inside an ingest stage, and the live step and phase of a project."""

import threading
from pathlib import Path

from conftest import MakeService
from test_ingest_evidence_scope import on
from test_ingest_service import Blocking
from test_ingest_triage import PLAN, SCAN, zipped
from test_raster_composite import LEFT, element
from triage_fakes import FakeClassifier, FakeDescriber, WordJudge, steps

from app.adapters.archive import ThreadRunner
from app.adapters.carbon import CarbonThings
from app.adapters.evidence.store import SqliteEvidenceIndex
from app.adapters.raster_scale import PriorScale
from app.core.drawing.model import Conflict, Scale
from app.core.evidence.chunks import passages
from app.core.ingest.model import (
    Description,
    Entry,
    FileStatus,
    Normalised,
    ProjectContext,
    ProjectStatus,
    RanStep,
    Relevance,
    StageTrace,
    StepTrace,
    TriageClass,
    Unavailable,
)
from app.core.ingest.progress import Run
from app.core.ingest.steps import frame_steps, second_count_steps, triage_step
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.steps import Span, starting
from scripts.make_sample_archive import build_archive, png_bytes, raster_plan


def test_a_step_has_empty_defaults_and_old_traces_read_with_no_steps() -> None:
    step = StepTrace(id="detector", label="Symbol detector")
    assert (step.did, step.at_ms, step.ms, step.cost_usd, step.state, step.found) == (
        "",
        0,
        0,
        0.0,
        "done",
        {},
    )
    old = StageTrace.model_validate({"stage": "extract", "did": "read", "ms": 1.0})
    assert old.steps == ()


def test_a_file_lists_its_live_step_only_while_one_runs() -> None:
    idle = FileStatus(id="f1", path="a.png", size=1)
    assert "step" not in idle.model_dump(mode="json")
    running = idle.model_copy(update={"step": "Room reader"})
    assert running.model_dump(mode="json")["step"] == "Room reader"


def test_a_project_has_no_phase_or_index_steps_by_default() -> None:
    status = ProjectStatus(id="p", name="n", state="queued", created_at="2026-11-15T00:00:00Z")
    dumped = status.model_dump(mode="json")
    assert dumped["phase"] is None and dumped["index_steps"] == []


def test_a_drawn_pdf_trace_lists_what_ran_inside_extract(make_service: MakeService) -> None:
    ingest = make_service()
    status = ingest.status(ingest.start("a.zip", build_archive()))
    pdf = next(file for file in status.files if file.path == "plans/flat-a.pdf")
    stages = {stage.stage: stage for stage in ingest.trace(status.id, pdf.id).stages}
    steps = stages["extract"].steps
    assert [step.id for step in steps] == ["vector", "tables"]
    vector = steps[0]
    assert vector.label == "Drawn-PDF reader (Swiss plan rules)"
    assert vector.found["room"] == 5 and "5 rooms" in vector.did
    assert steps[1].at_ms >= steps[0].at_ms  # the schedules are read after the drawn page
    assert stages["takeoff"].steps == ()


def test_identify_normalise_and_second_count_say_what_ran_inside(
    make_service: MakeService,
) -> None:
    ingest = make_service()
    status = ingest.status(ingest.start("a.zip", build_archive()))
    by_path = {file.path: file for file in status.files}
    stages = {s.stage: s for s in ingest.trace(status.id, by_path["plans/flat-b.pdf"].id).stages}
    (probe,) = stages["identify"].steps
    assert (probe.id, probe.label) == ("probe", "Content probe")
    assert probe.did.startswith("a drawn PDF (page 1 of 1")
    (pages,) = stages["normalise"].steps
    assert (pages.id, pages.did) == ("pages", "1 page, page 1 is 600 x 400 pt")
    (areas,) = stages["second_count"].steps
    assert (areas.id, areas.label) == ("room_areas", "Room areas: printed vs measured")
    assert areas.found == {"agree": 4, "conflict": 1}
    assert areas.did == "5 quantities compared: 4 agree, 1 conflict"
    model = ingest.trace(status.id, by_path["model/house.ifc"].id).stages
    assert [s.id for stage in model for s in stage.steps] == ["probe", "ifc"]


def test_a_turned_and_rectified_photo_lists_both_in_normalise() -> None:
    frame = Normalised(exif=6, rectified=True, width=800, height=600, rectifier="R3 quad")
    exif, rectifier = frame_steps(frame, 40.0)
    assert (exif.id, exif.did, exif.ms) == ("exif", "orientation 6 applied", 0)
    assert (rectifier.label, rectifier.ms) == ("Photo rectifier (R3 quad)", 40.0)
    assert frame_steps(Normalised(exif=1, width=8, height=6), 3.0) == []


def test_each_kind_of_comparison_is_a_step() -> None:
    def compared(quantity: str, methods: tuple[str, str], status: str) -> Conflict:
        return Conflict.model_validate(
            {
                "id": "c",
                "quantity": quantity,
                "subject": {"kind": "sheet", "ref": None},
                "status": status,
                "tolerance": 0,
                "values": [{"value": 1, "method": method} for method in methods],
            }
        )

    steps = second_count_steps(
        [
            compared("scale", ("scale_text", "scale_bar"), "agree"),
            compared("element_count", ("plan_drawing", "ifc_model"), "conflict"),
            compared("element_count", ("plan_drawing", "ifc_model"), "agree"),
            compared("element_count", ("detector", "schedule"), "agree"),
            compared("room_count", ("detector", "annotation"), "agree"),
            compared("storey_count", ("detector", "annotation"), "conflict"),
        ]
    )
    assert [(s.id, s.found) for s in steps] == [
        ("scale_check", {"agree": 1, "conflict": 0}),
        ("ifc_vs_sheet", {"agree": 1, "conflict": 1}),
        ("schedule_tags", {"agree": 1, "conflict": 0}),
        ("second_count:room_count", {"agree": 1, "conflict": 0}),
        ("second_count:storey_count", {"agree": 0, "conflict": 1}),
    ]
    assert steps[-2].label == "Room count: annotation vs detector"
    assert second_count_steps(None) == []


def test_triage_that_could_not_answer_is_a_failed_step() -> None:
    span = Span(at_ms=0, ms=5, cost_usd=0.001, faults=0)
    step = triage_step(None, "triage not available: timed out; read as today", span)
    assert (step.id, step.state, step.cost_usd) == ("classifier", "failed", 0.001)


def test_the_last_phase_lists_the_judge_the_describer_and_the_index(
    make_service: MakeService, tmp_path: Path
) -> None:
    triage = steps(
        FakeClassifier({SCAN: "other_drawing"}),
        FakeDescriber({SCAN: ("the south elevation of a house", ("Küche",))}),
        WordJudge(),
    )
    index = SqliteEvidenceIndex(tmp_path / "index", passages, None)
    service = make_service(triage=triage, evidence=index, evidence_steps=on())
    status = service.wait(service.start("p.zip", zipped({"plan.pdf": PLAN, "e.png": SCAN})))
    assert status.phase is None
    assert [(s.id, s.label) for s in status.index_steps] == [
        ("judge", "Relevance judge"),
        ("describe", "Files for the evidence index"),
        ("evidence", "Evidence index"),
    ]
    judge = status.index_steps[0]
    assert judge.found == {"related": 1} and judge.did == "1 file judged: 1 related"
    assert [s.at_ms for s in status.index_steps] == sorted(s.at_ms for s in status.index_steps)


def test_a_project_is_in_the_files_phase_while_its_files_are_read(
    make_service: MakeService,
) -> None:
    reader = Blocking()
    ingest = make_service(runner=ThreadRunner(), raster=lambda files: reader)
    try:
        project = ingest.start("scan.png", png_bytes(raster_plan()))
        assert reader.entered.wait(10)
        assert ingest.status(project).phase == "files"
        reader.release.set()
        done = ingest.wait(project, timeout=10)
    finally:
        reader.release.set()
        ingest.close()
    assert done.phase is None and done.index_steps == ()  # no judge, no index: nothing ran


class Announcing(Blocking):
    """A raster reader that says its step starts, then waits like `Blocking`."""

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        starting("rooms", "Room reader (Gemini)")
        return super().extract(source, sheet)


def test_a_running_file_shows_the_step_running_now_and_drops_it_when_done(
    make_service: MakeService,
) -> None:
    reader = Announcing()
    ingest = make_service(runner=ThreadRunner(), raster=lambda files: reader)
    try:
        project = ingest.start("scan.png", png_bytes(raster_plan()))
        assert reader.entered.wait(10)
        (file,) = ingest.status(project).files
        assert (file.stage, file.step, file.step_id) == ("extract", "Room reader (Gemini)", "rooms")
        assert file.model_dump(mode="json")["step_id"] == "rooms"
        reader.release.set()
        done = ingest.wait(project, timeout=10)
    finally:
        reader.release.set()
        ingest.close()
    dumped = done.files[0].model_dump(mode="json")
    assert "step" not in dumped and "step_id" not in dumped


def test_the_route_stage_is_timed(make_service: MakeService) -> None:
    ticks = iter(range(10_000))
    ingest = make_service(clock=lambda: next(ticks) / 1000)  # each reading 1 ms later
    status = ingest.status(ingest.start("a.zip", build_archive()))
    pdf = next(file for file in status.files if file.path == "plans/flat-a.pdf")
    stages = {stage.stage: stage for stage in ingest.trace(status.id, pdf.id).stages}
    assert stages["route"].ms > 0


class HeldJudge(WordJudge):
    """A judge that waits until the test lets it go, to look at a project mid-index."""

    def __init__(self) -> None:
        super().__init__()
        self.entered, self.release = threading.Event(), threading.Event()

    def judge(
        self, kind: TriageClass, description: Description | None, context: ProjectContext
    ) -> Relevance | Unavailable:
        self.entered.set()
        assert self.release.wait(10)
        return super().judge(kind, description, context)


def test_a_project_mid_index_lists_the_step_running_now(make_service: MakeService) -> None:
    judge = HeldJudge()
    triage = steps(
        FakeClassifier({SCAN: "other_drawing"}),
        FakeDescriber({SCAN: ("the south elevation of a house", ("Küche",))}),
        judge,
    )
    ingest = make_service(runner=ThreadRunner(), triage=triage, evidence_steps=on())
    try:
        project = ingest.start("p.zip", zipped({"plan.pdf": PLAN, "e.png": SCAN}))
        assert judge.entered.wait(10)
        mid = ingest.status(project)
        assert mid.phase == "index"
        assert [(s.id, s.label, s.state) for s in mid.index_steps] == [
            ("judge", "Relevance judge", "running")
        ]
        judge.release.set()
        done = ingest.wait(project, timeout=10)
    finally:
        judge.release.set()
        ingest.close()
    assert [(s.id, s.state) for s in done.index_steps] == [("judge", "done"), ("describe", "done")]


class Shipped:
    """The shipped raster reader: one door on `doors`, none elsewhere, its own detector step."""

    def __init__(self, doors: str) -> None:
        self._doors = doors

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:

        found = [element("door", LEFT)] if source.path == self._doors else []
        step = StepTrace(id="detector", label="Symbol detector", ms=1)
        return Extracted(
            method="detector", scale=Scale(status="no_scale"), elements=tuple(found), steps=(step,)
        )


class CarbonDoors:
    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:

        return Extracted(method="detector", scale=Scale(status="no_scale"), read=("door",))


def test_a_project_says_which_steps_ran_on_each_route(make_service: MakeService) -> None:

    other = png_bytes(raster_plan().resize((900, 640)))
    ingest = make_service(
        raster=lambda files: CarbonThings(Shipped("a.png"), CarbonDoors(), lambda _: False, 1),
    )
    status = ingest.wait(ingest.start("a.zip", zipped({"a.png": SCAN, "b.png": other,
                                                        "plan.pdf": PLAN})))  # fmt: skip
    assert {file.path: file.route for file in status.files} == {
        "a.png": "raster", "b.png": "raster", "plan.pdf": "vector"
    }  # fmt: skip
    raster = {step.id: step for step in status.ran["raster"]}
    # a.png: the detector found a door, so Carbon's things drawn were not needed; b.png: none
    assert raster["detector"] == RanStep(id="detector", label="Symbol detector", done=2)
    assert (raster["carbon"].done, raster["carbon"].skipped, raster["carbon"].failed) == (1, 1, 0)
    assert raster["probe"].done == 2
    vector = [step.id for step in status.ran["vector"]]
    assert {"probe", "vector", "tables"} <= set(vector) and "carbon" not in vector
    assert "ran" in status.model_dump(mode="json")
    assert ingest.status(status.id).ran == status.ran  # the stored project says the same


def test_the_door_size_scale_estimate_is_a_step_that_reaches_ran(make_service: MakeService) -> None:
    """The ingest screen's "scale from door sizes" ticks by the `prior_scale` id in `ran`."""
    other = png_bytes(raster_plan().resize((900, 640)))
    ingest = make_service(raster=lambda files: PriorScale(Shipped("a.png")))
    status = ingest.wait(ingest.start("a.zip", zipped({"a.png": SCAN, "b.png": other})))
    raster = {step.id: step for step in status.ran["raster"]}
    # a.png: a door, so a scale; b.png: no door, so none (it ran and says why)
    assert raster["prior_scale"] == RanStep(id="prior_scale", label="Scale from door sizes", done=2)
    by_path = {file.path: file for file in status.files}
    stages = {s.stage: s for s in ingest.trace(status.id, by_path["b.png"].id).stages}
    assert [(s.id, s.did) for s in stages["extract"].steps] == [
        ("detector", ""),
        ("prior_scale", "no scale: no door was detected"),
    ]


def test_ran_grows_as_each_file_finishes_and_a_file_read_again_is_counted_once() -> None:

    created = ProjectStatus(id="p", name="n", state="running", created_at="2026-11-15T00:00:00Z")
    assert "ran" not in created.model_dump(mode="json")  # left out while empty
    run = Run(created, fresh=False)
    detector = StepTrace(id="detector", label="Symbol detector")
    for path in ("a.png", "b.png"):
        run.add(Entry(path=path, size=1))
        run.set(path, route="raster")
        run.stage(path, "extract", "read", 1.0, steps=[detector])
    run.finish("a.png", "ready", "read")
    assert run.status().ran == {
        "raster": (RanStep(id="detector", label="Symbol detector", done=1),)
    }
    run.finish("b.png", "ready", "read")
    assert run.status().ran["raster"][0].done == 2
    again = Run.resumed(run.status(), run.traces())
    again.finish("a.png", "ready", "read again")
    assert again.status().ran["raster"][0].done == 2  # replaced, not added
