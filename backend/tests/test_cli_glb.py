"""`python -m app.cli glb PROJECT_OR_FILES`: the deploy precomputes the 3D views, so the route
serves them at once."""

import hashlib
from pathlib import Path

import pytest
from test_ifc_glb import flat, house

from app.cli import main
from app.composition import build_ingest
from app.settings import Settings


@pytest.fixture
def projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path / "projects"))
    return tmp_path / "projects"


def test_files_are_converted_into_the_cache(
    projects: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data, _ = house()
    (tmp_path / "house.ifc").write_bytes(data)
    (tmp_path / "flat.ifc").write_bytes(flat())
    assert main(["glb", str(tmp_path / "house.ifc"), str(tmp_path / "flat.ifc")]) == 1
    digest = hashlib.sha256(data).hexdigest()
    assert (projects / "models-3d" / f"{digest}.glb.gz").is_file()
    said = capsys.readouterr().out
    assert "house.ifc: ready, 3 elements" in said
    assert "flat.ifc: unavailable (no_geometry)" in said


def test_a_project_has_its_ifc_files_converted(
    projects: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data, _ = house()
    settings = Settings(projects_dir=projects)
    ingest = build_ingest(settings, projects, background=False)
    project_id = ingest.start("house.ifc", data)
    ingest.close()
    assert main(["glb", project_id]) == 0
    assert f"{project_id}/house.ifc: ready, 3 elements" in capsys.readouterr().out


def test_an_unknown_argument_is_an_error(projects: Path) -> None:
    assert main(["glb", "nothing-here.ifc"]) == 1
