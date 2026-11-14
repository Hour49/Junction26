"""USER_SCALE through POST /api/projects/{id}/chat (CHAT_MODEL=rules): a no-scale refusal says what
to type; "the kitchen is 22.4 m2" re-measures that drawing for the chat, never sure; off by
default. The sample's flat-a.pdf is made a sheet without a scale (its rooms' areas unknown)."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.drawing.model import Drawing, Scale
from app.core.pipeline.raster_scale import _shoelace  # pyright: ignore[reportPrivateUsage]
from app.core.pipeline.user_scale import HINT
from app.main import create_app
from app.settings import Settings

QUESTION = "What is the area of the bathroom?"


def scaled_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, on: bool) -> TestClient:
    monkeypatch.chdir(tmp_path)
    return TestClient(create_app(Settings(user_scale=on)))


def no_scale_sample(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    """The sample project with flat-a.pdf read as a sheet without a scale, and that drawing."""
    app: Any = client.app
    project = client.post("/api/projects/sample").json()["url"].split("/")[-1]
    app.state.ingest.wait(project)
    drawings = client.get(f"/api/projects/{project}").json()["drawings"]
    flat_a = next(d["drawing_id"] for d in drawings if d["file"].endswith("flat-a.pdf"))
    read = app.state.ingest.drawing

    def drawing(drawing_id: str) -> Drawing:
        found = read(drawing_id)
        if drawing_id != flat_a:
            return found
        rooms = tuple(room.model_copy(update={"area_m2": None}) for room in found.rooms)
        return found.model_copy(update={"scale": Scale(status="no_scale"), "rooms": rooms})

    monkeypatch.setattr(app.state.ingest, "drawing", drawing)
    return project, flat_a


def turn(client: TestClient, project: str, message: str, chat_id: str | None = None) -> Any:
    body = {"message": message, **({"chat_id": chat_id} if chat_id else {})}
    response = client.post(f"/api/projects/{project}/chat", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def part_of(found: Any, drawing_id: str) -> Any:
    [answer] = found["answers"]
    return next(p["answer"] for p in answer["parts"] if p["drawing_id"] == drawing_id)


def test_a_scale_the_user_gives_answers_that_drawings_areas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = scaled_client(tmp_path, monkeypatch, on=True)
    project, flat_a = no_scale_sample(client, monkeypatch)
    first = turn(client, project, QUESTION)
    refused = part_of(first, flat_a)
    assert refused["refusal"]["code"] == "no-scale" and HINT in refused["refusal"]["text"]
    chat_id = first["chat_id"]
    turn(client, project, "the kitchen is 22.4 m2", chat_id)
    app: Any = client.app
    assert list(app.state.user_scales.of(chat_id)) == [flat_a]  # flat-b prints its own scale
    again = part_of(turn(client, project, QUESTION, chat_id), flat_a)
    assert again["refusal"] is None
    rooms = {room.type: room for room in app.state.ingest.drawing(flat_a).rooms}
    share = {kind: _shoelace(room.polygon) for kind, room in rooms.items() if room.polygon}
    # the bathroom at the scale that makes the kitchen outline 22.4 m² (shown rounded)
    assert again["line"]["answer"] == pytest.approx(
        22.4 * share["bathroom"] / share["kitchen"], abs=0.01
    )
    assert "using the scale you gave: the kitchen is 22.4 m²" in again["explanation"]
    assert again["line"]["sure"] is False and again["line"]["estimate"] is True
    other = part_of(turn(client, project, QUESTION), flat_a)  # a new chat: no scale given there
    assert other["refusal"]["code"] == "no-scale"


def test_off_by_default_nothing_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings().user_scale is False
    client = scaled_client(tmp_path, monkeypatch, on=False)
    project, flat_a = no_scale_sample(client, monkeypatch)
    first = turn(client, project, QUESTION)
    assert HINT not in part_of(first, flat_a)["refusal"]["text"]
    turn(client, project, "the kitchen is 22.4 m2", first["chat_id"])
    again = part_of(turn(client, project, QUESTION, first["chat_id"]), flat_a)
    assert again["refusal"]["code"] == "no-scale"
