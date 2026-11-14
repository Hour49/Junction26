"""`expected_drawings` while a project runs (QA R4-a-1): screen 2 shows "Drawings ready n /
expected" from every poll, so each status the run saves must give a number that is never above
the final one and never drops: unknown (None) until the files are grouped, then the final count."""

from collections.abc import Mapping
from pathlib import Path

from conftest import MakeService

from app.adapters.archive import DiskProjectStore
from app.api.projects import drawings_of
from app.api.views import expected_drawings_of
from app.core.ingest.model import FileTrace, ProjectStatus
from scripts.make_sample_archive import build_archive


class Recording(DiskProjectStore):
    """The store, keeping every status the run saves (what a poll can read)."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.saved: list[ProjectStatus] = []

    def save_project(self, status: ProjectStatus, traces: Mapping[str, FileTrace]) -> None:
        self.saved.append(status)
        super().save_project(status, traces)


def test_expected_drawings_never_overshoots_nor_drops_while_the_sample_runs(
    make_service: MakeService, tmp_path: Path
) -> None:
    store = Recording(tmp_path / "projects")
    ingest = make_service(store=store)
    final = ingest.status(ingest.start("sample-project.zip", build_archive()))
    assert final.state == "done"
    expected = expected_drawings_of(final)
    assert expected == len(drawings_of(final)) == 5
    seen = [expected_drawings_of(status) for status in store.saved]
    known = [n for n in seen if n is not None]
    assert known, seen
    assert max(known) == expected, seen  # never above the final count
    assert known == sorted(known), seen  # never drops
