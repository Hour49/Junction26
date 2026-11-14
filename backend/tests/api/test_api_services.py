"""SV-29: GET /api/projects/{project_id}/drawings/{drawing_id}/services/{storey_id}.png draws a
storey of the drawing's stored services model; 404 unknown, 409 no model."""

import gzip
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapters.services_store import ServicesStore
from app.api.deps import get_ingest
from app.composition import build_ingest
from app.core.errors import NotFoundError
from app.core.ingest.model import FileStatus, ProjectStatus
from app.main import create_app
from app.settings import Settings
from tests.services_fixtures import two_rooms

PROJECT, MODELLED, BARE = "a" * 12, "0123456789abcdef", "fedcba9876543210"


class _Ingest:
    """A project of two IFC files: the first has a stored services model, the second not."""

    def status(self, project_id: str) -> ProjectStatus:
        if project_id != PROJECT:
            raise NotFoundError(f"no project {project_id}")
        files = (
            FileStatus(id="f1", path="m/heating.ifc", size=1, sha256="f" * 64, drawing_id=MODELLED),
            FileStatus(id="f2", path="m/other.ifc", size=1, sha256="e" * 64, drawing_id=BARE),
        )
        return ProjectStatus(
            id=PROJECT, name="p", state="done", created_at="2026-11-14T00:00:00Z", files=files
        )


@pytest.fixture
def client(settings: Settings, tmp_path: Path) -> TestClient:
    cache = tmp_path / "services"
    cache.mkdir()
    model = two_rooms()
    ServicesStore(cache).path(model.source.sha256).write_bytes(
        gzip.compress(model.model_dump_json().encode())
    )
    settings = settings.model_copy(update={"services_cache_dir": cache})
    app = create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    app.dependency_overrides[get_ingest] = _Ingest
    return TestClient(app)


def url(drawing: str = MODELLED, storey: str = "L1", project: str = PROJECT) -> str:
    return f"/api/projects/{project}/drawings/{drawing}/services/{storey}.png"


def test_sv29_route(client: TestClient) -> None:
    found = client.get(url())
    assert found.status_code == 200, found.text
    assert found.headers["content-type"] == "image/png" and found.content[:4] == b"\x89PNG"
    assert client.get(url(storey="L9")).status_code == 404
    assert client.get(url(drawing="1" * 16)).status_code == 404
    assert client.get(url(project="b" * 12)).status_code == 404
    missing = client.get(url(drawing=BARE))
    assert missing.status_code == 409 and "no services model" in missing.json()["detail"]


class _SetAside:
    """A project whose only IFC file was set aside at upload: no drawing, its sha256 known."""

    def status(self, project_id: str) -> ProjectStatus:
        if project_id != PROJECT:
            raise NotFoundError(f"no project {project_id}")
        heating = FileStatus(id="f1", path="m/heating.ifc", size=1, sha256="f" * 64)
        return ProjectStatus(
            id=PROJECT, name="p", state="done", created_at="2026-11-15T00:00:00Z", files=(heating,)
        )


def test_sv29_a_set_aside_ifc_is_drawn_by_its_sha256_prefix(client: TestClient) -> None:
    """#281 c6885170828: such a file has no drawing id; its model is found by sha256[:16]."""
    client.app.dependency_overrides[get_ingest] = _SetAside  # type: ignore[attr-defined]
    found = client.get(url(drawing="f" * 16))
    assert found.status_code == 200, found.text
    assert client.get(url(drawing="e" * 16)).status_code == 404
