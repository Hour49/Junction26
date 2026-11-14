"""The chat's fact sheets of IFC models (adapters/ifc_model/facts_store.py): read from disk by the
file's sha256; on a miss one capped child build starts in the background (one at a time, one per
sha256 in flight) and the question is answered as today. The API process never parses a model."""

from collections.abc import Callable
from pathlib import Path

from app.adapters.ifc_model.facts_source import CODE
from app.adapters.ifc_model.facts_store import StoredFacts, build_apart
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


def test_only_a_building_model_has_a_sheet(tmp_path: Path) -> None:
    facts, jobs = store(tmp_path, [])
    assert facts.facts("abc", "plans/flat-a.pdf", lambda: b"pdf") is None and jobs.waiting == []


def test_the_child_builds_the_sheet_a_model_gives(tmp_path: Path) -> None:
    out = tmp_path / "sheet.json"
    build_apart(ifc_model(), "house", out)
    sheet = FactSheet.model_validate_json(out.read_text(encoding="utf-8"))
    assert sheet.model == "house" and any(f.topic == "wall.count" for f in sheet.facts)
