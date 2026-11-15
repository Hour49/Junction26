"""SV-25, SV-28, SV-31: the services tools in a chat turn (decision 0017 on 0013's chat). A scripted
model calls the tools through the real loop; the project is one IFC file whose stored services
model is the two-room fixture (radiators E2 in SR1 and E3 in SR2 on the south wall SW1)."""

import gzip
import json
from pathlib import Path
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient

from app.adapters.services_store import ServicesStore
from app.api import chat as chat_api
from app.composition import build_ingest
from app.core.agent.ports import Reply
from app.core.errors import NotFoundError
from app.core.ingest.model import FileStatus, ProjectStatus
from app.main import create_app
from app.settings import Settings
from tests.services_fixtures import two_rooms

PROJECT, MODELLED = "a" * 12, "0123456789abcdef"


class _Ingest:
    """A done project of one IFC file (its stored services model may be in the cache)."""

    kind: Literal["ifc", "pdf_vector"] = "ifc"
    drawing_key: str | None = MODELLED

    def status(self, project_id: str) -> ProjectStatus:
        if project_id != PROJECT:
            raise NotFoundError(f"no project {project_id}")
        heating = FileStatus(
            id="f1", path="m/heating.ifc", size=1, sha256="f" * 64, kind=self.kind, state="ready",
            route="bim", drawing_id=self.drawing_key,
        )  # fmt: skip
        return ProjectStatus(
            id=PROJECT, name="p", state="done", created_at="2026-11-14T00:00:00Z", files=(heating,)
        )

    def drawing(self, drawing_id: str) -> Any:
        raise NotFoundError(f"drawing {drawing_id} not read")  # list_drawings: pages unknown


class _SetAside(_Ingest):
    """The IFC file was set aside at upload ("no PDF, PNG or JPEG in its group"): no drawing."""

    drawing_key: str | None = None


class _PdfOnly(_Ingest):
    """The same project with no IFC file: a PDF plan only."""

    kind: Literal["ifc", "pdf_vector"] = "pdf_vector"


def _call(name: str, n: int, **arguments: Any) -> dict[str, Any]:
    return {"id": f"c{n}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}  # fmt: skip


def _step(*calls: dict[str, Any]) -> Reply:
    return Reply({"role": "assistant", "content": None, "tool_calls": list(calls)}, 0.0)


class _Scripted:
    name = "scripted"

    def __init__(self, *replies: Reply) -> None:
        self.replies = list(replies)
        self.results: list[str] = []

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
        self.results += [m["content"] for m in messages if m.get("role") == "tool"]
        return self.replies.pop(0)


def _edit_turn(*calls: dict[str, Any], proposal: str = "p1") -> _Scripted:
    """The model calls the tools, then answers with the proposal it got."""
    final = _call("final_answer", 99, kind="edit", text="Here is the change.", proposal_id=proposal)
    return _Scripted(*(_step(c) for c in calls), _step(final))


def _dont_know(*calls: dict[str, Any]) -> _Scripted:
    final = _call("final_answer", 99, kind="dont_know", text="That cannot be done.")
    return _Scripted(*(_step(c) for c in calls), _step(final))


@pytest.fixture
def client(settings: Settings, tmp_path: Path) -> TestClient:
    return _client(settings, tmp_path)


def _client(
    settings: Settings, tmp_path: Path, follow: str = "on", ingest: _Ingest | None = None
) -> TestClient:
    """The services tools are offered behind SERVICES_FOLLOW (on here unless `follow`)."""
    cache = tmp_path / "services"
    cache.mkdir(exist_ok=True)
    model = two_rooms()
    ServicesStore(cache).path(model.source.sha256).write_bytes(
        gzip.compress(model.model_dump_json().encode())
    )
    settings = settings.model_copy(
        update={"services_cache_dir": cache, "chat_model": "rules", "services_follow": follow}
    )
    app = create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    app.state.ingest = ingest or _Ingest()
    app.state.evidence = None  # the evidence index reads the real ingest; not this test's subject
    return TestClient(app)


def _turn(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    model: _Scripted,
    chat_id: str | None = None,
    **more: Any,
) -> dict[str, Any]:
    monkeypatch.setattr(chat_api, "chat_model", lambda settings: (model, None))
    body = {"message": "move the radiator", **({"chat_id": chat_id} if chat_id else {}), **more}
    response = client.post(f"/api/projects/{PROJECT}/chat", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _move(n: int = 1, element: str = "E2", wall: str = "SW2") -> dict[str, Any]:
    return _call("propose_move_terminal", n, drawing_id=MODELLED, element_id=element, wall_id=wall)


def test_sv25_sv28_a_chat_turn_moves_a_radiator_as_a_services_change(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    turn = _turn(client, monkeypatch, _edit_turn(_move()))
    assert turn["kind"] == "edit", turn
    edit = turn["edit"]
    assert edit["proposal_id"] == "p1" and edit["drawing_id"] == MODELLED and edit["page"] == 1
    assert edit["services"] is None  # #333's follow-up is another field
    change = edit["services_change"]
    assert change["op"] == "move_terminal" and change["moved"][0]["id"] == "E2"
    assert all(c["ok"] for c in change["checks"])
    assert (edit["removed"], edit["added"], edit["rooms"]) == ([], [], [])
    assert change["picture"] == f"/api/projects/{PROJECT}/drawings/{MODELLED}/services/L1.png"


def test_sv31_accept_then_the_next_proposal_is_computed_on_the_accepted_copy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _turn(client, monkeypatch, _edit_turn(_move()))
    chat_id = first["chat_id"]
    accepted = client.post(
        f"/api/projects/{PROJECT}/chat/{chat_id}/proposals/p1", json={"action": "accept"}
    )
    assert accepted.status_code == 200 and accepted.json()["state"] == "accepted"
    # E2 now hangs on SW2: moving it to SW2 again is refused, to SW5 it moves from SW2
    model = _dont_know(_move(1, wall="SW2"))
    _turn(client, monkeypatch, model, chat_id)
    assert any("It is already on that wall." in result for result in model.results)
    second = _turn(client, monkeypatch, _edit_turn(_move(1, wall="SW5"), proposal="p2"), chat_id)
    change = second["edit"]["services_change"]
    assert second["edit"]["proposal_id"] == "p2" and change["based_on"] == ["p1"]
    assert change["moved"][0]["from"][1] < 0.5  # it starts from the north wall (top of the page)


def test_sv25_law_check_does_not_read_a_services_change(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    turn = _turn(client, monkeypatch, _edit_turn(_move()), pack="ch-zh")
    assert turn["edit"]["services_change"] is not None and turn["edit"]["law"] is None


def test_sv25_a_project_without_a_services_model_says_so(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for stored in (tmp_path / "services").iterdir():
        stored.unlink()
    model = _dont_know(_call("list_services", 1, drawing_id=MODELLED))
    _turn(client, monkeypatch, model)
    assert "has been read into a services model yet" in model.results[0]


SIX = {"list_services", "ask_services", "propose_move_terminal", "propose_add_terminal",
       "propose_remove_element", "propose_resize"}  # fmt: skip


def _offered(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> set[str]:
    seen: list[str] = []

    class Looking(_Scripted):
        def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
            seen.extend(t["function"]["name"] for t in tools)
            return super().complete(messages, tools)

    _turn(client, monkeypatch, Looking(_step(_call("final_answer", 1, kind="dont_know", text="?"))))
    return set(seen)


def test_sv25_the_six_tools_are_offered(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _offered(client, monkeypatch) >= SIX


def test_sv25_with_services_follow_off_no_services_tool_is_offered(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    offered = _offered(_client(settings, tmp_path, follow="off"), monkeypatch)
    assert offered and not SIX & offered  # other tools still are


def test_sv25_a_project_without_an_ifc_file_is_offered_no_services_tool(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    offered = _offered(_client(settings, tmp_path, ingest=_PdfOnly()), monkeypatch)
    assert offered and not SIX & offered


def _rules(client: TestClient, message: str, chat_id: str | None = None) -> dict[str, Any]:
    """A turn of the no-keys rules model (CHAT_MODEL=rules, the fixture's setting)."""
    body = {"message": message, **({"chat_id": chat_id} if chat_id else {})}
    response = client.post(f"/api/projects/{PROJECT}/chat", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_sv26_the_rules_model_moves_a_radiator_then_again_on_the_accepted_copy(
    client: TestClient,
) -> None:
    first = _rules(client, "Move radiator E2 to another wall")
    assert first["kind"] == "edit", first
    change = first["edit"]["services_change"]
    assert change["op"] == "move_terminal" and change["moved"][0]["id"] == "E2"
    assert change["based_on"] == [] and "Radiator 22-600" in first["text"]
    chat_id = first["chat_id"]
    accepted = client.post(
        f"/api/projects/{PROJECT}/chat/{chat_id}/proposals/p1", json={"action": "accept"}
    )
    assert accepted.status_code == 200 and accepted.json()["state"] == "accepted"
    second = _rules(client, "Move radiator E2 to wall SW5", chat_id)
    assert second["kind"] == "edit", second
    change = second["edit"]["services_change"]
    assert second["edit"]["proposal_id"] == "p2" and change["based_on"] == ["p1"]
    assert change["moved"][0]["from"][1] < 0.5  # from the north wall p1 put it on


def test_sv26_the_rules_model_answers_what_feeds_from_ask_services(client: TestClient) -> None:
    turn = _rules(client, "What feeds radiator E2?")
    assert turn["kind"] == "answer", turn
    assert turn["text"].startswith("E2 is fed by E1")


@pytest.mark.parametrize(
    "message",
    [
        "What is cut off if we remove the wall between the kitchen and the living room?",
        "Is it legal to move the radiator under the window?",
        "What supplies are needed to repaint the kitchen?",
        "Can I move the door next to the socket?",
    ],
)
def test_sv26_on_a_pdf_only_project_no_turn_calls_a_services_tool(
    settings: Settings, tmp_path: Path, message: str
) -> None:
    turn = _rules(_client(settings, tmp_path, ingest=_PdfOnly()), message)
    assert not {step["tool"] for step in turn["steps"]} & SIX, turn["steps"]


SET_ASIDE = "f" * 16  # the model id of a file with no drawing: its sha256's first 16 characters


def test_sv25_a_set_aside_ifc_is_offered_and_listed_by_its_sha256_prefix(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#281 c6885170828: the services IFC of a project was set aside at upload, so it has no
    drawing id; its stored model is still offered, listed and edited."""
    client = _client(settings, tmp_path, ingest=_SetAside())
    assert _offered(client, monkeypatch) >= SIX
    listed = _dont_know(_call("list_services", 1, drawing_id=SET_ASIDE))
    _turn(client, monkeypatch, listed)
    assert '"E2"' in listed.results[0] and "error" not in json.loads(listed.results[0])
    move = _call("propose_move_terminal", 1, drawing_id=SET_ASIDE, element_id="E2", wall_id="SW2")
    moved = _turn(client, monkeypatch, _edit_turn(move))
    assert moved["kind"] == "edit" and moved["edit"]["drawing_id"] == SET_ASIDE
    assert moved["edit"]["services_change"]["picture"].startswith(
        f"/api/projects/{PROJECT}/drawings/{SET_ASIDE}/services/"
    )


def test_sv26_the_rules_model_finds_a_set_aside_ifc(settings: Settings, tmp_path: Path) -> None:
    turn = _rules(_client(settings, tmp_path, ingest=_SetAside()), "move the radiator")
    assert turn["kind"] in ("edit", "needs_input"), turn["text"]
