"""IFC -> GLB for the 3D view (app/adapters/ifc_model/glb.py): a synthetic model, converted in a
capped subprocess; failures become `unavailable` with a reason and leave no half-written file."""

import gzip
import hashlib
import json
import struct
from pathlib import Path

import pytest
from ifc_models import IfcFile, box

from app.adapters.ifc_model import glb
from app.adapters.ifc_model.glb import GlbModels


def house() -> tuple[bytes, list[str]]:
    """A storey with two walls and a slab, each a box; a room (left out of the view)."""
    model = IfcFile()
    storey = model.storey("Ground floor")
    walls = [
        model.element("IfcWall", storey=storey, name="Wall 1", solid=(box(0, 0, 8, 0.2), 0, 2.6)),
        model.element("IfcWall", storey=storey, name="Wall 2", solid=(box(0, 0, 0.2, 6), 0, 2.6)),
        model.element("IfcSlab", storey=storey, name="Slab", solid=(box(0, 0, 8, 6), -0.25, 0.25)),
    ]
    model.space(storey, "0.01", "Living", (box(0, 0, 8, 6), 0, 2.6))
    return model.ifc(), walls


def flat() -> bytes:
    """Objects without any shape: nothing to draw."""
    model = IfcFile()
    model.element("IfcWall", storey=model.storey("Ground floor"), name="Wall 1")
    return model.ifc()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def node_names(glb_bytes: bytes) -> list[str]:
    assert glb_bytes[:4] == b"glTF"
    length = struct.unpack("<I", glb_bytes[12:16])[0]
    return [node.get("name") for node in json.loads(glb_bytes[20 : 20 + length])["nodes"]]


def leftovers(root: Path) -> list[str]:
    """What a conversion left besides its record and its GLB."""
    return sorted(
        path.name
        for path in root.iterdir()
        if not (path.name.endswith(".json") or path.name.endswith(".glb.gz"))
    )


@pytest.fixture(params=["systemd", "rlimit"])
def cap(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Both memory caps: a systemd scope where the machine has one, else RLIMIT_AS."""
    if request.param == "systemd" and not glb.has_systemd_scope():
        pytest.skip("no systemd user scope on this machine")
    monkeypatch.setattr(glb, "has_systemd_scope", lambda: request.param == "systemd")
    return str(request.param)


def test_a_model_becomes_a_gzipped_glb_named_by_globalid(tmp_path: Path, cap: str) -> None:
    data, walls = house()
    models = GlbModels(tmp_path, memory_mb=1500, timeout_s=60)
    assert models.status(sha(data)).state == "not_started"
    found = models.convert(sha(data), data)
    assert (found.state, found.elements, found.code) == ("ready", 3, None)
    assert models.status(sha(data)) == found  # from the record, after the run
    names = node_names(gzip.decompress(models.glb_gz(sha(data)).read_bytes()))
    assert set(walls) <= set(names)  # the room is left out
    assert len(names) == 3
    assert leftovers(tmp_path) == []


def test_a_model_without_shapes_is_no_geometry(tmp_path: Path) -> None:
    data = flat()
    found = GlbModels(tmp_path, memory_mb=1500, timeout_s=60).convert(sha(data), data)
    assert (found.state, found.code) == ("unavailable", "no_geometry")
    assert found.reason
    assert not GlbModels(tmp_path, 1500, 60).glb_gz(sha(data)).exists()
    assert leftovers(tmp_path) == []


def test_over_the_memory_budget_is_too_big_and_leaves_nothing(tmp_path: Path, cap: str) -> None:
    data, _ = house()
    found = GlbModels(tmp_path, memory_mb=20, timeout_s=60).convert(sha(data), data)
    assert (found.state, found.code) == ("unavailable", "too_big")
    assert "memory" in found.reason
    assert not GlbModels(tmp_path, 1500, 60).glb_gz(sha(data)).exists()
    assert leftovers(tmp_path) == []


def test_over_the_time_limit_is_killed_and_too_big(tmp_path: Path) -> None:
    data, _ = house()
    found = GlbModels(tmp_path, memory_mb=1500, timeout_s=0.01).convert(sha(data), data)
    assert (found.state, found.code) == ("unavailable", "too_big")
    assert "0.01 s" in found.reason
    assert leftovers(tmp_path) == []


def test_a_glb_over_the_size_limit_is_too_big(tmp_path: Path) -> None:
    data, _ = house()
    found = GlbModels(tmp_path, memory_mb=1500, timeout_s=60, max_bytes=100).convert(
        sha(data), data
    )
    assert (found.state, found.code) == ("unavailable", "too_big")
    assert "limit" in found.reason
    assert leftovers(tmp_path) == []


def test_start_converts_in_the_background_once(tmp_path: Path) -> None:
    data, _ = house()
    models = GlbModels(tmp_path, memory_mb=1500, timeout_s=60)
    calls: list[int] = []

    def read() -> bytes:
        calls.append(1)
        return data

    assert models.start(sha(data), read).state == "converting"
    assert models.start(sha(data), read).state in ("converting", "ready")  # queued once
    models.join()
    assert models.status(sha(data)).state == "ready"
    assert calls == [1]
