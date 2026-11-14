"""DrawingEntry.drawable / not_drawable_reason (board #404, the pen button): GET /api/projects/{id}
says per drawing whether a person can draw an edit on it, and why not, with the same checks the
plan tools refuse an edit with (plan_tools.plan_page), so the two never disagree."""

import dataclasses
from typing import Any

import pytest
from fastapi.testclient import TestClient
from swiss_walls import walled_flat

from app.adapters.pipeline_tools import PipelineStore
from app.adapters.plan_tools import CannotEditError, not_drawable, plan_page
from app.api.views import DrawingEntry, drawings_of
from app.composition import build_ingest
from app.core.drawing.model import Drawing
from app.main import create_app
from app.settings import Settings

SAMPLE = {
    "scans/ground-floor.png": "this plan is a scan: its walls are not geometry",
    "photos/plan-photo.jpg": "this plan is a photo: its walls are not geometry",
    "plans/flat-a.pdf": "no walls are drawn as geometry on this page",
    "model/house.ifc": "this building model has no drawn plan to edit",
}


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )


def listed(client: TestClient, pdf: bytes) -> tuple[str, dict[str, Any]]:
    pid = client.post("/api/projects", params={"name": "flat.pdf"}, content=pdf).json()["id"]
    [drawing] = client.get(f"/api/projects/{pid}").json()["drawings"]
    return pid, drawing


def fields(drawing: dict[str, Any]) -> tuple[bool, str | None]:
    return drawing["drawable"], drawing["not_drawable_reason"]


def test_a_vector_plan_with_walls_rooms_and_scale_is_drawable(client: TestClient) -> None:
    _, drawing = listed(client, walled_flat())
    assert fields(drawing) == (True, None)


def test_a_plan_without_scale_is_not_drawable(client: TestClient) -> None:
    _, drawing = listed(client, walled_flat(scale=False))
    assert fields(drawing) == (False, "this drawing has no scale")


def test_a_plan_without_wall_geometry_is_not_drawable(client: TestClient) -> None:
    from test_vector_pdf import swiss_sheet  # rooms, but no grey wall fills

    _, drawing = listed(client, swiss_sheet().pdf())
    assert fields(drawing) == (False, "no walls are drawn as geometry on this page")


def test_raster_and_model_drawings_of_the_sample_are_not_drawable(client: TestClient) -> None:
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    got = {d["file"]: fields(d) for d in project["drawings"] if d["file"] in SAMPLE}
    assert got == {file: (False, why) for file, why in SAMPLE.items()}


class _NoOutlines:
    """The ingest, but every room of the drawings it gives has lost its outline."""

    def __init__(self, ingest: Any) -> None:
        self.ingest = ingest

    def __getattr__(self, name: str) -> Any:
        return getattr(self.ingest, name)

    def drawing(self, drawing_id: str) -> Drawing:
        drawing = self.ingest.drawing(drawing_id)
        rooms = tuple(r.model_copy(update={"polygon": None}) for r in drawing.rooms)
        return drawing.model_copy(update={"rooms": rooms})


def entry_of(store: PipelineStore, drawing_id: str) -> DrawingEntry:
    status = store.ingest.status(store.project_id)
    return next(e for e in drawings_of(status) if e.drawing_id == drawing_id)


def test_a_plan_whose_rooms_have_no_outlines_is_not_drawable(client: TestClient) -> None:
    pid, drawing = listed(client, walled_flat())
    store = PipelineStore.of_app(client.app, pid)
    store = dataclasses.replace(store, ingest=_NoOutlines(store.ingest))
    entry = entry_of(store, drawing["drawing_id"])
    assert not_drawable(store, entry) == "the rooms on this page have no outlines"


def plan_page_says(store: PipelineStore, entry: DrawingEntry) -> str | None:
    first = store.ingest.drawing(entry.drawing_id).pages
    try:
        plan_page(store, entry.drawing_id, first[0].page if first else 1)
    except CannotEditError as error:
        return str(error)
    return None


def test_the_list_and_plan_page_agree_on_every_fixture(client: TestClient) -> None:
    from test_vector_pdf import swiss_sheet

    stores: list[PipelineStore] = []
    for pdf in (walled_flat(), walled_flat(scale=False), swiss_sheet().pdf()):
        pid, _ = listed(client, pdf)
        stores.append(PipelineStore.of_app(client.app, pid))
    stores.append(dataclasses.replace(stores[0], ingest=_NoOutlines(stores[0].ingest)))
    sample = client.get(client.post("/api/projects/sample").json()["url"]).json()["id"]
    stores.append(PipelineStore.of_app(client.app, sample))
    seen: set[str | None] = set()
    for store in stores:
        project = client.get(f"/api/projects/{store.project_id}").json()
        for drawing in project["drawings"]:
            entry = entry_of(store, drawing["drawing_id"])
            said = plan_page_says(store, entry)
            assert not_drawable(store, entry) == said, drawing["file"]
            if not isinstance(store.ingest, _NoOutlines):  # the route, on the real ingest
                assert fields(drawing) == (said is None, said), drawing["file"]
            seen.add(said)
    assert len(seen) >= 6  # drawable, and each reason, were all compared
