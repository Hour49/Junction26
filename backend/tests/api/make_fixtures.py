"""Writes tests/fixtures/api_v1/*.json, the examples docs/API.md quotes, from real responses of
the API on the synthetic sample archive (scripts/make_sample_archive.py), trimmed to a few rows.

    cd backend && uv run python tests/api/make_fixtures.py

tests/api/test_api_fixtures.py checks each file against its response model, and that API.md
quotes it as it is. Rerun this after a change to a response model, then update API.md's quotes
(`uv run python tests/api/make_fixtures.py --doc` rewrites them).

The output is the same on every run, so a diff is a change of shape or value: the project id,
times and durations are replaced by fixed stand-ins (`stable`), and rows are picked by key, not
by position (core's dict and list order follows the hash seed today). tests/api/
test_api_fixtures.py runs it twice under different hash seeds and compares.
"""

import hashlib
import io
import json
import os
import sys
import tempfile
import threading
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(BACKEND / "tests" / "api"),  # its conftest (the raster arm), before tests/conftest.py
    str(BACKEND),
    str(BACKEND / "tests"),
    str(BACKEND / "scripts"),
]

import test_pdf_tables as tables  # noqa: E402  # pyright: ignore[reportMissingImports]
from conftest import plan_png, raster_arm  # noqa: E402  # pyright: ignore[reportMissingImports]
from fastapi.testclient import TestClient  # noqa: E402
from make_sample_archive import build_archive  # noqa: E402  # pyright: ignore[reportMissingImports]
from pdf_sheets import SheetPdf  # noqa: E402  # pyright: ignore[reportMissingImports]
from test_vector_pdf import swiss_sheet  # noqa: E402  # pyright: ignore[reportMissingImports]

from app.composition import DECISIONS_SIGNAL, build_ingest  # noqa: E402
from app.core.pipeline.ports import DrawingFiles  # noqa: E402
from app.main import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402

# Stand-ins for what changes on every run
PROJECT_ID = "5e0c1a2b3d4f"
CREATED_AT = "2026-11-14T08:00:00+00:00"
EDITED_AT = "2026-11-14T08:05:00Z"
DURATIONS = {"ms": 12.5, "latency_s": 0.002}
FIXTURES = BACKEND / "tests" / "fixtures" / "api_v1"
DOC = BACKEND.parent / "docs" / "API.md"
MARKER = "<!-- fixture: "


@dataclass(frozen=True)
class Rated:
    """A stand-in for DECISIONS_CONFIDENCE (no network): 0.87 for every answer."""

    value: float | None = 0.87
    note: str = "decisions: example"


class ExampleConfidence:
    def __init__(self, files: DrawingFiles) -> None:
        self._files = files

    def probability(self, path: str, family: str, value: object) -> Rated:
        self._files.read(path)  # the sheet as the pipeline read it, as Decisions reads it
        return Rated()


def responses() -> dict[str, Any]:
    root = Path(tempfile.mkdtemp())
    settings = Settings(
        projects_dir=root / "projects",
        sample_archive=root / "sample.zip",
        credit_dataset=root / "dataset",  # none: the sample is synthetic, its credit null
        credit_photos=root / "photos",
    )
    settings.sample_archive.write_bytes(build_archive())
    ingest = build_ingest(settings, settings.projects_dir, background=False)
    client = TestClient(create_app(settings, ingest))
    found: dict[str, Any] = {"info": client.get("/api/info").json()}
    started = client.post("/api/projects/sample").json()
    found["project_started"] = started
    project = client.get(started["url"]).json()
    found["project"] = project
    found["project_list"] = client.get("/api/projects").json()
    files = {file["path"]: file for file in project["files"]}
    flat_a, flat_b = files["plans/flat-a.pdf"], files["plans/flat-b.pdf"]
    found["trace"] = client.get(f"{started['url']}/files/{flat_a['id']}/trace").json()
    found["drawing"] = client.get(f"/api/drawings/{flat_a['drawing_id']}").json()
    ask = {"drawing_id": flat_a["drawing_id"], "question": "How many doors are there?"}
    found["ask_request"] = ask
    found["answer"] = client.post("/api/ask", json=ask).json()
    refused = {"drawing_id": flat_a["drawing_id"], "question": "What colour is the roof?"}
    found["answer_refused"] = client.post("/api/ask", json=refused).json()
    area = "What is the net floor area of all indoor rooms in m²?"
    found["answer_area"] = client.post(
        "/api/ask", json={"drawing_id": flat_a["drawing_id"], "question": area}
    ).json()
    found["answer_confidence"] = rated(root / "raster", settings)
    storey = "How many doors are shown on the floor plan of 'Ground Floor'?"
    house = files["model/house.ifc"]
    found["answer_model"] = client.post(
        "/api/ask", json={"drawing_id": house["drawing_id"], "question": storey}
    ).json()
    found["takeoff"] = client.get(f"/api/drawings/{flat_b['drawing_id']}/takeoff").json()
    found["project_review"] = client.get(f"{started['url']}/review").json()
    found["review_requests"] = [
        {"quantity": "door", "action": "reject", "mark": "m2"},
        {"quantity": "door", "action": "restore", "mark": "m2"},
        {"quantity": "door", "action": "add", "page": 1, "box": [0.2, 0.5, 0.23, 0.53]},
        {"quantity": "door", "action": "settle", "value": 3},
        {"quantity": "door", "action": "reset"},
        {"action": "reset"},
    ]
    found["signoff_request"] = {"quantity": "door", "by": "Ana"}
    found["error"] = client.get("/api/drawings/0123456789abcdef").json()
    others = reviewed(client, flat_b["drawing_id"], found)
    found["answer_schedule"] = schedule_answer(client)
    others.append(set_aside(client, found))
    others += in_flight(root / "flight", settings, found)
    variable = {  # the synthetic PDFs' bytes vary with the hash seed (tests/pdf_sheets.py)
        found["answer_schedule"]["drawing_id"]: "5c4ed01e00000001",
        found["project_running"]["files"][0]["sha256"]: hashlib.sha256(b"plan.pdf").hexdigest(),
    }
    return stable(trimmed(found), [started["id"], *others], variable)


ROOM = "area:room|name=1.01"  # flat-b's conflict: printed label against the drawn outline


def ask_on(client: TestClient, drawing_id: str, question: str) -> dict[str, Any]:
    return client.post("/api/ask", json={"drawing_id": drawing_id, "question": question}).json()


def reviewed(client: TestClient, drawing_id: str, found: dict[str, Any]) -> list[str]:
    """flat-b through the review flow: its conflict answered, marks rejected and added, a value
    settled, the conflict signed off, then an edit of the signed quantity refused (409)."""
    question = "What is the area of room 1.01?"
    found["answer_conflict"] = ask_on(client, drawing_id, question)
    url = f"/api/drawings/{drawing_id}"
    for edit in (
        {"quantity": "door", "action": "reject", "mark": "m1"},
        {"quantity": "door", "action": "add", "page": 1, "box": [0.2, 0.5, 0.23, 0.53]},
        {"quantity": "window", "action": "settle", "value": 3},
    ):
        assert client.post(f"{url}/review", json=edit).status_code == 200
    signed = client.post(f"{url}/signoff", json={"quantity": ROOM, "by": "Ana"})
    assert signed.status_code == 200, signed.text
    found["takeoff_edited"] = client.get(f"{url}/takeoff").json()
    found["answer_signed"] = ask_on(client, drawing_id, question)
    refused = client.post(f"{url}/review", json={"quantity": ROOM, "action": "settle", "value": 1})
    assert refused.status_code == 409, refused.text
    found["error_not_allowed"] = refused.json()
    return []


def door_schedule_pdf() -> bytes:
    """A sheet that prints a door schedule (tests/test_pdf_tables.py's, with door numbers as
    real schedules write them)."""
    rows = (
        ("101.A", "3'-0\"", "7'-0\"", "WD-1", "A"),
        ("102.A", "3'-0\"", "7'-0\"", "WD-1", None),
        ("111.B", "2'-8\"", "7'-0\"", "AL-1", "A, B"),
    )
    sheet = SheetPdf()
    with_rows = tables.DOOR_ROWS
    tables.DOOR_ROWS = rows
    try:
        tables.door_schedule(sheet)
    finally:
        tables.DOOR_ROWS = with_rows
    return sheet.pdf()


def schedule_answer(client: TestClient) -> dict[str, Any]:
    """A cell read from a schedule: a string answer, its row as the proof."""
    upload = client.post("/api/projects", params={"name": "doors.pdf"}, content=door_schedule_pdf())
    drawing_id = client.get(upload.json()["url"]).json()["drawings"][0]["drawing_id"]
    return ask_on(client, drawing_id, "What are the width and height of door 111.B?")


def set_aside(client: TestClient, found: dict[str, Any]) -> str:
    """A zip whose one entry would be written outside the project: set aside at unpack."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(zipfile.ZipInfo("../outside.pdf", (2026, 11, 14, 0, 0, 0)), b"%PDF-1.7")
    upload = client.post("/api/projects", params={"name": "unsafe.zip"}, content=buffer.getvalue())
    found["trace_set_aside"] = client.get(f"{upload.json()['url']}/files/f1/trace").json()
    return upload.json()["id"]


def in_flight(root: Path, settings: Settings, found: dict[str, Any]) -> list[str]:
    """A project caught while it runs (held after unpacking, before its files are read), and the
    same project as a restarted server finds it: failed, its unread files set aside."""
    settings = settings.model_copy(update={"projects_dir": root / "projects"})
    ingest = build_ingest(settings, settings.projects_dir, background=True)
    reached, release = threading.Event(), threading.Event()
    readers = ingest._readers  # pyright: ignore[reportPrivateUsage]

    def held(project_id: str) -> Any:
        reached.set()
        release.wait(60)
        return readers(project_id)

    ingest._readers = held  # pyright: ignore[reportPrivateUsage]
    client = TestClient(create_app(settings, ingest))
    upload = client.post("/api/projects", params={"name": "plan.pdf"}, content=swiss_sheet().pdf())
    url = upload.json()["url"]
    assert reached.wait(60), "the run never reached its readers"
    found["project_running"] = client.get(url).json()
    restarted = TestClient(create_app(settings, build_ingest(settings, settings.projects_dir)))
    found["project_failed"] = restarted.get(url).json()
    release.set()
    ingest.close()
    return [upload.json()["id"]]


def rated(root: Path, settings: Settings) -> dict[str, Any]:
    """A door count on an image read on the raster route (a precomputed arm: the only route the
    confidence rates), with DECISIONS_CONFIDENCE's stand-in."""
    raster_arm(root / "arm", "plan.png")
    settings = settings.model_copy(
        update={
            "projects_dir": root / "projects",
            "extractor_raster": "composite",
            # relative, so the reader names (part of the drawing id) are the same on every run
            "raster_components": "elements=dir:arm,plans=dir:arm",
        }
    )
    here = Path.cwd()
    os.chdir(root)
    try:
        ingest = build_ingest(settings, settings.projects_dir, background=False)
        app = create_app(settings, ingest)
        app.state.answering = replace(
            app.state.answering, confidence=ExampleConfidence, signal=DECISIONS_SIGNAL
        )
        client = TestClient(app)
        upload = client.post("/api/projects", params={"name": "plan.png"}, content=plan_png())
        drawing_id = client.get(upload.json()["url"]).json()["drawings"][0]["drawing_id"]
        ask = {"drawing_id": drawing_id, "question": "How many doors are there?"}
        return client.post("/api/ask", json=ask).json()
    finally:
        os.chdir(here)


def stable(
    found: dict[str, Any], project_ids: list[str], variable: dict[str, str] | None = None
) -> dict[str, Any]:
    """The run's project ids, times, durations and the `variable` values replaced by fixed
    stand-ins, and each file's takeoff (key -> number) in key order."""
    text = json.dumps(_fixed(found))
    for value, stand_in in (variable or {}).items():
        text = text.replace(value, stand_in)
    for at, project_id in enumerate(project_ids):
        text = text.replace(project_id, f"{int(PROJECT_ID, 16) + at:012x}")
    return json.loads(text)


def _fixed(value: Any) -> Any:
    if isinstance(value, list):
        return [_fixed(item) for item in value]
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for key, item in value.items():
        if key in DURATIONS and isinstance(item, int | float):
            out[key] = DURATIONS[key]
        elif key == "created_at":
            out[key] = CREATED_AT
        elif key == "at" and isinstance(item, str):  # when an edit or sign-off was made
            out[key] = EDITED_AT
        elif key == "takeoff" and isinstance(item, dict) and "quantities" not in item:
            out[key] = dict(sorted(item.items()))
        else:
            out[key] = _fixed(item)
    return out


def trimmed(found: dict[str, Any]) -> dict[str, Any]:
    """A few rows of each list, so the doc stays readable; every field stays."""
    found["project"]["files"] = found["project"]["files"][:3]
    for answer in (
        found["answer"],
        found["answer_confidence"],
        found["answer_refused"],
        found["answer_area"],
    ):
        _marks(answer)
    found["answer_refused"]["refusal"]["can_answer"] = found["answer_refused"]["refusal"][
        "can_answer"
    ][:2]
    rows = found["takeoff"]["quantities"]
    conflicts = sorted((row for row in rows if row["conflict"]), key=lambda row: row["key"])
    keep = conflicts[:1] + [row for key in ("door", "area:room|indoor") for row in rows
                            if row["key"] == key]  # fmt: skip
    for row in keep:
        row["marks"] = row["marks"][:2]
    found["takeoff"]["quantities"] = keep
    found["takeoff"]["review_queue"] = sorted(found["takeoff"]["review_queue"])
    by_key = sorted(found["project_review"]["conflicts"], key=lambda c: (c["file"], c["quantity"]))
    found["project_review"]["conflicts"] = by_key[:1]
    found["drawing"]["suggestions"] = found["drawing"]["suggestions"][:3]
    edited = found["takeoff_edited"]
    edited["quantities"] = [row for key in ("door", "window", ROOM) for row in edited["quantities"]
                            if row["key"] == key]  # fmt: skip
    edited["review_queue"] = sorted(edited["review_queue"])
    for answer in (found["answer_conflict"], found["answer_signed"], found["answer_schedule"]):
        _marks(answer)
    return found


def _marks(answer: dict[str, Any]) -> None:
    answer["marks"] = answer["marks"][:2]
    if answer["quantity"] is not None:
        answer["quantity"]["marks"] = answer["quantity"]["marks"][:2]
    answer["line"]["evidence"] = answer["line"]["evidence"][:2]


def text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def rewrite_doc(fixtures: dict[str, Any]) -> None:
    """Each `<!-- fixture: <name>.json -->` line in API.md is followed by a ```json block: the
    block becomes the fixture's text."""
    lines = DOC.read_text(encoding="utf-8").splitlines(keepends=True)
    out: list[str] = []
    at = 0
    while at < len(lines):
        line = lines[at]
        out.append(line)
        at += 1
        if line.startswith(MARKER):
            name = line.removeprefix(MARKER).split()[0].removesuffix(".json")
            assert lines[at].startswith("```json"), f"no json block after {line!r}"
            end = next(i for i in range(at + 1, len(lines)) if lines[i].startswith("```"))
            out += ["```json\n", text(fixtures[name]), "```\n"]
            at = end + 1
    DOC.write_text("".join(out), encoding="utf-8")


def main() -> None:
    found = responses()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, value in found.items():
        (FIXTURES / f"{name}.json").write_text(text(value), encoding="utf-8")
    if "--doc" in sys.argv:
        rewrite_doc(found)
    print(f"wrote {len(found)} fixtures to {FIXTURES}")


if __name__ == "__main__":
    main()
