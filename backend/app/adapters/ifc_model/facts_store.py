"""`IFC_FACTS=true` in the API: the chat's fact sheets of IFC models, stored as JSON by the file's
sha256 and the fact code's version (the name IfcFactSource's cache uses, so one folder serves both).

The API process never parses a model at question time: ifcopenshell keeps what it parsed until its
process ends (16 models grew it by 2.9 GB, ifc_services.py), and a big model took 127 s and
1.36 GB. A stored sheet is read from disk. On a miss, one build starts in a child process with its
own memory and time budget, off the request, one at a time and once per sha256 in flight; the
question is answered as it would be without facts. A build that fails is not started again in this
process.
"""

import hashlib
import logging
import os
import resource
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from app.adapters.ifc_model.facts_source import CODE, read_facts
from app.adapters.ifc_model.glb import (
    _SCOPE,  # pyright: ignore[reportPrivateUsage]
    _out_of_memory,  # pyright: ignore[reportPrivateUsage]
    has_systemd_scope,
)
from app.core.errors import InvalidInputError
from app.core.ifc_facts import FactSheet

log = logging.getLogger(__name__)

BUILD_MEMORY_MB = 3000  # the big model measured 1.36 GB
BUILD_TIMEOUT_S = 600.0  # off the request: a big model measured 127 s
NOT_READ = 2  # the child's exit code for a file it cannot read, its words on stderr
CHILD = [sys.executable, "-m", __name__]  # the builder; run with `-m` from the backend folder
BACKEND = Path(__file__).resolve().parents[3]

Build = Callable[[bytes, str, Path], None]  # model bytes, its name, where the sheet goes
Start = Callable[[Callable[[], None]], None]


def build_apart(
    data: bytes, model: str, out: Path, memory_mb: int | None = None, timeout_s: float | None = None
) -> None:
    """The model's fact sheet written to `out` by a child process held to `memory_mb`
    (BUILD_MEMORY_MB) and `timeout_s` (BUILD_TIMEOUT_S); the parse's memory goes with the child.
    A model it cannot read, or that needs more, is an InvalidInputError, and nothing is written."""
    memory_mb = memory_mb or BUILD_MEMORY_MB
    timeout_s = timeout_s or BUILD_TIMEOUT_S
    with tempfile.TemporaryDirectory(prefix="facts-build-") as work:
        source = Path(work) / "model.ifc"
        source.write_bytes(data)
        child = [*CHILD, str(source), model, str(out.resolve())]  # the child runs in BACKEND
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
            out.unlink(missing_ok=True)
            raise InvalidInputError(
                f"the model takes more than {timeout_s:g} s for its facts"
            ) from error
    errors = done.stderr.decode(errors="replace")
    if done.returncode == 0:
        return
    out.unlink(missing_ok=True)
    if done.returncode == NOT_READ:
        raise InvalidInputError(errors.strip().splitlines()[-1] if errors.strip() else "not read")
    if done.returncode < 0 or _out_of_memory(errors):
        raise InvalidInputError(f"the model needs more than {memory_mb} MB for its facts")
    raise RuntimeError(f"the facts builder exited {done.returncode}: {errors[-2000:]}")


def store_facts(
    folder: Path, name: str, data: bytes, build: Build = build_apart, sha256: str | None = None
) -> Path:
    """The sheet of the model `name` with these bytes built and stored where StoredFacts reads it
    (`<sha256>-<CODE>.json`; `sha256` when the caller has it), written whole or not at all."""
    out = folder / f"{sha256 or hashlib.sha256(data).hexdigest()}-{CODE}.json"
    folder.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(".part")  # a build killed mid-write leaves no half sheet
    build(data, PurePosixPath(name).stem, part)
    part.replace(out)
    return out


def _in_background(job: Callable[[], None]) -> None:
    threading.Thread(target=job, name="facts-build", daemon=True).start()


class StoredFacts:
    def __init__(self, folder: Path, build: Build = build_apart, start: Start = _in_background):
        self._folder = folder
        self._builder = build
        self._start = start
        self._lock = threading.Lock()  # guards the two sets
        self._one = threading.Lock()  # one build at a time: two at once would double the memory
        self._busy: set[str] = set()  # sha256s in flight
        self._failed: set[str] = set()

    def facts(self, sha256: str, path: str, data: Callable[[], bytes]) -> FactSheet | None:
        """The stored sheet of the model with this content, or None (a build starts when none is
        stored, in flight or failed). Only a building model (.ifc) has one."""
        if PurePosixPath(path).suffix.lower() != ".ifc":
            return None
        out = self._folder / f"{sha256}-{CODE}.json"
        if out.is_file():
            try:
                return FactSheet.model_validate_json(out.read_text(encoding="utf-8"))
            except ValueError as error:  # pydantic's ValidationError is one
                log.warning("%s: stored sheet unreadable, built again: %s", sha256[:12], error)
        self._build(sha256, path, data)
        return None

    def start(self, sha256: str, path: str, data: Callable[[], bytes]) -> None:
        """The build of a model's sheet started when none is stored, in flight or failed, without
        reading a stored one: ingest is done with the model, so its first question finds it."""
        stored = (self._folder / f"{sha256}-{CODE}.json").is_file()
        if PurePosixPath(path).suffix.lower() == ".ifc" and not stored:
            self._build(sha256, path, data)

    def reading(self, sha256: str) -> bool:
        """The sheet of the model with this content is being built now."""
        with self._lock:
            return sha256 in self._busy

    def _build(self, sha256: str, path: str, data: Callable[[], bytes]) -> None:
        with self._lock:
            if sha256 in self._busy or sha256 in self._failed:
                return
            self._busy.add(sha256)

        def job() -> None:
            failed = False
            try:
                with self._one:
                    store_facts(self._folder, path, data(), self._builder, sha256)
            except Exception:  # the question was answered without it; said once in the log
                log.warning("%s: no fact sheet built", sha256[:12], exc_info=True)
                failed = True
            with self._lock:
                self._busy.discard(sha256)
                if failed:
                    self._failed.add(sha256)

        self._start(job)


def _cap(limit: int) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def _child(source: str, model: str, out: str) -> int:
    try:
        sheet = read_facts(Path(source).read_bytes(), model)
    except Exception as error:  # ifcopenshell raises its own and plain RuntimeErrors
        print(str(error).replace("\n", " "), file=sys.stderr)
        return NOT_READ
    Path(out).write_text(sheet.model_dump_json(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(_child(*sys.argv[1:4]))
