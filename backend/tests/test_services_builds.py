"""A project's services models built off the request (services-model.md SV-8; QA B4, 2026-11-15):
a services IFC uploaded on its own had no stored model, because only the deploy's
`app.cli services build` made one, so the chat said "This project has no services model". Now the
chat turn starts the build of each missing one in a capped child (as facts_store), and the tools
say it is being built instead of "none"."""

import hashlib
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from test_services_build import (  # pyright: ignore[reportPrivateUsage]
    _architecture,
    _Ifc,
    _services,
)

from app.adapters import services_store
from app.adapters.pipeline_tools import ToolError
from app.adapters.services_agent_tools import (  # pyright: ignore[reportPrivateUsage]
    BUILDING,
    ServicesToolStore,
    _list,
    _ListArgs,
)
from app.adapters.services_agent_tools import NOT_READ as NO_MODEL
from app.adapters.services_store import (
    NO_SERVICES,
    NOT_READ,
    ServicesBuilds,
    ServicesStore,
    _child,  # pyright: ignore[reportPrivateUsage]
    build_apart,
)
from app.core.errors import InvalidInputError


class Jobs:
    """A `start` that keeps the background jobs until the test runs them."""

    def __init__(self) -> None:
        self.waiting: list[Callable[[], None]] = []

    def __call__(self, job: Callable[[], None]) -> None:
        self.waiting.append(job)

    def run(self) -> None:
        while self.waiting:
            self.waiting.pop(0)()


def test_a_missing_model_starts_one_build_and_says_it_is_being_built(tmp_path: Path) -> None:
    built: list[str] = []

    def build(data: bytes, name: str, cache: Path, architecture: bytes | None) -> None:
        built.append(name)
        ServicesStore(cache).build(name, data)

    jobs = Jobs()
    builds = ServicesBuilds(tmp_path / "cache", build=build, start=jobs)
    data = _services(tmp_path / "s.ifc").read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    assert builds.building(sha, "heating.ifc", lambda: data)
    assert builds.building(sha, "heating.ifc", lambda: data)  # in flight: no second build
    assert len(jobs.waiting) == 1 and built == []
    jobs.run()
    assert built == ["heating.ifc"] and ServicesStore(tmp_path / "cache").load(sha) is not None
    assert not builds.building(sha, "heating.ifc", lambda: data) and jobs.waiting == []


def test_a_build_that_fails_is_not_started_again_and_is_not_said_to_be_building(
    tmp_path: Path,
) -> None:
    def build(data: bytes, name: str, cache: Path, architecture: bytes | None) -> None:
        raise InvalidInputError("no distribution element: not a services model")

    jobs = Jobs()
    builds = ServicesBuilds(tmp_path, build=build, start=jobs)
    assert builds.building("abc", "architecture.ifc", lambda: b"x")
    jobs.run()
    assert not builds.building("abc", "architecture.ifc", lambda: b"x") and jobs.waiting == []


def test_the_child_stores_a_services_model_and_nothing_for_a_building_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = tmp_path / "cache"
    services = _services(tmp_path / "s.ifc")
    assert _child(str(services), "heating.ifc", str(cache)) == 0
    sha = hashlib.sha256(services.read_bytes()).hexdigest()
    assert ServicesStore(cache).path(sha).is_file()
    building = _architecture(tmp_path / "a.ifc")
    assert _child(str(building), "architecture.ifc", str(cache)) == NO_SERVICES
    assert "not a services model" in capsys.readouterr().err
    sha = hashlib.sha256(building.read_bytes()).hexdigest()
    assert not ServicesStore(cache).path(sha).is_file()
    (tmp_path / "x.ifc").write_bytes(b"no ifc")
    assert _child(str(tmp_path / "x.ifc"), "x.ifc", str(cache)) == NOT_READ


def test_a_building_model_with_proxies_only_is_no_services_model(tmp_path: Path) -> None:
    """Services demo check (2026-11-15): DigitalHub's architecture IFC lists 150 portless
    IfcBuildingElementProxy items (parking marks, trees, bike stands). The child kept them as a
    services model, so the chat named "Building model 1" among the services models. A proxy
    counts only with ports (an exporter's toilet or socket); a distribution element always."""
    m = _Ifc()
    m.box("IfcSpace", 2.5, 2.0, 0.0, (5.0, 4.0, 2.7), Name="1 Living")
    m.box("IfcBuildingElementProxy", 1.0, 1.0, 0.0, (0.5, 0.5, 6.0), Name="Baum")
    building = m.save(tmp_path / "a.ifc")
    cache = tmp_path / "cache"
    assert _child(str(building), "architecture.ifc", str(cache)) == NO_SERVICES
    sha = hashlib.sha256(building.read_bytes()).hexdigest()
    assert not ServicesStore(cache).path(sha).is_file()
    assert ServicesStore(cache).none_path(sha).is_file()


def test_a_building_model_is_tried_once_not_again_after_a_restart(tmp_path: Path) -> None:
    """Review of #475, Gap A: an architecture IFC has no distribution element, so its child build
    stored nothing and every restart parsed it again (up to 3 GB, 600 s) while the tools said
    "being built" for a model that never comes. The child now leaves a marker per sha256."""
    cache = tmp_path / "cache"
    building = _architecture(tmp_path / "a.ifc")
    assert _child(str(building), "architecture.ifc", str(cache)) == NO_SERVICES
    started: list[str] = []
    jobs = Jobs()
    restarted = ServicesBuilds(cache, build=lambda d, n, c, a: started.append(n), start=jobs)
    sha = hashlib.sha256(building.read_bytes()).hexdigest()
    assert not restarted.building(sha, "architecture.ifc", building.read_bytes)
    assert jobs.waiting == [] and started == []


def test_two_files_are_built_one_at_a_time(tmp_path: Path) -> None:
    """Review of #475, Gap B: two builds at once would double the memory."""
    entered = {"a": threading.Event(), "b": threading.Event()}
    release = threading.Event()
    threads: list[threading.Thread] = []

    def build(data: bytes, name: str, cache: Path, architecture: bytes | None) -> None:
        entered[name].set()
        if name == "a":
            assert release.wait(10)

    def start(job: Callable[[], None]) -> None:
        threads.append(threading.Thread(target=job))
        threads[-1].start()

    builds = ServicesBuilds(tmp_path, build=build, start=start)
    assert builds.building("sha-a", "a", lambda: b"")
    assert entered["a"].wait(10)
    assert builds.building("sha-b", "b", lambda: b"")
    assert not entered["b"].wait(0.5)  # held behind a's build
    release.set()
    for thread in threads:
        thread.join(10)
    assert entered["b"].is_set()


def test_the_capped_child_builds_the_model_the_api_reads(tmp_path: Path) -> None:
    data = _services(tmp_path / "s.ifc").read_bytes()
    build_apart(data, "heating.ifc", tmp_path / "cache")
    model = ServicesStore(tmp_path / "cache").load(hashlib.sha256(data).hexdigest())
    assert model is not None and model.elements
    assert not model.rooms  # no architecture model: no room
    building = _architecture(tmp_path / "a.ifc").read_bytes()
    build_apart(data, "heating.ifc", tmp_path / "with", building)  # #475 review S2
    model = ServicesStore(tmp_path / "with").load(hashlib.sha256(data).hexdigest())
    assert model is not None and model.rooms


@pytest.mark.parametrize("scope", [True, False], ids=["systemd-scope", "rlimit"])
def test_a_build_is_held_to_its_memory_and_time_budget(
    scope: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if scope and not services_store.has_systemd_scope():
        pytest.skip("no systemd user manager here")
    monkeypatch.setattr(services_store, "has_systemd_scope", lambda: scope)
    data = _services(tmp_path / "s.ifc").read_bytes()
    with pytest.raises(InvalidInputError, match="needs more than 1 MB"):
        build_apart(data, "heating.ifc", tmp_path / "cache", memory_mb=1)  # less than Python
    with pytest.raises(InvalidInputError, match=r"more than 0\.001 s"):
        build_apart(data, "heating.ifc", tmp_path / "cache", timeout_s=0.001)
    assert not list((tmp_path / "cache").glob("*.json.gz"))


def test_the_tools_say_a_model_is_being_built_not_that_there_is_none() -> None:
    store = ServicesToolStore({}, building=("a1b2c3d4e5f60708",))
    with pytest.raises(ToolError, match=BUILDING):
        store.model("a1b2c3d4e5f60708")
    with pytest.raises(ToolError, match=f"{NO_MODEL}; {BUILDING}: a1b2c3d4e5f60708"):
        _list(store, _list_args())
    with pytest.raises(ToolError) as nothing:
        _list(ServicesToolStore({}), _list_args())
    assert BUILDING not in str(nothing.value)


def _list_args() -> _ListArgs:
    return _ListArgs()
