"""SERVICES_FOLLOW through the chat API (decision 0016): off by default, and on a project
without service models every lane says so and the answer's text is what it was."""

from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from swiss_walls import walled_flat

from app.adapters.chat_rules import RulesChatModel
from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings

MESSAGE = "Remove the wall between Bagno and Stanza to make the bathroom larger"


def edit_turn(client: TestClient) -> dict[str, Any]:
    project = upload(client, walled_flat(), "flat.pdf")
    response = client.post(f"/api/projects/{project}/chat", json={"message": MESSAGE})
    assert response.status_code == 200, response.text
    turn = response.json()
    assert turn["kind"] == "edit", turn
    return turn


def test_sf15_off_by_default_a_proposal_has_no_services(client: TestClient) -> None:
    assert edit_turn(client)["edit"]["services"] is None


def test_sf15_on_every_lane_is_listed_and_a_project_without_models_says_so(
    settings: Settings, client: TestClient
) -> None:
    plain = edit_turn(client)
    following = settings.model_copy(
        update={"services_follow": "on", "projects_dir": settings.projects_dir / "on"}
    )
    ingest = build_ingest(following, following.projects_dir, background=False)
    turn = edit_turn(TestClient(create_app(following, ingest)))
    services = turn["edit"]["services"]
    assert [d["discipline"] for d in services["disciplines"]] == [
        "plumbing", "ventilation", "heating", "electrical"]  # fmt: skip
    assert {d["status"] for d in services["disciplines"]} == {"no_model"}
    assert services["disciplines"][3]["line"] == (
        "Electrical: not checked, this project has no electrical model."
    )
    assert services["unknowns"] == [] and services["storey"] is None
    assert turn["text"] == plain["text"]  # nothing was checked, so nothing is said of services
    assert turn["edit"]["rooms"] == plain["edit"]["rooms"]  # the edit itself is the same


def test_sf15_the_rules_planner_says_the_services_text_of_a_proposal() -> None:
    import json

    proposal = {
        "status": "ok",
        "proposal": {"proposal_id": "p1", "removed": [], "unknowns": [], "rooms": []},
        "services": {"text": "Heating: 1 to re-seat. Not checked: electrical (no model)."},
    }
    place = {"drawing_id": "0123456789abcdef", "page": 1, "wall_id": "W1"}
    arguments = json.dumps(place)
    call = {
        "id": "c0",
        "type": "function",
        "function": {"name": "propose_remove_wall", "arguments": arguments},
    }
    messages = [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "Remove wall W1"},
        {"role": "assistant", "tool_calls": [call]},
        {"role": "tool", "tool_call_id": "c0", "content": json.dumps(proposal)},
    ]
    names = ("list_drawings", "list_walls", "propose_remove_wall", "final_answer")
    tools = [{"type": "function", "function": {"name": name}} for name in names]
    [answer] = RulesChatModel().complete(messages, tools).message["tool_calls"]
    text = json.loads(answer["function"]["arguments"])["text"]
    assert text.endswith("Heating: 1 to re-seat. Not checked: electrical (no model).")


@pytest.mark.parametrize("value", ["off", "on"])
def test_sf15_the_setting_takes_off_and_on(value: str) -> None:
    assert Settings(services_follow=value).services_follow == value  # pyright: ignore[reportArgumentType]
