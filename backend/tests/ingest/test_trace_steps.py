"""Decision 0018: the steps inside an ingest stage, and the live step and phase of a project."""

from pathlib import Path

from conftest import MakeService
from test_ingest_evidence_scope import on
from test_ingest_service import Blocking
from test_ingest_triage import PLAN, SCAN, zipped
from triage_fakes import FakeClassifier, FakeDescriber, WordJudge, steps

from app.adapters.archive import ThreadRunner
from app.adapters.evidence.store import SqliteEvidenceIndex
from app.core.drawing.model import Conflict
from app.core.evidence.chunks import passages
from app.core.ingest.model import FileStatus, Normalised, ProjectStatus, StageTrace, StepTrace
from app.core.ingest.steps import frame_steps, second_count_steps, triage_step
from app.core.pipeline.steps import Span
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
        ]
    )
    assert [(s.id, s.found) for s in steps] == [
        ("scale_check", {"agree": 1, "conflict": 0}),
        ("ifc_vs_sheet", {"agree": 1, "conflict": 1}),
        ("schedule_tags", {"agree": 1, "conflict": 0}),
        ("second_count", {"agree": 1, "conflict": 0}),
    ]
    assert steps[-1].label == "Room count: annotation vs detector"
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
