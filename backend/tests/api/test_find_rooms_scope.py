"""find_rooms says what it searched (demo walk r13, regression 2): "Which drawings show a kitchen?"
went to find_rooms, which matched printed labels only, and the answer named 2 drawings as if
complete. Drawn plan 1's 3 kitchens are labelled "0.03", "0.16", "0.19" (typed kitchen), and a
building model has no drawn rooms to search."""

import json
from types import SimpleNamespace
from typing import Any

from test_api_drawing_names import read, status

from app.adapters.agent_tools import _find_rooms  # pyright: ignore[reportPrivateUsage]
from app.core.drawing.model import Drawing, Page, Room, RoomType, Scale
from app.core.errors import NotFoundError

PAGE = Page(page=1, width=100, height=100, unit="pt")


def room(n: int, kind: RoomType, label: str | None) -> Room:
    return Room(id=f"r{n}", type=kind, label=label, page=1, box=(0.1 * n, 0.1, 0.1 * n + 0.05, 0.2))


def drawing(*rooms: Room) -> Drawing:
    return Drawing(file="x", pages=(PAGE,), scale=Scale(status="no_scale"), rooms=rooms)


DRAWINGS: dict[str, Drawing] = {
    "d1": drawing(
        room(1, "kitchen", "0.03"), room(2, "kitchen", "0.16"), room(3, "bedroom", "0.02")
    ),
    "d2": drawing(room(4, "kitchen", "KITCHEN"), room(5, "living", "LIVING")),
    "d3": drawing(),  # a building model: no drawn rooms
}


class Ingest:
    def status(self, project_id: str) -> Any:
        return status(
            read("plans/a.pdf", "pdf_vector", "d1"),
            read("scans/b.png", "png_plan", "d2"),
            read("bim/house.ifc", "ifc", "d3"),
            read("photos/c.jpg", "photo_plan", "d4"),
        )

    def drawing(self, drawing_id: str) -> Drawing:
        if drawing_id not in DRAWINGS:
            raise NotFoundError("not read")
        return DRAWINGS[drawing_id]


def find(query: str) -> Any:
    store = SimpleNamespace(project_id="p", ingest=Ingest())
    return json.loads(_find_rooms(store, "find_rooms", json.dumps({"query": query})))  # pyright: ignore[reportArgumentType]


def test_a_room_typed_kitchen_is_found_though_its_label_is_a_number() -> None:
    found = find("kitchen")
    assert found["status"] == "ok"
    assert [(r["name"], r["label"]) for r in found["rooms"]] == [
        ("Drawn plan 1", "0.03"),
        ("Drawn plan 1", "0.16"),
        ("Plan image 1", "KITCHEN"),
    ]
    assert [r["label"] for r in find("kitchen 0.16")["rooms"]] == ["0.16"]  # every word still


def test_the_drawings_it_could_not_search_are_named() -> None:
    """A drawing with no rooms read (the model) or not read at all is named, so an answer built
    on find_rooms can't call its list complete."""
    expected = [
        {"name": "Building model 1", "why": "no rooms were read on it"},
        {"name": "Plan photo 1", "why": "it was not read"},
    ]
    assert find("kitchen")["not_searched"] == expected
    none = find("sauna")
    assert none["status"] == "unknown" and none["not_searched"] == expected
