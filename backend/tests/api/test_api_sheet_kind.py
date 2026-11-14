"""SHEET_KIND=carbon through the settings, composition, ingest and API (.agents/exp/vlm-kind.md):
replies replayed from the cache folder as the scoring run writes them, the network shut."""

import hashlib
import io
import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from conftest import plan_png
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from pydantic import SecretStr
from test_api_triage import project, read_as_plan
from test_sheet_kind import PIPING, PLAN, STRUCTURAL_UNSURE, reply
from test_vector_pdf import swiss_sheet

from app.adapters.extraction_v1 import ExtractionV1Writer
from app.adapters.triage.sheet_kind import MODEL, PROMPT_SHA
from app.composition import _triage, build_ingest, uses_keys  # pyright: ignore[reportPrivateUsage]
from app.core.drawing.model import Drawing, Element, Scale
from app.core.pipeline.model import Page
from app.main import create_app
from app.settings import Settings

DOORS = "How many doors are there?"
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
    a raster reader that finds one door on every file of NAMES (so an answer has a value)."""
    cache = tmp_path / "sheet-kind"
    cache.mkdir()
    for data, found in ((PIPING_PNG, PIPING), (DOUBT_PNG, STRUCTURAL_UNSURE), (PLAN_PNG, PLAN)):
        name = f"sheetkind-{hashlib.sha256(data).hexdigest()}-{PROMPT_SHA[:12]}-{MODEL}.json"
        (cache / name).write_text(json.dumps(reply(found)))
    arm = tmp_path / "arm"
    door = Element(id="d1", class_="door", page=1, box=(0.1, 0.1, 0.2, 0.3))
    writer = ExtractionV1Writer(arm, dict.fromkeys(NAMES, "dev"))
    for path in NAMES:
        page = Page(page=1, width=800, height=400, unit="px")
        writer.write(Drawing(file=path, pages=(page,), scale=Scale(status="no_scale"),
                             elements=(door,), read=("door",)))  # fmt: skip
    changed = settings.model_copy(
        update={
            "sheet_kind": "carbon",
            "sheet_kind_cache_dir": cache,
            "gemini_api_key": SecretStr("test-key-not-real"),
            "extractor_raster": "composite",
            "raster_components": f"elements=dir:{arm},plans=dir:{arm}",
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
    assert files["doubt.png"]["state"] in ("ready", "flagged")
    assert files["doubt.png"]["triage"]["sheet"]["decision"] == "doubt"
    answer = ask(client, found, "doubt.png", DOORS)
    assert answer["answer"] == 1
    line = (
        "This sheet may not be a floor plan: it looks like a structural plan (foundation, slab, "
        "framing or reinforcement)."
    )
    assert answer["explanation"].endswith(line)
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
    assert piping["state"] in ("ready", "flagged") and piping["drawing_id"] is not None
    sheet = piping["triage"]["sheet"]
    assert (piping["triage"]["class"], sheet["decision"], sheet["kind"]) == (
        "floor_plan",
        "doubt",
        "mep_plan",
    )
    assert (sheet["title"], sheet["sheet_number"]) == ("PIPING PLAN", "M-101A")
    answer = ask(client, found, "piping.png", DOORS)
    assert answer["answer"] == 1
    assert answer["explanation"].endswith(
        "This sheet may not be a floor plan: it looks like a piping, plumbing, ventilation or "
        "electrical plan."
    )
    assert network == []
