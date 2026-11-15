"""PIPELINE_TOOLS for the agent chat (board #222): each tool gives what its HTTP route gives, and
a bad call is {"error": ...}, never an exception."""

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pdf_sheets import rect
from test_vector_pdf import swiss_sheet

from app.adapters import pipeline_tools
from app.adapters.pipeline_tools import (
    _RUNNERS,
    PIPELINE_TOOLS,
    PipelineStore,
    geometry_of,
    run_pipeline_tool,
)
from app.adapters.vector_pdf.objects import read_page
from app.adapters.vector_pdf.scale import read_scale
from app.adapters.vector_pdf.wall_fills import wall_fills
from app.api.checks import ProjectChecks
from app.composition import build_ingest
from app.core.agent.loop import _for_model
from app.core.checks.model import RulePack
from app.core.drawing.model import Drawing
from app.main import create_app
from app.settings import Settings

RULES = Path(__file__).parents[1] / "fixtures" / "rules"
FLOOR = (
    Path(__file__).parents[3]
    / "data/stoa/full/junction-dataset/data/swiss_dwellings/site980_bldg2055_floor9178.pdf"
)
DOORS = "How many doors are there?"
BOX = (0.1, 0.1, 0.2, 0.2)


@pytest.fixture
def checked(settings: Settings) -> TestClient:
    """The app with the TEST rule pack only."""
    settings = settings.model_copy(update={"rule_packs_dir": RULES})
    ingest = build_ingest(settings, settings.projects_dir, background=False)
    return TestClient(create_app(settings, ingest))


@pytest.fixture
def project(checked: TestClient) -> dict[str, Any]:
    return checked.get(checked.post("/api/projects/sample").json()["url"]).json()


@pytest.fixture
def store(checked: TestClient, project: dict[str, Any]) -> PipelineStore:
    return PipelineStore.of_app(checked.app, project["id"])


def call(store: PipelineStore, name: str, **arguments: object) -> Any:
    return json.loads(run_pipeline_tool(store, name, json.dumps(arguments)))


def timeless(answer: dict[str, Any]) -> dict[str, Any]:
    return {**answer, "latency_s": 0, "line": {**answer["line"], "latency_s": 0}}


def test_every_tool_is_an_openai_function_with_all_its_arguments_required() -> None:
    names = [tool["function"]["name"] for tool in PIPELINE_TOOLS]
    assert names == [
        "list_drawings",
        "ask_drawings",
        "get_takeoff",
        "list_conflicts",
        "list_issues",
        "run_checks",
        "get_plan_geometry",
    ]
    for tool in PIPELINE_TOOLS:
        function = tool["function"]
        assert tool["type"] == "function" and function["description"]
        parameters = function["parameters"]
        assert parameters["type"] == "object"
        assert parameters["required"] == list(parameters["properties"])
        json.dumps(tool)  # plain JSON


def test_list_drawings_names_each_drawing_of_the_project(
    store: PipelineStore, project: dict[str, Any]
) -> None:
    found = call(store, "list_drawings")
    assert [d["drawing_id"] for d in found] == [d["drawing_id"] for d in project["drawings"]]
    assert [d["name"] for d in found] == [d["file"] for d in project["drawings"]]
    assert all(isinstance(d["pages"], int) for d in found)  # a model file has 0 pages
    assert {"kind", "route", "state", "triage"} <= set(found[0])


def test_ask_drawings_is_the_project_ask_route(
    checked: TestClient, store: PipelineStore, project: dict[str, Any]
) -> None:
    found = call(store, "ask_drawings", question=DOORS)
    route = checked.post(f"/api/projects/{project['id']}/ask", json={"question": DOORS}).json()
    assert [timeless(part["answer"]) for part in found["parts"]] == [
        timeless(part["answer"]) for part in route["parts"]
    ]
    assert {k: found[k] for k in ("total", "total_note", "why_no_total", "refused_note")} == {
        k: route[k] for k in ("total", "total_note", "why_no_total", "refused_note")
    }
    assert found["why_no_total"] is not None  # the sample's drawings may show the same flat


def test_get_takeoff_is_the_drawings_takeoff_in_the_project(
    checked: TestClient, store: PipelineStore, project: dict[str, Any]
) -> None:
    drawing_id = project["drawings"][0]["drawing_id"]
    found = call(store, "get_takeoff", drawing_id=drawing_id)
    route = checked.get(f"/api/drawings/{drawing_id}/takeoff?project={project['id']}").json()
    assert found == route and found["quantities"]


def test_conflicts_and_issues_are_the_routes_lists(
    checked: TestClient, store: PipelineStore, project: dict[str, Any]
) -> None:
    conflicts = call(store, "list_conflicts")
    review = checked.get(f"/api/projects/{project['id']}/review").json()
    assert conflicts == review["conflicts"]
    issues = call(store, "list_issues")
    route = checked.get(f"/api/projects/{project['id']}/issues").json()
    assert issues == route["issues"] and issues


def test_run_checks_is_the_project_checks_route_failures_first(
    checked: TestClient, store: PipelineStore, project: dict[str, Any]
) -> None:
    """R4-I5: the route's results, the fails and cannot-tells listed with their drawing and rule,
    the passes only counted per rule (the chat lists the failing rooms, not the passing ones)."""
    found = call(store, "run_checks", pack="test")
    route = checked.get(f"/api/projects/{project['id']}/checks", params={"pack": "test"}).json()
    assert {k: found[k] for k in ("project_id", "pack", "note", "status")} == {
        k: route[k] for k in ("project_id", "pack", "note", "status")
    }
    results = [
        (d["drawing_id"], r["rule_id"], x)
        for d in route["drawings"] for r in d["rules"] for x in r["results"]
    ]  # fmt: skip
    for status, listed in (("fail", "failures"), ("cannot_tell", "cannot_tell")):
        assert [x["id"] for x in found[listed]] == [x["id"] for _, _, x in results
                                                    if x["status"] == status]  # fmt: skip
    rules = [(d["drawing_id"], r["rule_id"], r["status"]) for d in route["drawings"]
             for r in d["rules"]]  # fmt: skip
    assert [(r["drawing_id"], r["rule_id"], r["status"]) for r in found["rules"]] == rules
    passes = sum(r["counts"].get("pass", 0) for r in found["rules"])
    assert passes == sum(x["status"] == "pass" for _, _, x in results) and found["rules"]
    assert list(found)[4:6] == ["failures", "cannot_tell"]  # before the per-rule list


@pytest.fixture
def sample(client: TestClient) -> PipelineStore:
    """The sample project with the app's own rule packs (ch-zh, fi)."""
    project = client.get(client.post("/api/projects/sample").json()["url"]).json()
    return PipelineStore.of_app(client.app, project["id"])


@pytest.mark.parametrize("times", [1, 8])
def test_run_checks_keeps_every_failure_when_the_chat_cuts_a_long_result(
    sample: PipelineStore, monkeypatch: pytest.MonkeyPatch, times: int
) -> None:
    """R4-I5 (Tudor's QA round 4): "Which rooms fail the Zürich building rules?" on the sample
    could not name Zimmer 1.05 on flat-b (8.06 m²): run_checks gave every drawing's every result,
    the loop halves the longest list to TOOL_CHARS, and the drawings list was cut to flat-a (whose
    own Zimmer 1.05 passes). times=8: the passing drawings eight times over, ahead of flat-b,
    so the chat still cuts the result, but not the failure."""
    real = pipeline_tools.checks_of

    def padded(project_id: str, pack: RulePack, ingest: Any) -> ProjectChecks:
        found = real(project_id, pack, ingest)
        failing = [d for d in found.drawings if d.status == "fail"]
        rest = [d for d in found.drawings if d.status != "fail"]
        return found.model_copy(update={"drawings": rest * times + failing})

    monkeypatch.setattr(pipeline_tools, "checks_of", padded)
    text = _for_model(call(sample, "run_checks", pack="ch-zh"))
    assert ("_more" in text) == (times > 1), text  # x1 now fits; x8 is still cut
    read = json.loads(text)  # cut by lists, not as text
    failures = [(x["file"], x["rule_id"], x["subject"]["label"]) for x in read["failures"]]
    assert failures == [("plans/flat-b.pdf", "ch-zh-room-area", "Zimmer 1.05")], text
    assert read["failures"][0]["value"] == pytest.approx(8.06, abs=0.01)


def drawing(**fields: object) -> Drawing:
    return Drawing.model_validate(
        {
            "file": "a.pdf",
            "pages": ({"page": 1, "width": 100, "height": 100, "unit": "pt"},),
            "scale": {"status": "estimated", "m_per_unit": 0.05, "text": "1:100"},
            "plans": ({"id": "p1", "page": 1, "box": BOX, "storey": "0"},),
            **fields,
        }
    )


def wall(n: int) -> dict[str, object]:
    return {"id": f"w{n}", "class": "wall", "page": 1, "box": BOX, "attrs": {"length_m": 3.5}}


def test_walls_of_a_building_model_are_sure_with_their_length() -> None:
    found = geometry_of(drawing(elements=(wall(1),)), "bim", "d" * 16, 1)
    assert found["walls"] == [
        {"id": "w1", "class": "wall", "box": list(BOX), "polygon": None, "length_m": 3.5}
    ]
    assert found["walls_sure"] is True and "walls" not in found["reasons"]
    assert found["scale"]["m_per_unit"] == 0.05 and found["frame"][0]["box"] == list(BOX)


def test_cut_solids_of_a_pdf_are_walls_that_are_not_sure() -> None:
    found = geometry_of(drawing(elements=(wall(1),)), "vector", "d" * 16, 1)
    assert found["walls"] and found["walls_sure"] is False
    assert "cut solids" in found["reasons"]["walls"]


def test_a_reader_that_does_not_look_for_walls_gives_null_and_why() -> None:
    sheet = drawing(read=("door", "window", "room"))
    found = geometry_of(sheet, "raster", "d" * 16, 1)
    assert found["walls"] is None and found["walls_sure"] is False
    assert "does not look for walls" in found["reasons"]["walls"]
    assert found["rooms"] == [] and found["reasons"]["rooms"] == "none were found on this page"


def test_get_plan_geometry_on_a_real_drawing(store: PipelineStore, project: dict[str, Any]) -> None:
    drawing_id = project["drawings"][0]["drawing_id"]
    found = call(store, "get_plan_geometry", drawing_id=drawing_id, page=1)
    assert found["drawing_id"] == drawing_id and found["page"] == 1
    assert found["source"]["route"] == project["drawings"][0]["route"]


@pytest.mark.parametrize(
    ("name", "arguments", "says"),
    [
        ("nope", "{}", "unknown tool"),
        ("list_drawings", "{not json", "not valid JSON"),
        ("list_drawings", "[1]", "must be a JSON object"),
        ("list_drawings", '{"project_id": "0123456789ab"}', "project_id: Extra inputs"),
        ("get_takeoff", "{}", "drawing_id: Field required"),
        ("get_takeoff", '{"drawing_id": "short"}', "drawing_id: String should match"),
        ("get_takeoff", '{"drawing_id": "' + "f" * 16 + '", "x": 1}', "x: Extra inputs"),
        ("ask_drawings", '{"question": ""}', "question: String should have at least 1"),
        ("ask_drawings", '{"question": "' + "x" * 501 + '"}', "at most 500"),
        ("ask_drawings", '{"question": ["x"]}', "question: Input should be a valid string"),
        ("get_plan_geometry", '{"drawing_id": "' + "f" * 16 + '", "page": "two"}', "page:"),
        ("get_plan_geometry", '{"drawing_id": "' + "f" * 16 + '", "page": 0}', "page:"),
        ("run_checks", '{"pack": "x"}', "x"),  # no such pack
        ("run_checks", {"pack": ""}, "pack:"),  # an already decoded object
        ("run_checks", [1], "must be a JSON object"),
    ],
)
def test_a_bad_call_is_an_error_not_an_exception(
    store: PipelineStore, name: str, arguments: Any, says: str
) -> None:
    found = json.loads(run_pipeline_tool(store, name, arguments))
    assert set(found) == {"error"} and says in found["error"]


def test_arguments_may_be_json_text_or_a_decoded_object(store: PipelineStore) -> None:
    text = run_pipeline_tool(store, "ask_drawings", json.dumps({"question": DOORS}))
    decoded = run_pipeline_tool(store, "ask_drawings", {"question": DOORS})
    assert json.loads(text).keys() == json.loads(decoded).keys() and "error" not in json.loads(text)
    assert json.loads(run_pipeline_tool(store, "list_drawings", ""))  # no arguments at all


def test_the_model_is_never_asked_for_a_project(store: PipelineStore) -> None:
    for tool in PIPELINE_TOOLS:
        assert "project_id" not in tool["function"]["parameters"]["properties"]
        assert tool["function"]["parameters"]["additionalProperties"] is False
    other = PipelineStore(**{**store.__dict__, "project_id": "0123456789ab"})
    assert "0123456789ab" in call(other, "list_drawings")["error"]  # no such project


def test_bad_calls_on_a_real_project(store: PipelineStore, project: dict[str, Any]) -> None:
    drawing_id = project["drawings"][0]["drawing_id"]
    assert "no drawing" in call(store, "get_takeoff", drawing_id="f" * 16)["error"]
    assert "no page 9" in call(store, "get_plan_geometry", drawing_id=drawing_id, page=9)["error"]
    assert "error" in call(store, "run_checks", pack="nope")


def test_a_project_that_is_not_done_is_an_error(
    store: PipelineStore, project: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    running = store.ingest.status(project["id"]).model_copy(update={"state": "running"})
    monkeypatch.setattr(store.ingest, "status", lambda project_id: running)
    for name, extra in (
        ("list_conflicts", {}),
        ("list_issues", {}),
        ("ask_drawings", {"question": DOORS}),
    ):
        found = call(store, name, **extra)
        assert "running" in found["error"]


def test_a_bug_in_a_tool_is_logged_with_its_traceback_and_the_reply_stays_plain(
    store: PipelineStore, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(store: PipelineStore, arguments: object) -> None:
        raise RuntimeError("secret internals")

    monkeypatch.setitem(_RUNNERS, "list_drawings", broken)
    with caplog.at_level(logging.ERROR, logger="app.adapters.pipeline_tools"):
        reply = run_pipeline_tool(store, "list_drawings", "{}")
    assert json.loads(reply) == {"error": "list_drawings failed (RuntimeError)"}
    (record,) = caplog.records
    assert "pipeline tool list_drawings failed" in record.getMessage()
    assert record.exc_info is not None and "secret internals" in str(record.exc_info[1])


def test_a_refused_call_is_not_logged_as_a_bug(
    store: PipelineStore, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.adapters.pipeline_tools"):
        call(store, "get_takeoff", drawing_id="f" * 16)  # no such drawing
        call(store, "nope")
    assert caplog.records == []


WALL = (191, 191, 191)


def walled_sheet() -> bytes:
    """The synthetic swiss plan (1:100: 1 m = 28.35 pt) with two wall fills, one with a hole, and
    a thin grey fill that is not a wall."""
    sheet = swiss_sheet()
    sheet.path(rect(50, 20, 450, 30), stroke=(0, 0, 0), width=0.99, fill=WALL)  # 14.11 x 0.35 m
    sheet.path(
        rect(50, 300, 150, 320), rect(70, 305, 90, 315), stroke=(0, 0, 0), width=0.99, fill=WALL
    )
    sheet.path(rect(200, 300, 220, 320), stroke=(0, 0, 0), width=0.5, fill=WALL)  # not a wall
    return sheet.pdf()


def test_wall_fills_of_a_swiss_pdf_are_walls_drawn_with_their_area() -> None:
    page = read_page(walled_sheet())
    found = wall_fills(page, 25.4 / 72 / 1000 * 100)
    assert len(found) == 2  # the 0.5-wide grey fill is not one
    by_area = sorted(found, key=lambda f: f.area_m2 or 0)
    assert by_area[1].holes == () and len(by_area[0].holes) == 1  # the holed one is smaller
    expected = (400 * 10 + 100 * 20 - 20 * 10) * (25.4 / 72 / 1000 * 100) ** 2
    assert sum(f.area_m2 or 0 for f in found) == pytest.approx(expected, rel=0.05)
    assert all(0 <= x <= 1 and 0 <= y <= 1 for f in found for x, y in f.polygon)


def test_get_plan_geometry_gives_walls_drawn_of_a_swiss_pdf(checked: TestClient) -> None:
    pid = checked.post("/api/projects", params={"name": "w.pdf"}, content=walled_sheet()).json()
    status = checked.get(f"/api/projects/{pid['id']}").json()
    drawing_id = status["drawings"][0]["drawing_id"]
    found = call(
        PipelineStore.of_app(checked.app, pid["id"]),
        "get_plan_geometry",
        drawing_id=drawing_id,
        page=1,
    )
    assert len(found["walls_drawn"]) == 2 and found["walls_drawn_source"] == "vector fills"
    assert found["walls_sure"] is False and found["walls"] is None  # the reader gives no walls
    assert found["walls_drawn_area_m2"] == pytest.approx(
        (400 * 10 + 100 * 20 - 20 * 10) * (25.4 / 72 / 1000 * 100) ** 2, rel=0.05
    )


def test_a_source_without_wall_fills_has_walls_drawn_null_and_why() -> None:
    found = geometry_of(drawing(), "raster", "d" * 16, 1)
    assert found["walls_drawn"] is None and found["walls_drawn_area_m2"] is None
    assert "swiss-style vector PDF" in found["reasons"]["walls_drawn"]


@pytest.mark.skipif(not FLOOR.exists(), reason="the dataset is not on this machine")
def test_floor9178_walls_are_about_the_dxf_wall_layer() -> None:
    page = read_page(FLOOR.read_bytes())
    scale, _ = read_scale(page)
    found = wall_fills(page, scale.m_per_unit)
    assert len(found) == 9
    assert sum(f.area_m2 or 0 for f in found) == pytest.approx(22.4, rel=0.06)  # DXF: 22.4 m²
