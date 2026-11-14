"""EVIDENCE_SCOPE=all_non_plan at ingest (decision 0012 sources v2, report 7.7): every picture
triage did not set aside is asked its kind and, when it is not a floor plan sheet, described for
the evidence index. Describing for the index never changes how a file is routed: with the scope on
or off every file has the same state, route and takeoff."""

from pathlib import Path

import pytest
from conftest import MakeService
from evidence_fakes import FakeKinds, picture_kind
from pdf_sheets import SheetPdf, rect
from test_ingest_triage import PHOTO, PLAN, SCAN, file_of, zipped
from triage_fakes import FakeClassifier, FakeDescriber, steps

from app.adapters.evidence.store import SqliteEvidenceIndex
from app.core.evidence.chunks import passages
from app.core.evidence.model import sources
from app.core.evidence.pictures import FLOOR_PLAN, NO_DESCRIBER, EvidenceSteps
from app.core.ingest.model import FileStatus, ProjectStatus


def elevation_pdf() -> bytes:
    """A drawn (vector) sheet the kind call will call an elevation."""
    sheet = SheetPdf(600, 400)
    sheet.path(rect(100, 100, 500, 300))
    sheet.path(rect(150, 150, 250, 250))
    sheet.text("SOUTH ELEVATION 1:50", 100, 330)
    return sheet.pdf()


ELEVATION = elevation_pdf()
FILES = {"A101 plan.pdf": PLAN, "A200 elevation.pdf": ELEVATION, "detail.png": SCAN}
KINDS = {
    PLAN: picture_kind("architectural_floor_plan", True),
    ELEVATION: picture_kind("elevation", False),
    SCAN: picture_kind("detail", False),
}
SUBJECTS = {
    ELEVATION: ("the south elevation of a house", ("SOUTH ELEVATION",)),
    SCAN: ("a window detail", ()),
}


def on(kinds: FakeKinds | None = None, describer: FakeDescriber | None = None) -> EvidenceSteps:
    return EvidenceSteps(
        kinds=kinds or FakeKinds(KINDS), describer=describer or FakeDescriber(SUBJECTS, usd=0.03)
    )


def ingest(
    make_service: MakeService, root: Path, files: dict[str, bytes], **ports: object
) -> ProjectStatus:
    service = make_service(root=root, **ports)
    return service.wait(service.start("house.zip", zipped(files)))


def routed(file: FileStatus) -> tuple[object, ...]:
    return (
        file.path,
        file.kind,
        file.state,
        file.reason,
        file.route,
        file.group,
        file.source,
        file.drawing_id,
        file.takeoff,
    )


def test_a_drawn_elevation_is_a_source_and_is_still_read(
    make_service: MakeService, tmp_path: Path
) -> None:
    status = ingest(make_service, tmp_path / "on", FILES, evidence_steps=on())
    elevation = file_of(status, "A200 elevation.pdf")
    assert elevation.kind == "pdf_vector" and elevation.state != "set_aside"
    assert elevation.drawing_id is not None  # read as today: that is SHEET_KIND's question
    evidence = elevation.evidence
    assert evidence is not None and evidence.indexed and evidence.how == "described"
    assert evidence.kind == "elevation"
    found = {source.path: source for source in sources(status)}
    assert set(found) == {"A200 elevation.pdf", "detail.png"}
    assert found["A200 elevation.pdf"].kind == "elevation"
    assert found["A200 elevation.pdf"].how == "described"


def test_a_drawn_floor_plan_is_asked_and_is_not_a_source(
    make_service: MakeService, tmp_path: Path
) -> None:
    status = ingest(make_service, tmp_path / "on", FILES, evidence_steps=on())
    plan = file_of(status, "A101 plan.pdf")
    assert plan.evidence is not None
    assert (plan.evidence.indexed, plan.evidence.why) == (False, FLOOR_PLAN)
    assert plan.evidence.cost_usd == 0.012


def test_every_file_is_routed_the_same_with_the_scope_on_or_off(
    make_service: MakeService, tmp_path: Path
) -> None:
    files = {**FILES, "cat.jpg": PHOTO}
    off = ingest(make_service, tmp_path / "off", files)
    with_scope = ingest(make_service, tmp_path / "on", files, evidence_steps=on())
    assert [routed(file) for file in with_scope.files] == [routed(file) for file in off.files]
    assert all(file.evidence is None for file in off.files)  # off: no evidence key at all
    assert "evidence" not in off.files[0].model_dump(mode="json")
    png = file_of(with_scope, "detail.png")
    assert png.evidence is not None and png.evidence.indexed  # a png no plan: a source
    assert png.cost_usd == file_of(off, "detail.png").cost_usd + png.evidence.cost_usd
    # 4 asked (the cat's call fails, unpaid), 2 described
    assert with_scope.cost_usd == pytest.approx(off.cost_usd + 3 * 0.012 + 2 * 0.03)


def test_a_failed_kind_call_or_no_describer_leaves_the_file_out_with_why(
    make_service: MakeService, tmp_path: Path
) -> None:
    kinds = FakeKinds({PLAN: KINDS[PLAN], SCAN: KINDS[SCAN]})  # the elevation's call fails
    steps_on = EvidenceSteps(kinds=kinds, describer=None)
    status = ingest(make_service, tmp_path / "on", FILES, evidence_steps=steps_on)
    elevation = file_of(status, "A200 elevation.pdf").evidence
    assert elevation is not None and not elevation.indexed
    assert elevation.why.startswith("the kind call failed: ")
    png = file_of(status, "detail.png").evidence
    assert png is not None and (png.indexed, png.why) == (False, NO_DESCRIBER)
    assert sources(status) == ()
    assert file_of(status, "A200 elevation.pdf").drawing_id is not None  # still read


def test_a_step_that_raises_is_the_files_why_never_the_projects(
    make_service: MakeService, tmp_path: Path
) -> None:
    class Raising:
        def kind(self, image: bytes) -> object:
            raise RuntimeError("socket closed")

    steps_on = EvidenceSteps(kinds=Raising(), describer=None)  # pyright: ignore[reportArgumentType]
    status = ingest(make_service, tmp_path / "on", FILES, evidence_steps=steps_on)
    assert status.state == "done"
    elevation = file_of(status, "A200 elevation.pdf").evidence
    assert elevation is not None and not elevation.indexed
    assert elevation.why == "the evidence step failed: RuntimeError: socket closed"


def test_a_picture_triage_set_aside_keeps_its_triage_path_and_is_not_asked(
    make_service: MakeService, tmp_path: Path
) -> None:
    kinds = FakeKinds(KINDS)
    triage = steps(
        FakeClassifier({SCAN: "other_drawing"}), FakeDescriber({SCAN: ("a window detail", ())})
    )
    status = ingest(
        make_service, tmp_path / "on", FILES, triage=triage, evidence_steps=on(kinds=kinds)
    )
    png = file_of(status, "detail.png")
    assert png.evidence is None and png.triage is not None and png.triage.description
    assert SCAN not in kinds.asked
    assert [source.path for source in sources(status)] == ["A200 elevation.pdf", "detail.png"]


def test_the_index_holds_the_new_sources_and_rebuilt_equals_the_first(
    make_service: MakeService, tmp_path: Path
) -> None:
    status = ingest(make_service, tmp_path / "on", FILES, evidence_steps=on())
    first, again = (SqliteEvidenceIndex(tmp_path / name, passages, None) for name in ("a", "b"))
    first.update(status)
    again.update(status)
    first.update(status)  # in step: nothing changes
    assert first.indexed(status.id) == again.indexed(status.id)
    assert [source.path for source in first.indexed(status.id)] == [
        "A200 elevation.pdf",
        "detail.png",
    ]
