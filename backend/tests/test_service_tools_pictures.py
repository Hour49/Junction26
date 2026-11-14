"""A plan edit on a drawing that was not drawn from a model, in a project whose services are
pictures: `ServiceFollower.run` adds the lanes the services picture gives (picture_follow). The
project is scripted; the picture's marks are those of test_services_picture_follow."""

from types import SimpleNamespace
from typing import Any

from test_services_picture_follow import WALL, heating

from app.adapters.ifc_services import ServiceFiles
from app.adapters.service_tools import ServiceFollower
from app.core.drawing.model import Drawing, Page, Room, Scale
from app.core.ifc_facts import FactSheet
from app.core.ingest.model import FileStatus, ProjectStatus
from app.core.plan_edit.model import Proposal

PLAN = "d1"


def project() -> Any:
    """One drawn PDF plan of a 10 m x 10 m page, no model files."""
    listed = (
        FileStatus(id="f1", path="plan.pdf", size=1, sha256="sheet", kind="pdf_vector",
                   state="ready", group="plan", route="vector", drawing_id=PLAN),
    )  # fmt: skip
    status = ProjectStatus(
        id="p", name="demo", state="done", created_at="2026-11-15T00:00:00Z", files=listed
    )
    drawing = Drawing(
        file="plan.pdf",
        pages=(Page(page=1, width=1000, height=1000, unit="pt"),),
        scale=Scale(status="scaled", m_per_unit=0.01),
        rooms=(Room(id="r1", type="other", label="Office 1", page=1, box=(0.2, 0.2, 0.4, 0.4)),),
    )
    ingest = SimpleNamespace(status=lambda _: status, drawing=lambda _: drawing)
    return SimpleNamespace(project_id="p", ingest=ingest)


def run(pictures: dict[str, FactSheet]) -> Any:
    follower = ServiceFollower(project(), ServiceFiles(), pictures=pictures.get)
    proposal = Proposal(proposal_id="p1", drawing_id=PLAN, page=1, removed=(WALL,))
    return follower.run(proposal)


def test_a_wall_removed_on_a_picture_plan_gets_the_picture_lane_of_its_services_marks() -> None:
    services, shown = run({PLAN: heating()})
    lanes = {d.discipline: d for d in services.disciplines}
    assert lanes["heating"].status == "checked"
    assert {a.code for a in lanes["heating"].actions} == {"reseat"}
    assert len(lanes["heating"].marks) >= 2
    assert {lanes[d].status for d in ("plumbing", "ventilation", "electrical")} == {"no_model"}
    assert any("picture" in u for u in services.unknowns)
    assert "Heating: " in shown["text"]


def test_without_a_services_picture_the_follow_up_is_as_before() -> None:
    services, _ = run({})
    assert {d.status for d in services.disciplines} == {"no_model"}
    assert services.unknowns == ()
