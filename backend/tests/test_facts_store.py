"""The chat's fact sheets of IFC models (adapters/ifc_model/facts_store.py): read from disk by the
file's sha256; on a miss one capped child build starts in the background (one at a time, one per
sha256 in flight) and the question is answered as today. The API process never parses a model."""

import hashlib
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from app.adapters.ifc_model import facts_store
from app.adapters.ifc_model.facts_source import CODE
from app.adapters.ifc_model.facts_store import StoredFacts, build_apart
from app.cli import main
from app.core.errors import InvalidInputError
from app.core.ifc_facts import FactSheet
from scripts.make_sample_archive import ifc_model

SHEET = FactSheet(model="house", disciplines=["architecture"], facts=[])


class Jobs:
    """A `start` that keeps the background jobs until the test runs them."""

    def __init__(self) -> None:
        self.waiting: list[Callable[[], None]] = []

    def __call__(self, job: Callable[[], None]) -> None:
        self.waiting.append(job)

    def run(self) -> None:
        while self.waiting:
            self.waiting.pop(0)()


def store(tmp_path: Path, built: list[str]) -> tuple[StoredFacts, Jobs]:
    def build(data: bytes, model: str, out: Path) -> None:
        built.append(model)
        out.write_text(SHEET.model_dump_json(), encoding="utf-8")

    jobs = Jobs()
    return StoredFacts(tmp_path, build=build, start=jobs), jobs


def test_a_miss_starts_one_build_and_a_second_ask_while_it_runs_starts_none(tmp_path: Path) -> None:
    built: list[str] = []
    facts, jobs = store(tmp_path, built)
    assert facts.facts("abc", "model/house.ifc", lambda: b"ifc") is None  # answered as today
    assert facts.facts("abc", "model/house.ifc", lambda: b"ifc") is None
    assert len(jobs.waiting) == 1 and built == []
    jobs.run()
    assert built == ["house"]
    assert facts.facts("abc", "model/house.ifc", lambda: b"ifc") == SHEET  # stored: no build
    assert jobs.waiting == [] and (tmp_path / f"abc-{CODE}.json").is_file()


def test_a_build_that_fails_is_not_started_again_in_this_process(tmp_path: Path) -> None:
    def build(data: bytes, model: str, out: Path) -> None:
        raise RuntimeError("not an IFC file")

    jobs = Jobs()
    facts = StoredFacts(tmp_path, build=build, start=jobs)
    assert facts.facts("bad", "a.ifc", lambda: b"x") is None
    jobs.run()
    assert facts.facts("bad", "a.ifc", lambda: b"x") is None and jobs.waiting == []


def test_start_builds_once_without_reading_and_says_while_it_is_reading(tmp_path: Path) -> None:
    """QA research-lead MUST-FIX: the build starts when ingest is done with the model, so the
    first question finds its sheet; while it runs, `reading` says so."""
    built: list[str] = []
    facts, jobs = store(tmp_path, built)
    facts.start("abc", "model/house.ifc", lambda: b"ifc")
    facts.start("abc", "model/house.ifc", lambda: b"ifc")  # in flight: no second build
    assert len(jobs.waiting) == 1 and facts.reading("abc") and not facts.reading("other")
    jobs.run()
    assert built == ["house"] and not facts.reading("abc")
    facts.start("abc", "model/house.ifc", lambda: b"ifc")  # stored: nothing to do
    facts.start("def", "plans/flat-a.pdf", lambda: b"pdf")  # not a model
    assert jobs.waiting == []


def test_only_a_building_model_has_a_sheet(tmp_path: Path) -> None:
    facts, jobs = store(tmp_path, [])
    assert facts.facts("abc", "plans/flat-a.pdf", lambda: b"pdf") is None and jobs.waiting == []


def test_the_child_builds_the_sheet_a_model_gives(tmp_path: Path) -> None:
    out = tmp_path / "sheet.json"
    build_apart(ifc_model(), "house", out)
    sheet = FactSheet.model_validate_json(out.read_text(encoding="utf-8"))
    assert sheet.model == "house" and any(f.topic == "wall.count" for f in sheet.facts)


def test_a_relative_out_is_the_callers_not_the_childs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """QA ifc-ask: IFC_FACTS_CACHE is relative by default and the child runs in backend/, so an
    API started from another folder sent its sheet elsewhere."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cache").mkdir()
    build_apart(ifc_model(), "house", Path("cache/sheet.json"))
    assert (tmp_path / "cache" / "sheet.json").is_file()


@pytest.mark.parametrize("scope", [True, False], ids=["systemd-scope", "rlimit"])
def test_a_build_is_held_to_its_memory_and_time_budget(
    scope: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As ifc_services' reader (#399): a capped scope where systemd runs one, an address-space
    limit where it does not (CI). Over either budget the build fails in words and stores nothing."""
    if scope and not facts_store.has_systemd_scope():
        pytest.skip("no systemd user manager here")
    monkeypatch.setattr(facts_store, "has_systemd_scope", lambda: scope)
    out = tmp_path / "sheet.json"
    with pytest.raises(InvalidInputError, match="needs more than 1 MB"):
        build_apart(ifc_model(), "house", out, memory_mb=1)  # less than Python itself
    with pytest.raises(InvalidInputError, match=r"more than 0\.001 s"):
        build_apart(ifc_model(), "house", out, timeout_s=0.001)
    assert not out.exists()


def test_real_threads_build_one_model_at_a_time(tmp_path: Path) -> None:
    running: list[int] = []
    most: list[int] = [0]
    lock = threading.Lock()

    def build(data: bytes, model: str, out: Path) -> None:
        with lock:
            running.append(1)
            most[0] = max(most[0], len(running))
        time.sleep(0.05)
        out.write_text(SHEET.model_dump_json(), encoding="utf-8")
        with lock:
            running.pop()

    facts = StoredFacts(tmp_path, build=build)  # the real background start: one thread per miss
    for n in range(4):
        assert facts.facts(f"sha{n}", "m.ifc", lambda: b"ifc") is None
    for _ in range(200):
        if len(list(tmp_path.glob("*.json"))) == 4:
            break
        time.sleep(0.02)
    assert len(list(tmp_path.glob("*.json"))) == 4 and most[0] == 1


def test_the_cli_fills_the_cache_with_the_file_the_api_reads(tmp_path: Path) -> None:
    model = tmp_path / "house.ifc"
    model.write_bytes(ifc_model())
    cache = tmp_path / "cache"
    assert main(["facts", "build", "--model", str(model), "--cache", str(cache)]) == 0
    sha256 = hashlib.sha256(model.read_bytes()).hexdigest()
    assert (cache / f"{sha256}-{CODE}.json").is_file()

    def never(job: Callable[[], None]) -> None:
        raise AssertionError("a stored sheet starts no build")

    sheet = StoredFacts(cache, start=never).facts(sha256, "house.ifc", lambda: b"")
    assert sheet is not None and any(f.topic == "wall.count" for f in sheet.facts)
