"""POST /api/projects/{id}/chat with CHAT_MODEL=rules (decision 0013, spec AC-11, AC-22..AC-25)."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import upload
from fastapi.testclient import TestClient
from swiss_walls import walled_flat

from app.adapters.agent_tools import project_toolbox
from app.adapters.plan_tools import PlanStore, run_plan_tool
from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings


def sample(client: TestClient) -> str:
    return client.post("/api/projects/sample").json()["url"].split("/")[-1]


def ask(client: TestClient, project: str, message: str, **more: Any) -> dict[str, Any]:
    response = client.post(f"/api/projects/{project}/chat", json={"message": message, **more})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def walled(client: TestClient) -> tuple[str, str]:
    """A project of one swiss sheet whose walls are grey fills, and its drawing id."""
    project = upload(client, walled_flat(), "flat.pdf")
    return project, client.get(f"/api/projects/{project}").json()["drawings"][0]["drawing_id"]


def test_ac11_ac22_an_answer_turn_with_sources_and_steps(client: TestClient) -> None:
    project = sample(client)
    turn = ask(client, project, "How many doors are there?")
    assert re.fullmatch(r"[0-9a-f]{12}", turn["chat_id"]) and turn["turn"] == 1
    assert turn["kind"] == "answer" and turn["model"] == "rules" and turn["cost_usd"] == 0
    assert "[1]" in turn["text"] and turn["evidence"][0]["n"] == 1
    assert (
        turn["evidence"][0]["name"].startswith("Drawn plan")
        and len(turn["evidence"][0]["box"]) == 4
    )
    assert [step["tool"] for step in turn["steps"]] == ["ask_drawings"]
    cited = set(re.findall(r"\[(\d+)\]", turn["text"]))
    assert {str(e["n"]) for e in turn["evidence"]} == cited  # only what the text cites
    assert turn["text"] == "The drawings answer this below [1][2]."
    [answer] = turn["answers"]  # the project ask result, as POST /api/projects/{id}/ask gives it
    asked = client.post(
        f"/api/projects/{project}/ask", json={"question": "How many doors are there?"}
    )
    assert answer["total"] == asked.json()["total"] and len(answer["parts"]) == len(
        asked.json()["parts"]
    )
    again = ask(client, project, "How many windows are there?", chat_id=turn["chat_id"])
    assert (again["chat_id"], again["turn"]) == (turn["chat_id"], 2)


def test_ac11_dont_know_turns(client: TestClient) -> None:
    project = sample(client)
    unknown = ask(client, project, "What is the fire rating?")
    assert unknown["kind"] == "dont_know" and unknown["text"].startswith("This question")
    assert unknown["options"] and unknown["options"][0]["message"].endswith("?")
    assert len(unknown["answers"]) == 1 and unknown["answers"][0]["parts"]
    load = ask(client, project, "Is that wall load-bearing?")
    assert load["kind"] == "dont_know" and "structural engineer" in load["text"]


def test_ac11_an_edit_is_refused_on_a_sheet_without_wall_fills(client: TestClient) -> None:
    turn = ask(client, sample(client), "Remove the wall between the bathroom and the bedroom")
    assert turn["kind"] == "dont_know" and turn["edit"] is None
    assert turn["text"].startswith("I can't edit this plan")


def test_ac11_ac22_remove_a_wall_end_to_end_then_accept(
    client: TestClient, walled: tuple[str, str]
) -> None:
    project, _ = walled
    turn = ask(
        client, project, "Remove the wall between Bagno and Stanza to make the bathroom larger"
    )
    assert turn["kind"] == "edit", turn
    edit = turn["edit"]
    assert edit["proposal_id"] == "p1" and edit["state"] == "proposed" and edit["removed"]
    [room] = edit["rooms"]
    assert room["area_after_m2"] > room["area_before_m2"] and len(room["was"]) == 2
    assert [step["tool"] for step in turn["steps"]] == [
        "list_drawings", "list_walls", "propose_remove_wall"]  # fmt: skip
    assert turn["steps"][1]["label"] == "Listed the walls of Drawn plan 1, page 1"
    url = f"/api/projects/{project}/chat/{turn['chat_id']}/proposals/p1"
    accepted = client.post(url, json={"action": "accept"})
    assert accepted.status_code == 200 and accepted.json()["state"] == "accepted"
    assert client.post(url, json={"action": "reject"}).status_code == 409
    missing = url.replace("/p1", "/p9")
    assert client.post(missing, json={"action": "reject"}).status_code == 404


def test_ac11_a_room_in_a_drawn_region(client: TestClient, walled: tuple[str, str]) -> None:
    project, drawing = walled
    region = {"id": "sel_1", "kind": "region", "drawing_id": drawing, "page": 1,
              "box": [0.40, 0.27, 0.47, 0.40]}  # fmt: skip
    turn = ask(client, project, "Put a storage room here", selection=[region])
    assert turn["kind"] == "edit", turn
    assert turn["steps"][0]["tool"] == "propose_room" and turn["edit"]["added"]


def test_ac22_errors(client: TestClient) -> None:
    project = sample(client)
    chat = f"/api/projects/{project}/chat"
    assert client.post(chat, json={"message": "hi", "chat_id": "0" * 12}).status_code == 404
    assert client.post(chat, json={"message": ""}).status_code == 422
    assert client.post("/api/projects/000000000000/chat", json={"message": "hi"}).status_code == 404
    first = ask(client, project, "How many doors are there?")
    app: Any = client.app
    lock = app.state.chats.lock(first["chat_id"])
    with lock:
        busy = client.post(chat, json={"message": "and windows?", "chat_id": first["chat_id"]})
    assert busy.status_code == 409 and "still running" in busy.json()["detail"]


def test_ac23_the_chat_is_kept_on_disk(client: TestClient, settings: Settings) -> None:
    project = sample(client)
    turn = ask(client, project, "How many doors are there?")
    path = settings.projects_dir / project / "chats" / f"{turn['chat_id']}.json"
    kept = path.read_text(encoding="utf-8")
    assert '"role": "assistant"' in kept and '"turns"' in kept


def test_ac24_ac25_off_is_503_and_info_says_so(settings: Settings) -> None:
    off = settings.model_copy(update={"chat_model": "off"})
    client = TestClient(create_app(off, build_ingest(off, off.projects_dir, background=False)))
    project = sample(client)
    response = client.post(f"/api/projects/{project}/chat", json={"message": "hi"})
    assert response.status_code == 503
    chat = client.get("/api/info").json()["chat"]
    assert chat == {
        "model": "off",
        "available": False,
        "reason": "the agent chat is off (CHAT_MODEL=off)",
    }


def test_ac24_info_gemini_without_a_key_is_not_available(settings: Settings) -> None:
    gemini = settings.model_copy(update={"chat_model": "gemini"})
    client = TestClient(create_app(gemini, build_ingest(gemini, gemini.projects_dir)))
    chat = client.get("/api/info").json()["chat"]
    assert chat["available"] is False and "GEMINI_API_KEY" in chat["reason"]


def test_ac24_info_rules_is_available(client: TestClient) -> None:
    assert client.get("/api/info").json()["chat"] == {
        "model": "rules", "available": True, "reason": None}  # fmt: skip


FLOOR9178 = (
    Path(__file__).parents[3]
    / "data/stoa/full/junction-dataset/data/swiss_dwellings/site980_bldg2055_floor9178.pdf"
)


@pytest.mark.skipif(not FLOOR9178.is_file(), reason="partner data absent (data/stoa/full)")
def test_ac11_floor9178_two_bathrooms_ask_which(client: TestClient) -> None:
    project = upload(client, FLOOR9178.read_bytes(), "floor9178.pdf")
    turn = ask(client, project, "How big is the bathroom?")
    assert turn["kind"] == "needs_input"
    assert [o["label"] for o in turn["options"]] == ["Room 1.01", "Room 1.09"]


def test_ac13_the_evidence_tools_are_offered(client: TestClient) -> None:
    project = sample(client)
    tools = {
        tool["function"]["name"] for tool in project_toolbox(client.app, project, [], {}).tools
    }
    assert {"search_evidence", "get_evidence", "ask_drawings", "list_walls"} <= tools


def test_ac13_the_law_tools_are_offered_when_the_app_has_laws(client: TestClient) -> None:
    pytest.importorskip("app.adapters.law_tools")  # on main since #249: runs once merged
    app: Any = client.app
    assert getattr(app.state, "laws", None) is not None
    tools = {
        tool["function"]["name"] for tool in project_toolbox(app, sample(client), [], {}).tools
    }
    assert {"search_law", "get_clause"} <= tools


def test_lc6_an_unknown_pack_is_422(client: TestClient) -> None:
    project = sample(client)
    response = client.post(f"/api/projects/{project}/chat", json={"message": "hi", "pack": "xx"})
    assert response.status_code == 422 and "xx" in response.json()["detail"]


def test_lc6_a_known_pack_reaches_the_plan_tools_and_none_works_as_before(
    client: TestClient,
) -> None:
    project = sample(client)
    assert ask(client, project, "How many doors are there?", pack="fi")["kind"] == "answer"
    assert ask(client, project, "How many doors are there?")["kind"] == "answer"
    app: Any = client.app
    fi = next(pack for pack in app.state.rule_packs if pack.id == "fi")
    toolbox = project_toolbox(app, project, [], {}, fi)
    runner: Any = toolbox._runners["propose_room"]  # pyright: ignore[reportPrivateUsage]
    store = runner.args[0]  # the PlanStore the plan tools run on
    assert store.pack == fi


STORAGE = [0.40, 0.27, 0.47, 0.40]  # a region in Stanza 1.02 (11.66 m2 printed) of walled_flat


def storage(client: TestClient, walled: tuple[str, str], **more: Any) -> dict[str, Any]:
    project, drawing = walled
    region = {"id": "sel_1", "kind": "region", "drawing_id": drawing, "page": 1, "box": STORAGE}
    return ask(client, project, "Put a storage room here", selection=[region], **more)


def test_lc7_lc8_lc10_ch_zh_names_the_rule_a_storage_room_breaks_and_accept_keeps_it(
    client: TestClient, walled: tuple[str, str]
) -> None:
    turn = storage(client, walled, pack="ch-zh")
    assert turn["kind"] == "edit", turn
    law = turn["edit"]["law"]
    assert (law["pack"], law["note"].startswith("A pre-check of")) == ("ch-zh", True)
    area = law["findings"][0]
    assert (area["rule_id"], area["change"], area["subject"]) == (
        "ch-zh-room-area", "newly_fails", "Stanza 1.02")  # fmt: skip
    assert area["before"]["value"] == pytest.approx(11.66, abs=0.01) and area["after"]["value"] < 10
    assert area["ev"] == "ev_1" and area["clause"]["quote"]  # the full clause, quote included
    assert "Stanza 1.02 would not meet" in turn["text"] and "[1]" in turn["text"]
    assert turn["evidence"][0]["label"] == "Stanza 1.02" and len(turn["evidence"][0]["box"]) == 4
    assert "ch-zh-ls-700-1-303" in [c["id"] for c in law["related"]]  # PBG § 303, room areas
    url = f"/api/projects/{walled[0]}/chat/{turn['chat_id']}/proposals/p1"
    accepted = client.post(url, json={"action": "accept"}).json()
    assert accepted["state"] == "accepted" and accepted["law"] == law


def test_lc7_fi_meets_and_no_pack_has_no_law(client: TestClient, walled: tuple[str, str]) -> None:
    fi = storage(client, walled, pack="fi")
    changes = {(f["rule_id"], f["change"]) for f in fi["edit"]["law"]["findings"]}
    assert ("fi-habitable-room-area", "still_passes") in changes
    assert all(change != "newly_fails" for _, change in changes)
    assert "would not meet" not in fi["text"]
    assert storage(client, walled)["edit"]["law"] is None


@pytest.mark.skipif(not FLOOR9178.is_file(), reason="partner data absent (data/stoa/full)")
@pytest.mark.parametrize(("pack", "change"), [("ch-zh", "newly_fails"), ("fi", "still_passes")])
def test_lc7_floor9178_a_storage_room_over_most_of_stanza_1_02(
    client: TestClient, pack: str, change: str
) -> None:
    """Spec §1 step 2: the same box breaks Zürich's 10 m2 and meets Finland's 7 m2."""
    project = upload(client, FLOOR9178.read_bytes(), "floor9178.pdf")
    drawing = client.get(f"/api/projects/{project}").json()["drawings"][0]["drawing_id"]
    walls = json.loads(run_plan_tool(PlanStore.of_app(client.app, project), "list_walls",
                                     {"drawing_id": drawing, "page": 1}))  # fmt: skip
    (stanza,) = [r for r in walls["rooms"] if r["label"] == "Stanza 1.02"]
    x0, y0, x1, y1 = stanza["box"]
    region = {"id": "sel_1", "kind": "region", "drawing_id": drawing, "page": 1,
              "box": [x0 + (x1 - x0) * 0.7, y0 + 0.002, x1 - 0.002, y1 - 0.002]}  # fmt: skip
    turn = ask(client, project, "Put a storage room here", selection=[region], pack=pack)
    assert turn["kind"] == "edit", turn
    area = [f for f in turn["edit"]["law"]["findings"] if f["subject"] == "Stanza 1.02"
            and f["rule_id"].endswith("room-area")]  # fmt: skip
    assert [f["change"] for f in area] == [change]


def test_robust_6_ac22_a_blank_message_is_422(client: TestClient) -> None:
    chat = f"/api/projects/{sample(client)}/chat"
    assert client.post(chat, json={"message": "   \n"}).status_code == 422


def test_robust_3_ac24_the_rules_chat_runs_when_the_gemini_budget_is_used_up(
    settings: Settings,
) -> None:
    spent = settings.model_copy(update={"gemini_budget_usd": 0.0})
    client = TestClient(
        create_app(spent, build_ingest(spent, spent.projects_dir, background=False))
    )
    turn = ask(client, sample(client), "How many doors are there?")
    assert turn["kind"] == "answer" and "budget" not in turn["text"]
    assert client.get("/api/info").json()["chat"] == {
        "model": "rules", "available": True, "reason": None}  # fmt: skip


class Seen:
    """A ChatModel that keeps what it is sent and ends every turn."""

    name = "seen"

    def __init__(self) -> None:
        self.sent: list[list[dict[str, Any]]] = []

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        from app.core.agent.ports import Reply

        self.sent.append(messages)
        args = {"kind": "dont_know", "text": "Seen."}
        call = {"id": "c1", "type": "function",
                "function": {"name": "final_answer", "arguments": json.dumps(args)}}  # fmt: skip
        return Reply({"role": "assistant", "content": None, "tool_calls": [call]}, 0.0)


def test_answers_3_robust_4_lc6_lc14_the_model_is_told_the_country_on_every_turn(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.api.chat as chat_api
    from app.core.agent.prompt import NO_COUNTRY

    seen = Seen()
    monkeypatch.setattr(chat_api, "chat_model", lambda settings: (seen, None))
    project = sample(client)
    ask(client, project, "How big must a bedroom be?", pack="fi")
    ask(client, project, "How big must a bedroom be?")
    fi, none = (sent[0]["content"] for sent in seen.sent)
    assert "Country chosen by the person: Finland" in fi and "(pack fi)" in fi
    assert "search_law(pack='fi'" in fi  # the pack's law contents (AC-9)
    assert none.endswith(NO_COUNTRY)


def test_robust_10_ac2_a_sideways_drag_gets_the_true_reason_on_the_rules_planner(
    client: TestClient, walled: tuple[str, str]
) -> None:
    project, drawing = walled
    line = {"id": "sel_1", "kind": "region", "drawing_id": drawing, "page": 1,
            "box": [0.40, 0.30, 0.47, 0.30]}  # fmt: skip
    turn = ask(client, project, "Put a storage room here", selection=[line])
    assert turn["kind"] == "dont_know" and "line, not an area" in turn["text"], turn["text"]
    assert [step["tool"] for step in turn["steps"]] == ["propose_room"]
