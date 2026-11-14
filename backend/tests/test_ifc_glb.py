"""IFC -> GLB for the 3D view (app/adapters/ifc_model/glb.py): a synthetic model, converted in a
capped subprocess; failures become `unavailable` with a reason and leave no half-written file."""

import fcntl
import gzip
import hashlib
import json
import struct
import sys
import threading
import time
from pathlib import Path

import pytest
from ifc_models import IfcFile, box

from app.adapters.ifc_model import glb
from app.adapters.ifc_model.glb import GlbModels
from app.core.ingest.model import Model3d


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
        and path.name != glb.LOCK
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


SPIN = [sys.executable, "-c", "while True: pass"]  # a child that only computes
HANG = [sys.executable, "-c", "import time; time.sleep(60)"]  # one that never gets to compute


def test_over_the_computing_time_limit_is_too_big(
    tmp_path: Path, cap: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The limit is CPU time (RLIMIT_CPU): what the model costs, whatever else the machine runs."""
    monkeypatch.setattr(glb, "CHILD", SPIN)
    data, _ = house()
    found = GlbModels(tmp_path, memory_mb=1500, timeout_s=1).convert(sha(data), data)
    assert (found.state, found.code) == ("unavailable", "too_big")
    assert "1 s of computing time" in found.reason
    assert GlbModels(tmp_path, 1500, 1).status(sha(data)) == found  # recorded: it is the model
    assert leftovers(tmp_path) == []


def test_a_busy_or_stuck_conversion_is_not_too_big_and_is_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past the wall-clock guard without using its CPU time: the machine, not the model. Said,
    not recorded, so the next request starts it again."""
    monkeypatch.setattr(glb, "CHILD", HANG)
    data, _ = house()
    models = GlbModels(tmp_path, memory_mb=1500, timeout_s=0.5)
    found = models.convert(sha(data), data)
    assert (found.state, found.code) == ("unavailable", "failed")
    assert found.reason == glb.BUSY
    assert models.status(sha(data)).state == "not_started"
    assert leftovers(tmp_path) == []


def test_the_cli_waits_while_the_app_converts(tmp_path: Path) -> None:
    """Two processes on one cache (the app, `python -m app.cli glb`) take turns on its lock file."""
    data, _ = house()
    tmp_path.mkdir(exist_ok=True)
    with (tmp_path / glb.LOCK).open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)  # another process's conversion, as flock sees it
        waiting = threading.Thread(
            target=GlbModels(tmp_path, 1500, 60).convert, args=(sha(data), data)
        )
        waiting.start()
        time.sleep(1.0)
        assert waiting.is_alive()
        assert not GlbModels(tmp_path, 1500, 60).glb_gz(sha(data)).exists()
    waiting.join(timeout=60)
    assert GlbModels(tmp_path, 1500, 60).status(sha(data)).state == "ready"


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


def test_a_failed_conversion_says_one_plain_sentence_and_logs_the_details(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The child's error names paths and the server's files: it goes to the log, not the API."""
    data = b"ISO-10303-21; not a model"
    found = GlbModels(tmp_path, memory_mb=1500, timeout_s=60).convert(sha(data), data)
    assert found == Model3d(state="unavailable", code="failed", reason=glb.FAILED)
    assert "Unable to parse" in caplog.text  # the details, for whoever reads the log

    def broken() -> bytes:
        raise OSError(f"[Errno 5] Input/output error: '{tmp_path}/secret/model.ifc'")

    models = GlbModels(tmp_path, memory_mb=1500, timeout_s=60)
    models.start("ab" * 32, broken)
    models.join()
    assert models.status("ab" * 32) == Model3d(
        state="unavailable", code="failed", reason=glb.FAILED
    )
    assert "secret" in caplog.text


def test_conversions_run_one_at_a_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two caches, two threads: the second child starts only when the first has ended."""
    running, most = [0], [0]
    count = threading.Lock()
    run = GlbModels._run  # pyright: ignore[reportPrivateUsage]

    def counted(self: GlbModels, source: Path, out: Path) -> Model3d:
        with count:
            running[0] += 1
            most[0] = max(most[0], running[0])
        time.sleep(0.3)
        try:
            return run(self, source, out)
        finally:
            with count:
                running[0] -= 1

    monkeypatch.setattr(GlbModels, "_run", counted)
    data, _ = house()
    both = [
        threading.Thread(
            target=GlbModels(tmp_path / name, 1500, 60).convert, args=(sha(data), data)
        )
        for name in ("a", "b")
    ]
    for thread in both:
        thread.start()
    for thread in both:
        thread.join()
    assert most == [1]
    assert all((tmp_path / name / f"{sha(data)}.glb.gz").is_file() for name in ("a", "b"))


def test_openblas_running_out_under_rlimit_is_too_big() -> None:
    """Without systemd, RLIMIT_AS often first fails numpy's OpenBLAS, which exits 1 saying so."""
    said = "OpenBLAS error: Memory allocation still failed after 10 retries, giving up.\n"
    assert glb._out_of_memory(said)  # pyright: ignore[reportPrivateUsage]
    assert not glb._out_of_memory("ValueError: not a model\n")  # pyright: ignore[reportPrivateUsage]
