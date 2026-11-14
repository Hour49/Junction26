"""The services of an IFC model as plain data for app/core/services: every distribution element
with its place, the places of its connection ports, the elements its ports connect to and the
systems it belongs to; the model's storeys with their heights; and where each space is, so a
plan sheet of the building can be laid over the model (services.model.fit_frame).

What an element is (kind, group, discipline, size, systems) is read by
app/adapters/ifc_model/facts_mep.mep_elements; this module adds the geometry and the graph.
Nothing is meshed but the spaces: an element's place is its placement, a run's centre line is
the line between its two ports. On the dataset's service models (1,000-1,800 elements) that
takes about a second and 150-200 MB a model; ifcopenshell does not give that memory back
(objects.py), so `ServiceFiles` keeps the plain data of a few models and reads none twice.

A model's lane is what its classes say it mostly is (core/discipline.discipline_from_census): a
heating model's pipes are heating, though a pipe alone could be plumbing. Only a model that
carries two service disciplines is split element by element.
"""

import logging
import os
import pickle
import resource
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.system

from app.adapters.ifc_model.census import entity_census
from app.adapters.ifc_model.facts_mep import MepElement, mep_elements
from app.adapters.ifc_model.glb import (
    _SCOPE,  # pyright: ignore[reportPrivateUsage]
    _out_of_memory,  # pyright: ignore[reportPrivateUsage]
    has_systemd_scope,
)
from app.adapters.ifc_model.objects import (
    _solid,  # pyright: ignore[reportPrivateUsage]
    _unit_scales,  # pyright: ignore[reportPrivateUsage]
)
from app.core.discipline import discipline_from_census
from app.core.errors import InvalidInputError
from app.core.ifc_facts import Discipline
from app.core.services.model import LANES, Point2, Point3, ServiceElement

log = logging.getLogger(__name__)

MAX_BYTES = 150_000_000  # a larger model is not followed: it would take over a GB to read
MIXED_SHARE = 0.2  # a second service discipline with this share: the model is split by element
FILES_KEPT = 8
# A read runs in a child process with its own budget (S2): ifcopenshell keeps what it parsed until
# its process ends, so in the API process 16 distinct models grew it by 2.9 GB though only 8 were
# kept. The largest dataset model under MAX_BYTES peaked at 0.8 GB and read in 12 s.
READ_MEMORY_MB = 3000
READ_TIMEOUT_S = 120.0
CHILD = [sys.executable, "-m", __name__]  # the reader; run with `-m` from the backend folder
BACKEND = Path(__file__).resolve().parents[2]
NOT_READ = 2  # the child's exit code for a file it refuses (InvalidInputError), its words on stderr


@dataclass(frozen=True)
class ServiceFile:
    storeys: tuple[tuple[str, float], ...]  # name and height in metres, lowest first
    spaces: Mapping[str, Point2]  # GlobalId -> the centre of the space's footprint, in metres
    lanes: tuple[Discipline, ...]  # the service disciplines it carries, most first
    elements: tuple[ServiceElement, ...]  # in the model's own metres


def read_service_file(data: bytes) -> ServiceFile:
    if len(data) > MAX_BYTES:
        raise InvalidInputError(
            f"the model is {len(data) / 1e6:.0f} MB: over {MAX_BYTES / 1e6:.0f} MB is not followed"
        )
    with tempfile.NamedTemporaryFile(suffix=".ifc") as on_disk:
        on_disk.write(data.decode("utf-8", errors="replace").encode())
        on_disk.flush()
        try:
            file: Any = ifcopenshell.open(on_disk.name)
            projects = file.by_type("IfcProject")
        except Exception as error:  # ifcopenshell raises its own and plain RuntimeErrors
            raise InvalidInputError(f"not an IFC file ifcopenshell can read: {error}") from error
    if not projects:
        raise InvalidInputError("not an IFC model: it has no IfcProject, so no units")
    return service_file(file)


def read_apart(
    data: bytes, memory_mb: int | None = None, timeout_s: float | None = None
) -> ServiceFile:
    """`read_service_file` in a child process held to `memory_mb` (READ_MEMORY_MB) and
    `timeout_s` (READ_TIMEOUT_S): the parse's memory goes with the child, the caller keeps only
    the plain data. A file it cannot read, or that needs more, is an InvalidInputError."""
    memory_mb = memory_mb or READ_MEMORY_MB
    timeout_s = timeout_s or READ_TIMEOUT_S
    if len(data) > MAX_BYTES:
        return read_service_file(data)  # its words, without writing the file out
    with tempfile.TemporaryDirectory(prefix="services-read-") as work:
        source = Path(work) / "model.ifc"
        source.write_bytes(data)
        child = [*CHILD, str(source)]
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
            raise InvalidInputError(f"the model takes more than {timeout_s:g} s to read") from error
    errors = done.stderr.decode(errors="replace")
    if done.returncode == 0:
        return pickle.loads(done.stdout)  # our own child's output
    if done.returncode == NOT_READ:
        raise InvalidInputError(errors.strip().splitlines()[-1] if errors.strip() else "not read")
    if done.returncode < 0 or _out_of_memory(errors):
        raise InvalidInputError(f"the model needs more than {memory_mb} MB to read")
    raise RuntimeError(f"the services reader exited {done.returncode}: {errors[-2000:]}")


def _cap(limit: int) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def _child(path: str) -> int:
    try:
        read = read_service_file(Path(path).read_bytes())
    except InvalidInputError as error:
        print(str(error).replace("\n", " "), file=sys.stderr)
        return NOT_READ
    sys.stdout.buffer.write(pickle.dumps(read))
    return 0


def service_file(file: Any) -> ServiceFile:
    """`file`: an opened `ifcopenshell.file`."""
    scale = _unit_scales(file)["LENGTHUNIT"]
    ranked: list[tuple[Discipline, float]] = [
        (discipline, share)
        for discipline, share in discipline_from_census(entity_census(file))
        if discipline in LANES
    ]
    whole = sum(share for _, share in ranked)
    lanes: tuple[Discipline, ...] = tuple(
        d for d, share in ranked if whole and share / whole >= MIXED_SHARE
    )
    elements: list[ServiceElement] = []
    if ranked:
        top = ranked[0][0]
        for read in mep_elements(file):
            entity = file.by_guid(read.guid)
            if not entity.is_a("IfcDistributionElement") or entity.ObjectPlacement is None:
                continue
            lane = read.discipline if len(lanes) > 1 and read.discipline in lanes else top
            elements.append(_element(entity, read, lane, scale))
    storeys = sorted(
        (
            (storey.Name or "", round(float(storey.Elevation or 0.0) * scale, 4))
            for storey in file.by_type("IfcBuildingStorey")
        ),
        key=lambda storey: storey[1],
    )
    return ServiceFile(
        storeys=tuple(storeys),
        spaces=_space_centres(file),
        lanes=lanes or tuple[Discipline, ...](d for d, _ in ranked[:1]),
        elements=tuple(elements),
    )


def _element(entity: Any, read: MepElement, lane: Discipline, scale: float) -> ServiceElement:
    ports = ifcopenshell.util.system.get_ports(entity)
    neighbours: list[str] = []
    for port in ports:
        other = ifcopenshell.util.system.get_connected_port(port)
        owner = None if other is None else ifcopenshell.util.system.get_port_element(other)
        if owner is not None:
            neighbours.append(owner.GlobalId)
    return ServiceElement(
        guid=read.guid,
        lane=lane,
        kind=read.kind,
        group=read.group,
        predefined=read.predefined,
        type_name=read.type_name,
        size=read.size,
        systems=tuple(sorted(read.systems)),
        storey=read.storey,
        at=_at(entity.ObjectPlacement, scale),
        ports=tuple(_at(p.ObjectPlacement, scale) for p in ports if p.ObjectPlacement is not None),
        neighbours=tuple(dict.fromkeys(neighbours)),
    )


def _at(placement: Any, scale: float) -> Point3:
    matrix = ifcopenshell.util.placement.get_local_placement(placement)
    return (
        round(float(matrix[0][3]) * scale, 4),
        round(float(matrix[1][3]) * scale, 4),
        round(float(matrix[2][3]) * scale, 4),
    )


def _space_centres(file: Any) -> dict[str, Point2]:
    spaces = file.by_type("IfcSpace")
    if not spaces:
        return {}
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    found: dict[str, Point2] = {}
    for space in spaces:
        solid = _solid(space, settings)
        if solid is not None and not solid.footprint.is_empty:
            centre = solid.footprint.centroid
            found[space.GlobalId] = (round(centre.x, 4), round(centre.y, 4))
    return found


def _in_background(job: Callable[[], None]) -> None:
    threading.Thread(target=job, name="services-read-ahead", daemon=True).start()


class ServiceFiles:
    """Read models by content hash, the last few kept."""

    def __init__(self, read: Callable[[bytes], ServiceFile] | None = None) -> None:
        self._read = read or read_apart
        self._kept: dict[str, ServiceFile] = {}
        self._lock = threading.Lock()
        self._asked: set[str] = set()  # read ahead once: by content hash
        self._warm_lock = threading.Lock()

    def file(self, sha256: str, data: Callable[[], bytes]) -> ServiceFile:
        with self._lock:  # one model is read at a time: two at once would double the memory
            if sha256 not in self._kept:
                if len(self._kept) >= FILES_KEPT:
                    del self._kept[next(iter(self._kept))]
                self._kept[sha256] = self._read(data())
            return self._kept[sha256]

    def warm(
        self,
        models: Sequence[tuple[str, Callable[[], bytes]]],
        start: Callable[[Callable[[], None]], None] = _in_background,
    ) -> None:
        """Reads the models that were never asked for, off the request (`start` runs the job),
        so the first proposal of a project does not wait for them. A model that cannot be read
        is left for the follow-up to report."""
        with self._warm_lock:
            new = [(sha256, data) for sha256, data in models if sha256 not in self._asked]
            self._asked.update(sha256 for sha256, _ in new)
        if not new:
            return

        def job() -> None:
            for sha256, data in new:
                try:
                    self.file(sha256, data)
                except Exception:  # the follow-up reads it again and says why
                    log.warning("service model %s not read ahead", sha256[:12], exc_info=True)

        start(job)


if __name__ == "__main__":
    # through the module's own name, so what is pickled is app.adapters.ifc_services.ServiceFile
    from app.adapters.ifc_services import _child as child  # pyright: ignore[reportPrivateUsage]

    sys.exit(child(sys.argv[1]))
