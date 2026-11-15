"""A plan edit on a drawing that was not drawn from a model, in a project whose services are
pictures: `ServiceFollower.run` adds the lanes the services picture gives (picture_follow). The
project is scripted; the picture's marks are those of test_services_picture_follow."""

from types import SimpleNamespace
from typing import Any

from test_services_picture_follow import WALL, heating

from app.adapters.discipline_pictures.lane import PictureFactSheet, PictureScale
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


def test_a_plan_drawn_from_a_model_is_not_given_picture_lanes() -> None:
    status = project().ingest.status("p")
    listed = tuple(f.model_copy(update={"route": "bim"}) for f in status.files)
    modelled = SimpleNamespace(
        project_id="p",
        ingest=SimpleNamespace(status=lambda _: status.model_copy(update={"files": listed})),
    )
    follower = ServiceFollower(modelled, ServiceFiles(), pictures={PLAN: heating()}.get)  # pyright: ignore[reportArgumentType]
    before = follower._follow(Proposal(proposal_id="p1", drawing_id=PLAN, page=1, removed=(WALL,)))  # pyright: ignore[reportPrivateUsage]
    proposal = Proposal(proposal_id="p1", drawing_id=PLAN, page=1, removed=(WALL,))
    after = follower._with_pictures(proposal, before)  # pyright: ignore[reportPrivateUsage]
    assert after == before


def test_a_picture_that_cannot_be_read_leaves_the_model_lanes_and_their_wording() -> None:
    seen, _ = run({PLAN: heating()})  # a followed result with a checked heating lane

    class Follower(ServiceFollower):
        def _follow(self, proposal: Proposal) -> Any:
            return seen

    def broken(_: str) -> FactSheet:
        raise RuntimeError("an unreadable picture sheet")

    follower = Follower(project(), ServiceFiles(), pictures=broken)
    services, shown = follower.run(
        Proposal(proposal_id="p1", drawing_id=PLAN, page=1, removed=(WALL,))
    )
    assert {d.discipline: d.status for d in services.disciplines}["heating"] == "checked"
    assert "could not be read" not in shown["text"]
    assert all(
        d.reason is None or "could not be read" not in d.reason for d in services.disciplines
    )


def test_a_heating_picture_of_another_floor_is_not_followed() -> None:
    """SFP-16: the follower pairs before it follows; a floor 2 heating picture is refused."""
    base = project()
    plan_file, *_ = base.ingest.status("p").files
    listed = (
        plan_file.model_copy(update={"path": "A-101 Floor 1 plan.pdf"}),
        FileStatus(id="f2", path="H-102 Floor 2 heating.png", size=1, sha256="h", kind="png_plan",
                   state="ready", group="h", route="raster", drawing_id="d2"),
    )  # fmt: skip
    status = base.ingest.status("p").model_copy(update={"files": listed})
    drawing = base.ingest.drawing(PLAN)
    ingest = SimpleNamespace(status=lambda _: status, drawing=lambda _: drawing)
    follower = ServiceFollower(
        SimpleNamespace(project_id="p", ingest=ingest),  # pyright: ignore[reportArgumentType]
        ServiceFiles(),
        pictures={"d2": heating()}.get,
    )
    services, _ = follower.run(Proposal(proposal_id="p1", drawing_id=PLAN, page=1, removed=(WALL,)))
    lanes = {d.discipline: d for d in services.disciplines}
    assert lanes["heating"].status == "not_aligned"
    assert (
        lanes["heating"].reason == "another floor: '2. krs' against 'Floor 1'"
    )  # its title block first


def test_a_picture_without_a_drawing_scale_is_sized_by_its_readers_scale() -> None:
    """fe-ui2's pair: the picture's drawing has no scale offline, but its reader measured one
    (PictureFactSheet.scale, #511); same floor and sheet size, so it is laid page to page."""
    base = project()
    plan_file, *_ = base.ingest.status("p").files
    listed = (
        plan_file.model_copy(update={"path": "set/A-101 Floor 1 plan.pdf"}),
        FileStatus(id="f2", path="set/H-101 Floor 1 heating.png", size=1, sha256="h",
                   kind="png_plan", state="ready", group="h", route="raster", drawing_id="d2"),
    )  # fmt: skip
    status = base.ingest.status("p").model_copy(update={"files": listed})
    plan = base.ingest.drawing(PLAN)
    unscaled = plan.model_copy(update={"scale": Scale(status="no_scale"), "rooms": ()})
    ingest = SimpleNamespace(
        status=lambda _: status, drawing=lambda d: plan if d == PLAN else unscaled
    )
    read = heating()
    facts = PictureFactSheet(
        model=read.model,
        disciplines=read.disciplines,
        facts=[f.model_copy(update={"storey": None}) for f in read.facts],
        scale=PictureScale(width_px=500, height_px=500, m_per_px=0.02),
    )
    follower = ServiceFollower(
        SimpleNamespace(project_id="p", ingest=ingest),  # pyright: ignore[reportArgumentType]
        ServiceFiles(),
        pictures={"d2": facts}.get,
    )
    services, _ = follower.run(Proposal(proposal_id="p1", drawing_id=PLAN, page=1, removed=(WALL,)))
    heated = {d.discipline: d for d in services.disciplines}["heating"]
    assert heated.status == "checked", heated.reason
    assert heated.picture is not None and heated.picture.pairing.paired_by == "metadata"
    assert "page to page" in heated.picture.pairing.reason
    # without the reader's scale: refused, and the reason says why
    follower = ServiceFollower(
        SimpleNamespace(project_id="p", ingest=ingest),  # pyright: ignore[reportArgumentType]
        ServiceFiles(),
        pictures={"d2": facts.model_copy(update={"scale": None})}.get,
    )
    services, _ = follower.run(Proposal(proposal_id="p1", drawing_id=PLAN, page=1, removed=(WALL,)))
    heated = {d.discipline: d for d in services.disciplines}["heating"]
    assert heated.status == "not_aligned"
    assert heated.reason is not None and heated.reason.endswith("the services picture has no scale")
