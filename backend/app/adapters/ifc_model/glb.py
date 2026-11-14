"""The 3D view of an IFC file (MODEL_3D): one GLB of the whole model, each node named by its
element's GlobalId so the view can highlight elements by id. Openings and rooms are left out:
an opening is a hole, not a thing, and a room's volume hides what bounds it.

ifcopenshell's own glTF serializer writes it (no new dependency). Geometry of a big model can
take gigabytes (DigitalHub plumbing, 25 MB: 2.2 GB peak with 4 threads, 1.7-2.0 GB with 2,
1.27 GB and 56 s with 1, 2026-11-14), so each conversion runs alone, on one thread, in a
subprocess, under a memory cap: a systemd user scope (MemoryMax) where the machine has one, else
RLIMIT_AS at 1.5x the budget (it counts address space, which runs ahead of memory used). Over the
cap, or over its computing time (RLIMIT_CPU: CPU seconds, so a busy machine does not count), the
child is killed and the model is too_big; the app never shares its memory. A child still running
at 3x its time in wall-clock seconds is stuck or starved: killed, said as busy, and not recorded,
so the next request tries again. One conversion per cache at a time across processes too: the app
and `python -m app.cli glb` take turns on the cache's lock file.

Cache, beside the projects' drawing models, by content (`<sha256>` of the IFC file):

    <root>/<sha256>.glb.gz   the GLB, gzipped: the route sends it as is to a client that takes gzip
    <root>/<sha256>.json     the result (Model3d): ready with its element count, or unavailable

A result is written last, whole; the GLB is written in a temporary folder of the cache and
renamed in, so a reader never sees half of either, and a killed run leaves nothing.
To retry a model that was unavailable (say, with a bigger budget), `python -m app.cli glb` does.

Run as a script, it is the child: `python -m app.adapters.ifc_model.glb <in.ifc> <out.glb>`.
"""

import fcntl
import gzip
import json
import logging
import math
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from functools import cache
from pathlib import Path

from app.adapters.whole_file import write_whole
from app.core.ingest.model import Model3d, Model3dCode

log = logging.getLogger(__name__)

MAX_BYTES = 60 * 1024 * 1024  # a larger GLB is too_big: a judge's laptop opens it slowly
THREADS = 1  # DigitalHub plumbing: 1.27 GB peak on 1, up to 2.0 GB on 2 (the live app has 4 GB)
LEFT_OUT = ["IfcOpeningElement", "IfcSpace"]
NO_GEOMETRY = 3  # the child's exit code for a model with no shape to draw
FAILED = "the 3D model could not be built from this file"  # the details go to the log
BUSY = "the server was too busy to build the 3D model; it is tried again on the next request"
LOCK = ".convert.lock"  # in the cache folder: one conversion at a time across processes
CHILD = [sys.executable, "-m", __name__]  # the converter; tests swap in one that spins or hangs
BACKEND = Path(__file__).resolve().parents[3]  # the child runs `-m` from here
_ONE_AT_A_TIME = threading.Lock()  # per process: the app's worker and any direct call


class GlbModels:
    """The 3D views of one cache folder. `start` queues a conversion on the one background
    worker; `convert` runs one now (the worker, the CLI)."""

    def __init__(
        self, root: Path, memory_mb: int, timeout_s: float, max_bytes: int = MAX_BYTES
    ) -> None:
        self._root = root
        self._memory_mb = memory_mb
        self._timeout_s = timeout_s
        self._max_bytes = max_bytes
        self._lock = threading.RLock()  # start reads the status under it
        self._queued: dict[str, Future[Model3d]] = {}
        self._worker = ThreadPoolExecutor(1, thread_name_prefix="glb")

    def glb_gz(self, sha256: str) -> Path:
        return self._root / f"{sha256}.glb.gz"

    def status(self, sha256: str) -> Model3d:
        record = self._root / f"{sha256}.json"
        if record.is_file():
            return Model3d.model_validate_json(record.read_text(encoding="utf-8"))
        with self._lock:
            queued = sha256 in self._queued
        return Model3d(state="converting" if queued else "not_started")

    def start(self, sha256: str, read: Callable[[], bytes]) -> Model3d:
        """Queues the conversion unless it has a result or is queued already; returns the state."""
        with self._lock:
            found = self.status(sha256) if sha256 not in self._queued else None
            if found is not None and found.state == "not_started":
                self._queued[sha256] = self._worker.submit(self._background, sha256, read)
        return self.status(sha256)

    def join(self) -> None:
        """Waits for every queued conversion (tests)."""
        with self._lock:
            queued = list(self._queued.values())
        for future in queued:
            future.result()

    def close(self) -> None:
        """Drops what is queued; a running conversion ends on its own (its time limit)."""
        self._worker.shutdown(wait=False, cancel_futures=True)

    def _background(self, sha256: str, read: Callable[[], bytes]) -> Model3d:
        try:
            return self.convert(sha256, read())
        except Exception as error:  # a bug or a disk error: logged, never shown (it names paths)
            log.exception("3D view of %s failed: %s", sha256, error)
            return self._record(sha256, _unavailable("failed", FAILED))
        finally:
            with self._lock:
                self._queued.pop(sha256, None)

    def convert(self, sha256: str, data: bytes) -> Model3d:
        """Converts one IFC file, alone, and records the result."""
        self._root.mkdir(parents=True, exist_ok=True)
        with (
            _ONE_AT_A_TIME,
            _one_per_cache(self._root),
            tempfile.TemporaryDirectory(dir=self._root, prefix=".glb-") as work,
        ):
            source, out = Path(work) / "model.ifc", Path(work) / "model.glb"
            source.write_bytes(data)
            found = self._run(source, out)
            if found.reason == BUSY:
                return found  # the machine's state, not the model's: not recorded
            if found.state == "ready":
                size = out.stat().st_size
                if size > self._max_bytes:
                    found = _unavailable(
                        "too_big",
                        f"its 3D model is {size / 2**20:.0f} MB, over the "
                        f"{self._max_bytes / 2**20:g} MB limit",
                    )
                else:
                    zipped = Path(work) / "model.glb.gz"
                    with out.open("rb") as raw, gzip.open(zipped, "wb", compresslevel=6) as packed:
                        shutil.copyfileobj(raw, packed)
                    zipped.replace(self.glb_gz(sha256))
        return self._record(sha256, found)

    def _record(self, sha256: str, found: Model3d) -> Model3d:
        write_whole(self._root / f"{sha256}.json", found.model_dump_json())
        return found

    def _run(self, source: Path, out: Path) -> Model3d:
        child = [*CHILD, str(source), str(out)]
        memory = None
        if has_systemd_scope():
            child = [*_SCOPE, "-p", f"MemoryMax={self._memory_mb}M", *child]
        else:
            memory = int(self._memory_mb * 1.5 * 2**20)
        cpu = max(1, math.ceil(self._timeout_s))  # RLIMIT_CPU counts whole seconds
        process = subprocess.Popen(
            child,
            cwd=BACKEND,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,  # its own group: a kill reaches whatever it started
            # one BLAS thread: each one's buffers count against RLIMIT_AS before any geometry
            env={**os.environ, "OPENBLAS_NUM_THREADS": "1"},
            preexec_fn=lambda: _cap(cpu, memory),  # kept across systemd-run's exec
        )
        try:
            said, errors = process.communicate(timeout=self._timeout_s * 3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            log.warning("3D view conversion still running after %g s: killed", self._timeout_s * 3)
            return _unavailable("failed", BUSY)
        if process.returncode == -signal.SIGXCPU:
            return _unavailable(
                "too_big", f"its 3D model needs more than {cpu} s of computing time to build"
            )
        if process.returncode == 0:
            return Model3d(state="ready", elements=int(json.loads(said)["elements"]))
        if process.returncode == NO_GEOMETRY:
            return _unavailable("no_geometry", "the model has no 3D shapes to draw")
        if process.returncode < 0 or _out_of_memory(errors):
            return _unavailable(
                "too_big", f"its 3D model needs more than the {self._memory_mb} MB memory budget"
            )
        log.warning("3D view conversion exited %s: %s", process.returncode, errors[-2000:])
        return _unavailable("failed", FAILED)  # the child's words name paths: the log only


_SCOPE = ["systemd-run", "--user", "--scope", "--quiet", "-p", "MemorySwapMax=0"]


@cache
def has_systemd_scope() -> bool:
    """A systemd user manager that runs a capped scope (not in most containers or CI)."""
    if shutil.which("systemd-run") is None:
        return False
    try:
        probe = subprocess.run([*_SCOPE, "true"], capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def _cap(cpu: int, memory: int | None) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 5))  # SIGXCPU at the soft limit
    if memory is not None:
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))


@contextmanager
def _one_per_cache(root: Path) -> Iterator[None]:
    """Holds the cache's lock file while one conversion runs, whichever process runs it."""
    with (root / LOCK).open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(held, fcntl.LOCK_UN)


def _out_of_memory(errors: str) -> bool:
    """The child said it ran out (RLIMIT_AS fails an allocation, not always with a signal)."""
    words = ("MemoryError", "bad_alloc", "Cannot allocate", "failed to map", "out of memory")
    words += ("Memory allocation",)  # OpenBLAS: "Memory allocation still failed after 10 retries"
    return any(word in errors for word in words)


def _unavailable(code: Model3dCode, reason: str) -> Model3d:
    return Model3d(state="unavailable", code=code, reason=reason)


def _child(source: str, out: str) -> int:
    """Writes the GLB; prints {"elements": n}. Run in the capped subprocess only."""
    import ifcopenshell
    import ifcopenshell.geom

    model = ifcopenshell.open(source)
    settings = ifcopenshell.geom.settings()
    settings.set("use-element-guids", True)
    settings.set("y-up", True)
    writer = ifcopenshell.geom.serializers.glb(out, settings)
    writer.setFile(model)
    writer.setUnitNameAndMagnitude("METER", 1.0)
    writer.writeHeader()
    shapes = ifcopenshell.geom.iterator(settings, model, THREADS, exclude=LEFT_OUT)
    elements = 0
    if shapes.initialize():
        while True:
            writer.write(shapes.get())
            elements += 1
            if not shapes.next():
                break
    writer.finalize()
    if elements == 0:
        return NO_GEOMETRY
    print(json.dumps({"elements": elements}))
    return 0


if __name__ == "__main__":
    sys.exit(_child(sys.argv[1], sys.argv[2]))
