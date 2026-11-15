"""SHEET_KIND=carbon through the settings, composition, ingest and API (.agents/exp/vlm-kind.md):
replies replayed from the cache folder as the scoring run writes them, the network shut."""

import hashlib
import io
import json
import urllib.request
from pathlib import Path
from typing import Any, cast

import pytest
from conftest import plan_png
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from pydantic import SecretStr
from test_api_triage import project, read_as_plan
from test_sheet_kind import PIPING, PLAN, STRUCTURAL_UNSURE, reply
from test_vector_pdf import swiss_sheet

from app.adapters.extraction_v1 import ExtractionV1Writer
from app.adapters.pipeline_tools import PipelineStore, run_pipeline_tool
from app.adapters.triage.sheet_kind import MODEL, PROMPT_SHA
from app.composition import _triage, build_ingest, uses_keys  # pyright: ignore[reportPrivateUsage]
from app.core.drawing.model import Drawing, Element, Room, Scale
from app.core.pipeline.model import Page
from app.main import create_app
from app.settings import Settings

DOORS = "How many doors are there?"
KITCHENS = "How many kitchens are there?"
# What /ask says to DOORS on a sheet the step flagged as a piping plan (R3-C3)
NOT_COUNTED = (
    "The sheet may not be a floor plan: it looks like a piping, plumbing, ventilation or "
    "electrical plan, so its symbols are not counted as doors, windows or fixtures. If it is a "
    'floor plan, use "Read it as a floor plan" on its file.'
)
ROOF = "What colour is the roof?"


def sheet(shade: int) -> bytes:
    """A drawing image unlike the others (each file is its own content, its own cache entry)."""
    image = Image.open(io.BytesIO(plan_png())).convert("RGB")
    ImageDraw.Draw(image).rectangle((0, 0, 9, 9), fill=(shade, shade, shade))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


PIPING_PNG, DOUBT_PNG, PLAN_PNG, MISS_PNG = sheet(10), sheet(20), sheet(30), sheet(40)
NAMES = {"piping.png": PIPING_PNG, "doubt.png": DOUBT_PNG, "plan.png": PLAN_PNG}


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every request that would leave the process; each one fails."""
    sent: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> Any:
        sent.append(request.full_url)
        raise OSError("no network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return sent


def seeded(settings: Settings, tmp_path: Path, **more: Any) -> TestClient:
    """SHEET_KIND=carbon with the replies of PIPING_PNG, DOUBT_PNG and PLAN_PNG in its cache, and
    a raster reader that finds one door and one kitchen on every file of NAMES (so an answer has
    a value)."""
    cache = tmp_path / "sheet-kind"
    cache.mkdir()
    for data, found in ((PIPING_PNG, PIPING), (DOUBT_PNG, STRUCTURAL_UNSURE), (PLAN_PNG, PLAN)):
        name = f"sheetkind-{hashlib.sha256(data).hexdigest()}-{PROMPT_SHA[:12]}-{MODEL}.json"
        (cache / name).write_text(json.dumps(reply(found)))
    arm = tmp_path / "arm"
    door = Element(id="d1", class_="door", page=1, box=(0.1, 0.1, 0.2, 0.3))
    kitchen = Room(id="r1", type="kitchen", page=1, box=(0.3, 0.1, 0.6, 0.6))
    writer = ExtractionV1Writer(arm, dict.fromkeys(NAMES, "dev"))
    for path in NAMES:
        page = Page(page=1, width=800, height=400, unit="px")
        writer.write(Drawing(file=path, pages=(page,), scale=Scale(status="no_scale"),
                             rooms=(kitchen,), elements=(door,),
                             read=("door", "room")))  # fmt: skip
    changed = settings.model_copy(
        update={
            "sheet_kind": "carbon",
            "sheet_kind_cache_dir": cache,
            "gemini_api_key": SecretStr("test-key-not-real"),
            "extractor_raster": "composite",
            "raster_components": f"elements=dir:{arm},rooms=dir:{arm},plans=dir:{arm}",
            **more,
        }
    )
    ingest = build_ingest(changed, changed.projects_dir, background=False)
    return TestClient(create_app(changed, ingest))


def files_of(found: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {file["path"]: file for file in found["files"]}


def ask(client: TestClient, found: dict[str, Any], path: str, question: str) -> dict[str, Any]:
    drawing_id = files_of(found)[path]["drawing_id"]
    body = {"drawing_id": drawing_id, "question": question, "project_id": found["id"]}
    answer = client.post("/api/ask", json=body)
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_an_mep_plan_is_set_aside_by_name_and_comes_back_when_a_person_reads_it(
    settings: Settings, tmp_path: Path, network: list[str]
) -> None:
    client = seeded(settings, tmp_path)
    found = project(client, {"piping.png": PIPING_PNG, "plan.pdf": swiss_sheet().pdf()})
    files = files_of(found)
    piping = files["piping.png"]
    assert piping["state"] == "set_aside"
    assert piping["reason"] == (
        "not a floor plan: a piping, plumbing, ventilation or electrical plan (PIPING PLAN, M-101A)"
    )
    assert piping["triage"]["class"] == "other_drawing"
    assert piping["triage"]["sheet"]["decision"] == "set_aside"
    assert piping["triage"]["sheet"]["model"] == "gemini-4-carbon"
    assert piping["triage"]["note"].startswith("not described: no description model is set up")
    assert "triage" not in files["plan.pdf"]  # a vector PDF is never asked
    assert (
        found["readers"]["triage"] == "classifier=off, sheet_kind=carbon, describer=off, judge=off"
    )
    assert network == []  # replayed from the cache
    issues = client.get(f"/api/projects/{found['id']}/issues").json()["issues"]
    (issue,) = [issue for issue in issues if issue["file"] == "piping.png"]
    assert issue["why"].startswith(
        "Not a floor plan (a piping, plumbing, ventilation or electrical plan (PIPING PLAN, "
        "M-101A))."
    )
    assert read_as_plan(client, found, "piping.png").status_code == 202
    found = client.get(f"/api/projects/{found['id']}").json()
    assert files_of(found)["piping.png"]["drawing_id"] is not None
    answer = ask(client, found, "piping.png", DOORS)
    assert answer["answer"] == 1
    assert "may not be a floor plan" not in (answer["explanation"] or "")


def test_a_doubtful_sheet_is_read_and_each_answer_with_a_value_says_so(
    settings: Settings, tmp_path: Path, network: list[str]
) -> None:
    client = seeded(settings, tmp_path)
    found = project(client, {"doubt.png": DOUBT_PNG, "plan.png": PLAN_PNG})
    files = files_of(found)
    line = (
        "the sheet may not be a floor plan: it looks like a structural plan (foundation, slab, "
        "framing or reinforcement)"
    )
    assert files["doubt.png"]["state"] == "flagged" and line in files["doubt.png"]["reason"]
    assert files["doubt.png"]["triage"]["sheet"]["decision"] == "doubt"
    doors = ask(client, found, "doubt.png", DOORS)["refusal"]["text"]  # R3-C3
    assert doors.startswith(f"T{line[1:]}, so its symbols are not counted")
    answer = ask(client, found, "doubt.png", KITCHENS)
    assert answer["answer"] == 1
    assert answer["explanation"] == f"read from a page flagged at upload: {line}"
    assert answer["line"]["explanation"] == answer["explanation"]
    assert ask(client, found, "doubt.png", ROOF)["refusal"] is not None  # no value: no line
    assert line not in (ask(client, found, "doubt.png", ROOF)["explanation"] or "")
    plan = ask(client, found, "plan.png", DOORS)
    assert files["plan.png"]["triage"]["sheet"]["decision"] == "read"
    assert "may not be a floor plan" not in (plan["explanation"] or "")
    assert network == []


def test_a_failed_call_reads_the_file_as_today_and_says_why(
    settings: Settings, tmp_path: Path, network: list[str]
) -> None:
    client = seeded(settings, tmp_path)
    found = project(client, {"miss.png": MISS_PNG})
    (file,) = found["files"]
    assert "triage" not in file
    assert file["state"] in ("ready", "flagged")
    trace = client.get(f"/api/projects/{found['id']}/files/{file['id']}/trace").json()
    (identify,) = [stage for stage in trace["stages"] if stage["stage"] == "identify"]
    assert (
        "triage not available: the sheet-kind model could not answer: no answer: OSError"
        in (identify["did"])
    )
    assert len(network) == 1


def test_off_by_default_changes_nothing_and_on_counts_as_using_keys(tmp_path: Path) -> None:
    off = Settings(projects_dir=tmp_path / "projects")
    assert off.sheet_kind == "off" and _triage(off) is None and not uses_keys(off)
    rules = off.model_copy(update={"triage_classifier": "rules"})
    found = _triage(rules)
    assert found is not None
    assert found.name == "classifier=rules, describer=off, judge=off"  # the same as before
    on = off.model_copy(
        update={"sheet_kind": "carbon", "gemini_api_key": SecretStr("test-key-not-real")}
    )
    assert uses_keys(on)
    described = on.model_copy(update={"triage_describer": "gemini"})
    found = _triage(described)
    assert found is not None and found.describer is not None  # triage is on without a classifier


def test_warn_only_reads_the_piping_plan_and_its_answers_name_the_kind(
    settings: Settings, tmp_path: Path, network: list[str]
) -> None:
    """SHEET_KIND_SET_ASIDE=false (Bogdan, 2026-11-14): the sheet the step would set aside is
    read, keeps its sheet record, and every answer with a value says what it looks like."""
    assert Settings(projects_dir=tmp_path / "default").sheet_kind_set_aside is True
    client = seeded(settings, tmp_path, sheet_kind_set_aside=False)
    found = project(client, {"piping.png": PIPING_PNG})
    (piping,) = found["files"]
    assert piping["state"] == "flagged" and piping["drawing_id"] is not None
    sheet = piping["triage"]["sheet"]
    assert (piping["triage"]["class"], sheet["decision"], sheet["kind"]) == (
        "floor_plan",
        "doubt",
        "mep_plan",
    )
    assert (sheet["title"], sheet["sheet_number"]) == ("PIPING PLAN", "M-101A")
    doors = ask(client, found, "piping.png", DOORS)
    assert doors["answer"] is None and doors["refusal"]["text"] == NOT_COUNTED  # R3-C3
    answer = ask(client, found, "piping.png", KITCHENS)
    assert answer["answer"] == 1
    assert answer["explanation"] == (
        "read from a page flagged at upload: the sheet may not be a floor plan: it looks like a "
        "piping, plumbing, ventilation or electrical plan"
    )
    assert network == []


CHECK = (
    Path(__file__).parents[3]
    / "eval/results/check/check-C1-T1-recall96-rt-full-small-medium20.json"
)


def test_a_warn_only_non_plan_sheet_is_flagged_so_its_answers_ask_and_are_low(
    settings: Settings, tmp_path: Path, network: list[str]
) -> None:
    """Orchestrator, 2026-11-14: a sheet the step doubts and calls a non-plan kind is flagged at
    upload (the path a Carbon-alone read takes), so under the demo's check policy its answers
    ask and are Low; a plain plan's answers are as they are with the step off."""
    client = seeded(settings, tmp_path, sheet_kind_set_aside=False, check_policy=str(CHECK))
    found = project(client, {"piping.png": PIPING_PNG, "plan.png": PLAN_PNG})
    files = files_of(found)
    flag = (
        "the sheet may not be a floor plan: it looks like a piping, plumbing, ventilation or "
        "electrical plan"
    )
    assert files["piping.png"]["state"] == "flagged" and flag in files["piping.png"]["reason"]
    assert ask(client, found, "piping.png", DOORS)["refusal"]["text"] == NOT_COUNTED  # R3-C3
    piping = ask(client, found, "piping.png", KITCHENS)
    assert piping["answer"] == 1
    assert piping["check"] is not None and piping["level"]["level"] == "low"
    assert piping["level"]["basis"] == "page"
    assert files["plan.png"]["state"] == "ready"
    (tmp_path / "off").mkdir()
    off = seeded(settings, tmp_path / "off", check_policy=str(CHECK), sheet_kind="off",
                 projects_dir=tmp_path / "off" / "projects")  # fmt: skip
    alone_found = project(off, {"plan.png": PLAN_PNG})
    assert files_of(alone_found)["plan.png"]["state"] == "ready"
    plan = ask(client, found, "plan.png", DOORS)
    alone = ask(off, alone_found, "plan.png", DOORS)
    for key in ("answer", "check", "level", "explanation", "sure"):
        assert plan.get(key) == alone.get(key), key
    assert network == []


def like(client: TestClient, **changes: Any) -> TestClient:
    """Another app on the same projects folder (the same ingest outcome cache) and readers."""
    app = cast(FastAPI, client.app)
    settings = cast(Settings, app.state.settings).model_copy(update=changes)
    ingest = build_ingest(settings, settings.projects_dir, background=False)
    return TestClient(create_app(settings, ingest))


def test_the_flag_follows_the_projects_triage_when_the_reading_is_reused(
    settings: Settings, tmp_path: Path, network: list[str]
) -> None:
    """codecheck's M1 on #265: the reading is cached by content, the triage is the project's. A
    sheet read first with SHEET_KIND off and then uploaded with warn-only on reuses the reading
    and is still flagged; switched off again, a new upload is not."""
    on = seeded(settings, tmp_path, sheet_kind_set_aside=False, check_policy=str(CHECK))
    off = like(on, sheet_kind="off")
    assert files_of(project(off, {"piping.png": PIPING_PNG}))["piping.png"]["state"] == "ready"
    found = project(on, {"piping.png": PIPING_PNG})
    piping = files_of(found)["piping.png"]
    assert piping["reused"] is True and piping["state"] == "flagged"
    flag = (
        "the sheet may not be a floor plan: it looks like a piping, plumbing, ventilation or "
        "electrical plan"
    )
    assert piping["reason"].startswith(f"{flag}; ")
    answer = ask(on, found, "piping.png", KITCHENS)
    assert answer["explanation"] == f"read from a page flagged at upload: {flag}"
    assert answer["level"]["basis"] == "page" and answer["check"] is not None
    issues = on.get(f"/api/projects/{found['id']}/issues").json()["issues"]
    assert any(issue["kind"] == "reading_flag" and flag in issue["reason"] for issue in issues)
    again = project(off, {"piping.png": PIPING_PNG})
    assert files_of(again)["piping.png"]["state"] == "ready"
    assert ask(off, again, "piping.png", DOORS)["explanation"] is None
    assert network == []


def test_a_person_reading_a_flagged_doubt_as_a_plan_clears_the_flag(
    settings: Settings, tmp_path: Path, network: list[str]
) -> None:
    """codecheck's S2 on #265: "read as a floor plan" on a warn-only doubt sheet is accepted (was
    422) and the person's call wins: the file is ready and its answers carry no flag."""
    client = seeded(settings, tmp_path, sheet_kind_set_aside=False, check_policy=str(CHECK))
    found = project(client, {"piping.png": PIPING_PNG})
    assert files_of(found)["piping.png"]["state"] == "flagged"
    assert read_as_plan(client, found, "piping.png").status_code == 202
    found = client.get(f"/api/projects/{found['id']}").json()
    piping = files_of(found)["piping.png"]
    assert piping["state"] == "ready" and "may not be a floor plan" not in piping["reason"]
    assert piping["triage"]["read_as_plan"] is not None
    answer = ask(client, found, "piping.png", DOORS)
    assert answer["answer"] == 1 and answer["explanation"] is None
    assert answer["level"]["basis"] != "page"
    assert read_as_plan(client, found, "piping.png").status_code == 409  # once
    assert network == []


def test_list_drawings_gives_the_chat_what_the_sheet_kind_step_called_each_sheet(
    settings: Settings, tmp_path: Path, network: list[str]
) -> None:
    """R3-G4 (Tudor's QA round 3): "What kind of drawing is this?" on T3, a piping plan the step
    flagged, was answered "a raster floor plan": list_drawings gave triage class floor_plan (a
    doubt is read) and the raster route, never the step's kind or the sheet's title. It now
    gives both, with the flag; a plain plan says it looks like one."""
    client = seeded(settings, tmp_path, sheet_kind_set_aside=False)
    found = project(client, {"piping.png": PIPING_PNG, "plan.png": PLAN_PNG})
    store = PipelineStore.of_app(client.app, found["id"])
    listed = {d["name"]: d for d in json.loads(run_pipeline_tool(store, "list_drawings", "{}"))}
    piping = listed["piping.png"]["triage"]["sheet"]
    assert piping == {
        "looks_like": "a piping, plumbing, ventilation or electrical plan",
        "decision": "doubt",
        "title": "PIPING PLAN",
        "sheet_number": "M-101A",
        "printed_scale": None,
        "seen": "a sheet",
        "flag": (
            "the sheet may not be a floor plan: it looks like a piping, plumbing, ventilation or "
            "electrical plan"
        ),
    }
    plan = listed["plan.png"]["triage"]["sheet"]
    assert plan["looks_like"] == "a floor plan" and plan["flag"] is None
    assert plan["printed_scale"] == "1:100" and plan["decision"] == "read"
    assert network == []
