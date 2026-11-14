"""Ingest keeps the project's evidence index in step (decision 0012): after the project is judged,
after a person's overrule, and never at the cost of the ingest itself."""

from dataclasses import dataclass, field
from pathlib import Path

from conftest import MakeService
from test_ingest_triage import PHOTO, PLAN, SCAN, file_of, zipped
from triage_fakes import FakeClassifier, FakeDescriber, WordJudge, steps

from app.adapters.evidence.store import SqliteEvidenceIndex
from app.core.evidence.model import EvidenceSource, Passage
from app.core.ingest.model import Overrule, ProjectStatus


@dataclass
class Recorder:
    statuses: list[ProjectStatus] = field(default_factory=list[ProjectStatus])

    def update(self, status: ProjectStatus) -> None:
        self.statuses.append(status)


class Broken:
    def update(self, status: ProjectStatus) -> None:
        raise RuntimeError("disk full")


def triage() -> object:
    classifier = FakeClassifier({SCAN: "other_drawing", PHOTO: "not_drawing"})
    describer = FakeDescriber(
        {SCAN: ("the south elevation of a house", ("Küche",)), PHOTO: ("a cat on a sofa", ())}
    )
    return steps(classifier, describer, WordJudge())


FILES = {"plan.pdf": PLAN, "elevation.png": SCAN, "cat.jpg": PHOTO}


def test_the_index_gets_the_judged_status_once_the_project_is_done(
    make_service: MakeService,
) -> None:
    index = Recorder()
    ingest = make_service(triage=triage(), evidence=index)
    status = ingest.wait(ingest.start("site.zip", zipped(FILES)))
    (indexed,) = index.statuses
    assert indexed.state == "done"
    elevation = file_of(indexed, "elevation.png").triage
    assert elevation is not None and elevation.verdict == "related"  # judged before indexing
    assert indexed == status


def test_an_overrule_updates_the_index_with_the_persons_verdict(
    make_service: MakeService,
) -> None:
    index = Recorder()
    ingest = make_service(triage=triage(), evidence=index)
    status = ingest.wait(ingest.start("site.zip", zipped(FILES)))
    cat = file_of(status, "cat.jpg")
    call = Overrule(verdict="related", by="a person", at="2026-11-14T00:00:00+00:00")
    ingest.overrule(status.id, cat.id, call)
    assert len(index.statuses) == 2
    found = file_of(index.statuses[-1], "cat.jpg").triage
    assert found is not None and found.verdict == "related"


def test_an_index_that_fails_never_fails_the_ingest(make_service: MakeService) -> None:
    ingest = make_service(triage=triage(), evidence=Broken())
    status = ingest.wait(ingest.start("site.zip", zipped(FILES)))
    assert status.state == "done"
    cat = file_of(status, "cat.jpg")
    call = Overrule(verdict="related", by="a person", at="2026-11-14T00:00:00+00:00")
    assert ingest.overrule(status.id, cat.id, call).triage is not None


def test_no_index_is_ingest_as_before(make_service: MakeService) -> None:
    ingest = make_service(triage=triage())
    assert ingest.wait(ingest.start("site.zip", zipped(FILES))).state == "done"


def summary(source: EvidenceSource) -> list[Passage]:
    return [Passage(part="summary", n=0, text=source.description.subject)]


def test_end_to_end_the_described_elevation_is_found_in_the_projects_sqlite(
    make_service: MakeService, tmp_path: Path
) -> None:
    root = tmp_path / "projects"
    index = SqliteEvidenceIndex(root, summary, None)
    ingest = make_service(root=root, triage=triage(), evidence=index)
    status = ingest.wait(ingest.start("site.zip", zipped(FILES)))
    (hit,) = index.bm25(status.id, "elevation", 5, frozenset({"related", "unsure", None}))
    found = index.passage(status.id, hit)
    assert found is not None and found[1].path == "elevation.png"
    assert index.bm25(status.id, "plan", 5, frozenset({"related", "unsure", None})) == []
