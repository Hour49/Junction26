"""Where services models are kept (services-model.md SV-2, SV-8): one gzipped JSON per source
file and builder version, `<cache>/<sha256>.services.v1.b<builder>.json.gz`, beside the fact-sheet
cache, written atomically. A model an older builder wrote is not served: it is rebuilt, with the
saved id map, so a deploy picks up builder fixes and ids survive.

The id map (GlobalId -> element id) is kept per file name as the project knows it, not per
content hash, so a re-exported file (new bytes, same name) keeps every old id; the spec's
`<sha256>.ids.json` could not, since a re-export has another sha256.

`ServicesBuilds` builds a project's missing models off the request (SV-8: never at question time),
as `facts_store.StoredFacts` builds fact sheets: one child process at a time with its own memory
and time budget, once per sha256 in flight, a failure not started again in this process. A file
with no distribution element (a building model) stores a marker,
`<sha256>.services.none.b<builder>`, so it is tried once, not again after a restart.
"""

import gzip
import hashlib
import json
import logging
import os
import resource
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from app.adapters.ifc_model import services_model
from app.adapters.ifc_model.glb import (
    _SCOPE,  # pyright: ignore[reportPrivateUsage]
    _out_of_memory,  # pyright: ignore[reportPrivateUsage]
    has_systemd_scope,
)
from app.core.errors import InvalidInputError
from app.core.services.stored import ServicesModel

logger = logging.getLogger(__name__)

BUILD_MEMORY_MB = 3000  # the plumbing model measured 1.29 GB (.agents/exp/services-wall-demo.md)
BUILD_TIMEOUT_S = 600.0  # off the request: the plumbing model measured 279 s on a loaded box
NOT_READ = 2  # the child's exit code for a file it cannot read, its words on stderr
NO_SERVICES = 3  # the child's exit code for a model with no distribution element
CHILD = [sys.executable, "-m", __name__]  # the builder; run with `-m` from the backend folder
BACKEND = Path(__file__).resolve().parents[2]

Build = Callable[[bytes, str, Path], None]  # the file's bytes, its name, the cache folder
Start = Callable[[Callable[[], None]], None]


class ServicesStore:
    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir

    def path(self, sha256: str) -> Path:
        """Where the current builder keeps the model of the file with this content."""
        version = services_model.BUILDER_VERSION
        return self._dir / f"{sha256}.services.v1.b{version}.json.gz"

    def none_path(self, sha256: str) -> Path:
        """The marker of a file with this content that has no services model (no distribution
        element), per builder version: a builder fix tries it again."""
        return self._dir / f"{sha256}.services.none.b{services_model.BUILDER_VERSION}"

    def load(self, sha256: str) -> ServicesModel | None:
        path = self.path(sha256)
        if not path.is_file():
            return None
        return ServicesModel.model_validate_json(gzip.decompress(path.read_bytes()))

    def build(
        self,
        name: str,
        data: bytes,
        architecture: bytes | None = None,
        keep_empty: bool = True,
    ) -> ServicesModel | None:
        """The model of the file `name` with content `data` (and its building model's bytes),
        built once and kept. None when ifcopenshell cannot read it. `keep_empty=False`: a model
        with no element is returned and not kept, only marked (a building model is no services
        model)."""
        sha256 = hashlib.sha256(data).hexdigest()
        stored = self.load(sha256)
        if stored is not None:
            return stored
        ids_path = self._dir / f"{hashlib.sha256(name.encode()).hexdigest()[:24]}.ids.json"
        ids = json.loads(ids_path.read_text(encoding="utf-8")) if ids_path.is_file() else {}
        with tempfile.TemporaryDirectory() as folder:
            services = Path(folder) / "services.ifc"
            services.write_bytes(data)
            building = None
            if architecture is not None:
                building = Path(folder) / "architecture.ifc"
                building.write_bytes(architecture)
            try:
                model, ids = services_model.build_services_model(services, ids, building)
            except Exception as error:  # ifcopenshell raises its own and plain RuntimeErrors
                logger.warning("%s: no services model: %s", name, error)
                return None
        if not keep_empty and not model.elements:
            self._write(self.none_path(sha256), b"")
            return model
        self._write(ids_path, json.dumps(ids, indent=0, sort_keys=True).encode())
        raw = model.model_dump_json().encode()
        self._write(self.path(model.source.sha256), gzip.compress(raw, mtime=0))
        return model

    def _write(self, path: Path, data: bytes) -> None:
        """Whole or not at all: a run killed mid-write leaves no half file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        part.write_bytes(data)
        part.replace(path)


def build_apart(
    data: bytes,
    name: str,
    cache: Path,
    memory_mb: int | None = None,
    timeout_s: float | None = None,
) -> None:
    """The services model of the file `name` stored in `cache` by a child process held to
    `memory_mb` (BUILD_MEMORY_MB) and `timeout_s` (BUILD_TIMEOUT_S); the parse's memory goes with
    the child. A file it cannot read, with no distribution element, or that needs more, is an
    InvalidInputError, and nothing is stored."""
    memory_mb = memory_mb or BUILD_MEMORY_MB
    timeout_s = timeout_s or BUILD_TIMEOUT_S
    with tempfile.TemporaryDirectory(prefix="services-build-") as work:
        source = Path(work) / "model.ifc"
        source.write_bytes(data)
        child = [*CHILD, str(source), name, str(cache)]
        limit = None
        if has_systemd_scope():
            child = [*_SCOPE, "-p", f"MemoryMax={memory_mb}M", *child]
        else:
            limit = int(memory_mb * 1.5 * 2**20)  # address space: more than what is touched
        try:
            done = subprocess.run(
                child,
                cwd=BACKEND,
                capture_output=True,
                timeout=timeout_s,
                check=False,
                env={**os.environ, "OPENBLAS_NUM_THREADS": "1"},
                preexec_fn=None if limit is None else lambda: _cap(limit),
            )
        except subprocess.TimeoutExpired as error:
            raise InvalidInputError(
                f"the model takes more than {timeout_s:g} s to build"
            ) from error
    errors = done.stderr.decode(errors="replace")
    if done.returncode == 0:
        return
    if done.returncode in (NOT_READ, NO_SERVICES):
        raise InvalidInputError(errors.strip().splitlines()[-1] if errors.strip() else "not read")
    if done.returncode < 0 or _out_of_memory(errors):
        raise InvalidInputError(f"the model needs more than {memory_mb} MB to build")
    raise RuntimeError(f"the services builder exited {done.returncode}: {errors[-2000:]}")


def _in_background(job: Callable[[], None]) -> None:
    threading.Thread(target=job, name="services-build", daemon=True).start()


class ServicesBuilds:
    """The project files' services models that are not stored yet, built off the request."""

    def __init__(self, cache: Path, build: Build = build_apart, start: Start = _in_background):
        self._store = ServicesStore(cache)
        self._cache = cache
        self._build = build
        self._start = start
        self._lock = threading.Lock()  # guards the two sets
        self._one = threading.Lock()  # one build at a time: two at once would double the memory
        self._busy: set[str] = set()  # sha256s in flight
        self._failed: set[str] = set()

    def building(self, sha256: str, name: str, data: Callable[[], bytes]) -> bool:
        """Whether the model of this content is being built: a build starts when none is stored,
        in flight or failed. False when it is stored, has none or its build failed."""
        if self._store.path(sha256).is_file() or self._store.none_path(sha256).is_file():
            return False
        with self._lock:
            if sha256 in self._failed:
                return False
            if sha256 in self._busy:
                return True
            self._busy.add(sha256)

        def job() -> None:
            failed = False
            try:
                with self._one:
                    self._build(data(), name, self._cache)
            except Exception:  # the tools said it is being built; said once in the log
                logger.warning("%s: no services model built", sha256[:12], exc_info=True)
                failed = True
            with self._lock:
                self._busy.discard(sha256)
                if failed:
                    self._failed.add(sha256)

        self._start(job)
        return True


def _cap(limit: int) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def _child(source: str, name: str, cache: str) -> int:
    try:
        model = ServicesStore(Path(cache)).build(name, Path(source).read_bytes(), keep_empty=False)
    except Exception as error:  # ifcopenshell raises its own and plain RuntimeErrors
        print(str(error).replace("\n", " "), file=sys.stderr)
        return NOT_READ
    if model is None:
        print("not an IFC file ifcopenshell can read", file=sys.stderr)
        return NOT_READ
    if not model.elements:
        print("no distribution element: not a services model", file=sys.stderr)
        return NO_SERVICES
    return 0


if __name__ == "__main__":
    sys.exit(_child(*sys.argv[1:4]))
