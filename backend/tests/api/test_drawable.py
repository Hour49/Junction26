"""DrawingEntry.drawable / not_drawable_reason (board #404, the pen button): GET /api/projects/{id}
says per drawing whether a person can draw an edit on it, and why not, with the same checks the
plan tools refuse an edit with (plan_tools.plan_page), so the two never disagree."""

import dataclasses
import json
from typing import Any, cast

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


def counted_reads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Every page read of a stored PDF from now on (pipeline_tools._fills' read_page)."""
    import app.adapters.pipeline_tools as pipeline_tools

    reads: list[int] = []
    read_page = pipeline_tools.read_page

    def counting(data: bytes, index: int) -> Any:
        reads.append(index)
        return read_page(data, index)

    monkeypatch.setattr(pipeline_tools, "read_page", counting)
    return reads


def test_review_407_polls_read_a_drawings_page_once(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ingest screens poll the project every 500 ms: each GET read page 1 of every drawable
    PDF again, under the pdfium lock ingest needs."""
    pid, _ = listed(client, walled_flat())
    reads = counted_reads(monkeypatch)
    for _ in range(3):
        [again] = client.get(f"/api/projects/{pid}").json()["drawings"]
        assert fields(again) == (True, None)
    assert len(reads) <= 1


def test_review_407_a_rewritten_drawing_gets_its_new_reason(
    client: TestClient, settings: Settings
) -> None:
    pid, drawing = listed(client, walled_flat())
    assert fields(drawing) == (True, None)
    [stored] = settings.projects_dir.rglob(f"drawings/{drawing['drawing_id']}.json")
    body = json.loads(stored.read_text())
    body["scale"]["m_per_unit"] = None  # read again, this time without a scale
    stored.write_text(json.dumps(body))
    [again] = client.get(f"/api/projects/{pid}").json()["drawings"]
    assert fields(again) == (False, "this drawing has no scale")


def test_review_407_a_pdf_whose_walls_cannot_be_read_does_not_fail_the_project(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.adapters.pipeline_tools as pipeline_tools

    def broken(data: bytes, index: int) -> Any:
        raise RuntimeError("pdfium: cannot load page")

    monkeypatch.setattr(pipeline_tools, "read_page", broken)  # _fills only: ingest reads its own
    pid, _ = listed(client, walled_flat())
    got = client.get(f"/api/projects/{pid}")
    assert got.status_code == 200
    [drawing] = got.json()["drawings"]
    assert fields(drawing) == (False, "the walls of this drawing could not be read")


def test_review_407_a_drawing_read_again_at_another_scale_reads_its_walls_again(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wall fills are measured in metres: a new scale must not reuse the old ones."""
    pid, drawing = listed(client, walled_flat())
    reads = counted_reads(monkeypatch)
    [stored] = settings.projects_dir.rglob(f"drawings/{drawing['drawing_id']}.json")
    body = json.loads(stored.read_text())
    body["scale"]["m_per_unit"] *= 2
    stored.write_text(json.dumps(body))
    client.get(f"/api/projects/{pid}")
    assert len(reads) == 1


def test_review_407b_the_memo_keeps_a_yes_or_no_not_the_wall_fills(client: TestClient) -> None:
    """Whole wall-fill results (up to 189 KB each, 4096 kept) could hold most of a GB."""
    listed(client, walled_flat())
    kept = cast(Any, client.app).state.drawable_fills
    assert kept and all(isinstance(walled, bool) for walled in kept.values())


class _ClearedByAnotherRequest(dict[Any, Any]):
    """A memo another request empties right after this one writes to it (KEPT reached)."""

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self.clear()


def test_review_407b_a_memo_emptied_meanwhile_does_not_fail_the_list(client: TestClient) -> None:
    pid, drawing = listed(client, walled_flat())
    store = PipelineStore.of_app(client.app, pid)
    entry = entry_of(store, drawing["drawing_id"])
    assert not_drawable(store, entry, _ClearedByAnotherRequest()) is None


def test_the_sample_has_a_drawable_plan(client: TestClient) -> None:
    """#416 check: every drawing of /sample was drawable false, so the pen did nothing on the
    no-keys demo. plans/flat-c.pdf draws its walls as grey fills (as tests/swiss_walls.py)."""
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    drawable = {d["file"]: d["name"] for d in project["drawings"] if d["drawable"]}
    assert list(drawable) == ["plans/flat-c.pdf"]


@pytest.mark.parametrize("pack", ["fi", "ch-zh"])
def test_the_samples_walled_plan_fails_no_rule(client: TestClient, pack: str) -> None:
    """The sample's one failed rule stays flat-b's 8.06 m2 bedroom under ch-zh (the demo's
    story): flat-c's Stanza has a window, so it passes both packs' window rules."""
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    found = client.get(f"/api/projects/{project['id']}/checks", params={"pack": pack}).json()
    failed = [
        (d["file"], result["subject"]["label"])
        for d in found["drawings"]
        for rule in d["rules"]
        for result in rule["results"]
        if result["status"] == "fail"
    ]
    assert failed == ([("plans/flat-b.pdf", "Zimmer 1.05")] if pack == "ch-zh" else [])


def test_an_edit_on_the_samples_walled_plan_passes_the_finnish_window_rule(
    client: TestClient,
) -> None:
    """fail-1's #427 review: flat-c had no window, so every edit's law check said "a bedroom or
    living room has a window: still doesn't meet". Stanza's window passes it before and after."""
    from app.adapters.plan_tools import PlanStore, run_plan_tool
    from app.api.checks import find_pack

    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    drawing = next(d["drawing_id"] for d in project["drawings"] if d["file"] == "plans/flat-c.pdf")
    packs = cast(Any, client.app).state.rule_packs
    store = PlanStore.of_app(client.app, project["id"])
    store = dataclasses.replace(store, pack=find_pack(packs, "fi"))
    where = {"drawing_id": drawing, "page": 1}
    walls = json.loads(run_plan_tool(store, "list_walls", where))
    rooms = {room["label"]: room["id"] for room in walls["rooms"]}
    removed = {**where, "room_a": rooms["Bagno 1.01"], "room_b": rooms["Stanza 1.02"]}
    found = json.loads(run_plan_tool(store, "propose_remove_wall", removed))
    [window] = [f for f in found["law"]["findings"] if f["rule_id"] == "fi-habitable-room-window"]
    assert (window["before"]["status"], window["after"]["status"]) == ("pass", "pass")
