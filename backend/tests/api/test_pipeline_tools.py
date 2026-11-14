"""PIPELINE_TOOLS for the agent chat (board #222): each tool gives what its HTTP route gives, and
a bad call is {"error": ...}, never an exception."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapters.pipeline_tools import (
    PIPELINE_TOOLS,
    PipelineStore,
    geometry_of,
    run_pipeline_tool,
)
from app.composition import build_ingest
from app.core.drawing.model import Drawing
from app.main import create_app
from app.settings import Settings

RULES = Path(__file__).parents[1] / "fixtures" / "rules"
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
def store(checked: TestClient) -> PipelineStore:
    return PipelineStore.of_app(checked.app)


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
    found = call(store, "list_drawings", project_id=project["id"])
    assert [d["drawing_id"] for d in found] == [d["drawing_id"] for d in project["drawings"]]
    assert [d["name"] for d in found] == [d["file"] for d in project["drawings"]]
    assert all(isinstance(d["pages"], int) for d in found)  # a model file has 0 pages
    assert {"kind", "route", "state", "triage"} <= set(found[0])


def test_ask_drawings_is_the_project_ask_route(
    checked: TestClient, store: PipelineStore, project: dict[str, Any]
) -> None:
    found = call(store, "ask_drawings", project_id=project["id"], question=DOORS)
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
    found = call(store, "get_takeoff", project_id=project["id"], drawing_id=drawing_id)
    route = checked.get(f"/api/drawings/{drawing_id}/takeoff?project={project['id']}").json()
    assert found == route and found["quantities"]


def test_conflicts_and_issues_are_the_routes_lists(
    checked: TestClient, store: PipelineStore, project: dict[str, Any]
) -> None:
    conflicts = call(store, "list_conflicts", project_id=project["id"])
    review = checked.get(f"/api/projects/{project['id']}/review").json()
    assert conflicts == review["conflicts"]
    issues = call(store, "list_issues", project_id=project["id"])
    route = checked.get(f"/api/projects/{project['id']}/issues").json()
    assert issues == route["issues"] and issues


def test_run_checks_is_the_project_checks_route(
    checked: TestClient, store: PipelineStore, project: dict[str, Any]
) -> None:
    found = call(store, "run_checks", project_id=project["id"], pack="test")
    route = checked.get(f"/api/projects/{project['id']}/checks", params={"pack": "test"}).json()
    assert found == route and found["drawings"]


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
    found = call(
        store, "get_plan_geometry", project_id=project["id"], drawing_id=drawing_id, page=1
    )
    assert found["drawing_id"] == drawing_id and found["page"] == 1
    assert found["source"]["route"] == project["drawings"][0]["route"]


@pytest.mark.parametrize(
    ("name", "arguments", "says"),
    [
        ("nope", "{}", "unknown tool"),
        ("list_drawings", "{not json", "not valid JSON"),
        ("list_drawings", "[1]", "must be a JSON object"),
        ("list_drawings", "{}", "missing argument project_id"),
        ("list_drawings", '{"project_id": "0123456789ab", "extra": "x"}', "unknown argument"),
        ("list_drawings", '{"project_id": ""}', "non-empty string"),
        ("list_drawings", '{"project_id": ["x"]}', "non-empty string"),
        ("list_drawings", '{"project_id": "0123456789ab"}', "0123456789ab"),  # no such project
        ("run_checks", '{"project_id": "0123456789ab", "pack": "x"}', ""),
    ],
)
def test_a_bad_call_is_an_error_not_an_exception(
    store: PipelineStore, name: str, arguments: str, says: str
) -> None:
    found = json.loads(run_pipeline_tool(store, name, arguments))
    assert set(found) == {"error"} and says in found["error"]


def test_bad_calls_on_a_real_project(store: PipelineStore, project: dict[str, Any]) -> None:
    pid = project["id"]
    drawing_id = project["drawings"][0]["drawing_id"]
    assert "no drawing" in call(store, "get_takeoff", project_id=pid, drawing_id="f" * 16)["error"]
    assert (
        "no page 9"
        in call(store, "get_plan_geometry", project_id=pid, drawing_id=drawing_id, page="9")[
            "error"
        ]
    )
    assert (
        "whole number"
        in call(store, "get_plan_geometry", project_id=pid, drawing_id=drawing_id, page="two")[
            "error"
        ]
    )
    assert "error" in call(store, "run_checks", project_id=pid, pack="nope")
    assert "error" in call(store, "ask_drawings", project_id=pid, question="x" * 5000)


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
        found = call(store, name, project_id=project["id"], **extra)
        assert "running" in found["error"]
