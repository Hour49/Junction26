"""Decision 0018: the steps inside an ingest stage, and the live step and phase of a project."""

from conftest import MakeService

from app.core.ingest.model import FileStatus, ProjectStatus, StageTrace, StepTrace
from scripts.make_sample_archive import build_archive


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
