"""Big QA R1 (local-dec, ifc rows 2, 3, 24, E1-E4): a storey named without quotes by the file's own
code or name ("on P1", "on level P1", "on the P1 plan", "on the Erdgeschoss", "on EG") was
dropped, so the building model's whole count (the demo's 68 doors, at High) and the other sheet's
16 came back as P1's answer. Now it scopes the question like a quoted storey does, and a storey the
file lacks is refused. Real files: the demo's bim/ folder and three dataset models (skipped when
the partner data is not linked)."""

import io
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings

ROOT = Path(__file__).resolve().parents[3] / "data"
DEMO = ROOT / "demo" / "demo-project.zip"
DATA = ROOT / "stoa" / "full" / "junction-dataset" / "data"
AC20 = DATA / "ifc_models" / "kit-fzk-haus_ac20-fzk-haus.ifc"
OFFICE = DATA / "ifc_bench" / "fantasy_office_building_3_arc.ifc"
HUB = DATA / "ifc_bench" / "digital_hub_arc.ifc"
MODEL = "bimspeed-vitoria_ald26-project.ifc"
P2 = "bimspeed-vitoria_ald26-project_plan-03-p2.pdf"
needs = pytest.mark.skipif(
    not all(p.exists() for p in (DEMO, AC20, OFFICE, HUB)), reason="partner data not linked"
)


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    """One app for the module (the demo's IFC takes seconds to read), as conftest's `client`."""
    tmp = tmp_path_factory.mktemp("storey")
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(tmp)  # so a developer's backend/.env can't change test results
        settings = Settings(
            projects_dir=tmp / "projects",
            sample_archive=tmp / "sample.zip",
            credit_dataset=tmp / "dataset",
            credit_photos=tmp / "photos",
        )
        yield TestClient(create_app(settings, build_ingest(settings, settings.projects_dir,
                                                           background=False)))  # fmt: skip


def project(client: TestClient, name: str, content: bytes) -> str:
    return client.post("/api/projects", params={"name": name}, content=content).json()["id"]


@pytest.fixture(scope="module")
def demo(client: TestClient) -> str:
    """The demo zip's bim/ folder alone: the IFC and its P1 and P2 sheets (local-dec's
    big-ifc-1)."""
    out = io.BytesIO()
    with zipfile.ZipFile(DEMO) as given, zipfile.ZipFile(out, "w") as made:
        for entry in given.namelist():
            if entry.startswith("bim/") and not entry.endswith("/"):
                made.writestr(entry, given.read(entry))
    return project(client, "bim.zip", out.getvalue())


def parts(client: TestClient, project_id: str, question: str) -> dict[str, Any]:
    found = client.post(f"/api/projects/{project_id}/ask", json={"question": question}).json()
    return {part["name"].split("/")[-1]: part["answer"] for part in found["parts"]}


@needs
@pytest.mark.parametrize(
    "question",
    [
        "How many doors are there on P1?",
        "How many doors are there on level P1?",
        "How many doors are there on floor P1?",
        "How many doors are there on 'P1'?",  # as before
    ],
)
def test_r1_the_demo_storey_by_its_code_is_that_storey_not_the_whole_model(
    client: TestClient, demo: str, question: str
) -> None:
    got = parts(client, demo, question)
    assert got[MODEL]["answer"] == 16, got[MODEL]  # main: 68, the whole model, at High
    assert got[P2]["answer"] is None, got[P2]  # the P2 sheet is no answer for P1 (main: 16)


@needs
@pytest.mark.parametrize(
    ("question", "want"),
    [
        ("How many windows are there on P1?", 18),  # main: 70
        ("How many windows are shown on the P1 plan?", 18),  # main: refused as a room
        ("How many rooms are there on P1?", 17),  # main: 73
    ],
)
def test_r1_the_demo_model_answers_for_the_named_storey(
    client: TestClient, demo: str, question: str, want: int
) -> None:
    assert parts(client, demo, question)[MODEL]["answer"] == want


@needs
@pytest.mark.parametrize(
    ("path", "question", "want"),
    [
        (OFFICE, "How many doors are there on EG?", 17),  # main: 75
        (OFFICE, "How many windows are there on OG1?", 37),  # main: 167
        (OFFICE, "How many doors are there on OG2?", 16),
        (HUB, "How many doors are there on E00?", 26),  # main: 64
    ],
)
def test_r1_a_models_storey_by_its_own_code_or_name(
    client: TestClient, path: Path, question: str, want: int
) -> None:
    got = parts(client, project(client, path.name, path.read_bytes()), question)
    assert got[path.name]["answer"] == want, got[path.name]


@needs
def test_r1_a_storey_the_file_lacks_is_refused_not_the_whole_model(
    client: TestClient, demo: str
) -> None:
    for name, answer in parts(client, demo, "How many doors are there on P9?").items():
        assert answer["answer"] is None, (name, answer)  # main: the model's 68


@needs
def test_r1_a_storey_by_its_name_is_scoped_as_if_quoted(client: TestClient) -> None:
    """ac20 row 24: "on the Erdgeschoss" was read as a room, and the fact path gave the file's 77.
    Now it is the storey, the same row as "on 'Erdgeschoss'" (the model's takeoff puts 5 doors
    there; local-dec's truth is 18: the IFC's door-to-storey count, not this parser path)."""
    pid = project(client, AC20.name, AC20.read_bytes())
    named = parts(client, pid, "How many doors are there on the Erdgeschoss?")[AC20.name]
    quoted = parts(client, pid, "How many doors are there on 'Erdgeschoss'?")[AC20.name]
    assert named["answer"] == quoted["answer"] is not None, named
    assert named["answer"] != 77  # main: the whole file's
