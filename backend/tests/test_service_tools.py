"""A proposal followed through a project's service models (spec services-follow, SF-16): the
models are laid over the sheet through the model's spaces, kept to the sheet's storey, and
every reason not to follow is said per lane. The project is scripted; the plan page is the
synthetic one of test_services_follow."""

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest
from shapely.geometry import box
from test_services_follow import page, removal, ring, run, terminal

from app.adapters import service_tools
from app.adapters.ifc_services import ServiceFile, ServiceFiles
from app.adapters.service_tools import NOT_FROM_MODEL, ServiceFollower, for_model
from app.core.drawing.model import Drawing, ModelObject, Scale
from app.core.errors import InvalidInputError
from app.core.ingest.model import FileStatus, ProjectStatus
from app.core.pipeline.model import Route
from app.core.plan_edit.walls import PlanPage, PlanRoom
from app.core.services.model import ServiceElement

DRAWING = "d" * 16
STORE = box(0, 5, 3, 8)  # a third room: a frame needs three rooms that are not in one line
CENTRES = {"guid-a": (1.5, 1.5), "guid-b": (5.1, 1.5), "guid-c": (1.5, 6.5)}  # on the page, m
ROOMS = {"guid-a": "r1", "guid-b": "r2", "guid-c": "r3", "guid-d": None}  # guid-d: not drawn


def sheet() -> PlanPage:
    two = page()
    return replace(two, rooms=(*two.rooms, PlanRoom("r3", "Store", "storage", ring(STORE))))


def to_model(x: float, y: float) -> tuple[float, float]:
    """The page's metres in the model's: the model is 100 m east and its y runs up."""
    return (x + 100.0, 50.0 - y)


def in_model(element: ServiceElement) -> ServiceElement:
    def moved(p: tuple[float, float, float]) -> tuple[float, float, float]:
        return (*to_model(p[0], p[1]), p[2])

    return ServiceElement(
        **{**element.__dict__, "at": moved(element.at), "ports": tuple(map(moved, element.ports))}
    )


ARCH = ServiceFile(
    storeys=(("Ground", 0.0), ("Upper", 3.0)),
    spaces={**{guid: to_model(*at) for guid, at in CENTRES.items()}, "guid-d": (140.0, 20.0)},
    lanes=(),
    elements=(),
)
HEATING = ServiceFile(
    storeys=(("Ground", 0.0), ("Upper", 3.0)),
    spaces={},
    lanes=("heating",),
    elements=(
        in_model(run("feed", (1.0, 2.9, 0.2), (2.9, 2.9, 0.2), "H_flow", "rad")),
        in_model(terminal("rad", (2.95, 1.5, 0.5), ("H_flow",), "feed")),
        in_model(terminal("upstairs", (2.95, 1.5, 3.5), ())),  # the same spot, a storey up
    ),
)


def project(route: Route = "bim", **files: ServiceFile) -> tuple[Any, ServiceFiles]:
    """A scripted project: the sheet read from arch.ifc, and one IFC file per keyword."""
    models = {"arch": ARCH, **files}
    listed = [
        FileStatus(id="f1", path="plan.pdf", size=1, sha256="sheet", kind="pdf_vector",
                   state="ready", group="plan", route=route, source="arch.ifc",
                   drawing_id=DRAWING),
        *(
            FileStatus(id=f"m{n}", path=f"{name}.ifc", size=10 + n, sha256=name, kind="ifc",
                       state="set_aside")
            for n, name in enumerate(models)
        ),
    ]  # fmt: skip
    status = ProjectStatus(
        id="p", name="demo", state="done", created_at="2026-11-14T00:00:00Z", files=tuple(listed)
    )
    drawing = Drawing(
        file="plan.pdf",
        pages=(),
        scale=Scale(status="scaled", m_per_unit=1.0),
        model_objects=tuple(
            ModelObject(id=f"m{n}", class_="space", storey="Ground", global_id=guid, element=room)
            for n, (guid, room) in enumerate(ROOMS.items(), start=1)
        ),
    )
    ingest = SimpleNamespace(
        status=lambda _: status,
        drawing=lambda _: drawing,
        upload_bytes=lambda _, file_id: next(
            f.sha256 or "" for f in listed if f.id == file_id
        ).encode(),
    )
    reads = ServiceFiles(lambda data: _read(models, data))
    return SimpleNamespace(project_id="p", ingest=ingest), reads


def _read(models: dict[str, ServiceFile], data: bytes) -> ServiceFile:
    if data == b"broken":
        raise InvalidInputError("not an IFC file")
    return models[data.decode()]


@pytest.fixture(autouse=True)
def the_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_tools, "plan_page", lambda *_: sheet())


def followed(route: Route = "bim", **files: ServiceFile) -> tuple[Any, dict[str, Any]]:
    pipeline, reads = project(route, **files)
    credits = {"heating": "Heating model: MIT, RWTH"}
    follower = ServiceFollower(pipeline, reads, lambda size, sha256: credits.get(sha256))
    return follower.run(removal().model_copy(update={"drawing_id": DRAWING}))


def test_sf16_a_service_model_is_laid_over_the_sheet_through_the_models_spaces() -> None:
    services, shown = followed(heating=HEATING)
    lanes = {d.discipline: d for d in services.disciplines}
    statuses = [d.status for d in services.disciplines]
    assert statuses == ["no_model", "no_model", "checked", "no_model"]
    heating = lanes["heating"]
    assert heating.source == "heating.ifc" and heating.elements == 2  # not the one upstairs
    (reseat,) = [a for a in heating.actions if a.code == "reseat"]
    assert reseat.status == "follows" and "radiator in Office 1" in reseat.label
    marks = {mark.ref: mark for mark in heating.marks}
    # the radiator's mark is back where it is on the page: 2.95 m, 1.5 m of a 10 m sheet
    assert marks[reseat.refs[0]].at == pytest.approx((0.295, 0.15), abs=1e-4)
    assert services.storey == "Ground" and services.credits == ("Heating model: MIT, RWTH",)
    assert shown["text"].startswith("Heating: 1 to re-seat.")
    assert "Not checked: plumbing (this project has no plumbing model)" in shown["text"]


def test_sf16_the_model_reads_lines_and_plain_actions_never_refs_or_places() -> None:
    services, shown = followed(heating=HEATING)
    assert shown == for_model(services)
    lane = shown["disciplines"][2]
    assert lane["discipline"] == "heating" and lane["model"] == "heating.ifc"
    assert lane["summary"]["follows"] == 1 and lane["more_actions"] == 0
    assert set(lane["actions"][0]) == {"status", "what"}
    assert "marks" not in lane and "refs" not in str(shown) and "moved_to" not in str(shown)


def test_sf16_a_model_without_the_sheets_storey_is_not_followed() -> None:
    elsewhere = ServiceFile((("Level 9", 27.0),), {}, ("heating",), HEATING.elements)
    services, _ = followed(heating=elsewhere)
    lane = services.disciplines[2]
    assert lane.status == "not_aligned" and lane.actions == ()
    assert lane.line == (
        "Heating: not checked, its storeys are not this building's (none at 0.00 m)."
    )


def test_sf16_a_plan_that_was_not_drawn_from_a_model_is_not_followed() -> None:
    services, shown = followed("vector", heating=HEATING)
    assert services.disciplines[2].status == "not_aligned"
    assert services.disciplines[2].reason == NOT_FROM_MODEL
    assert shown["text"] == ""  # nothing checked: the answer says nothing of services


def test_sf16_a_sheet_the_model_does_not_fit_is_not_followed() -> None:
    other = ServiceFile(ARCH.storeys, {**ARCH.spaces, "guid-b": (120.0, 48.5)}, (), ())
    services, _ = followed(arch=other, heating=HEATING)  # another building's model
    assert services.disciplines[2].status == "not_aligned"
    assert "scale and the model disagree" in (services.disciplines[2].reason or "")
    few = ServiceFile(ARCH.storeys, {"guid-a": ARCH.spaces["guid-a"]}, (), ())
    services, _ = followed(arch=few, heating=HEATING)
    assert "3 are needed" in (services.disciplines[2].reason or "")


def test_sf16_a_project_without_service_models_has_four_unchecked_lanes() -> None:
    services, shown = followed()
    assert {d.status for d in services.disciplines} == {"no_model"} and shown["text"] == ""


def test_sf16_a_failure_leaves_the_edit_and_says_the_lanes_were_not_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_: object) -> None:
        raise RuntimeError("geometry kernel")

    monkeypatch.setattr(service_tools, "follow", broken)
    services, _ = followed(heating=HEATING)
    assert {d.status for d in services.disciplines} == {"no_model"}
    assert services.disciplines[0].line == (
        "Plumbing: not checked, the service models could not be read (RuntimeError)."
    )
