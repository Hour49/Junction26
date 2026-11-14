"""Fixtures of the ingest tests: the real adapters on a temporary projects folder, run inside
`start` (no thread) unless a test passes its own runner, with fixed ids and clock-free times."""

import itertools
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from app.adapters.archive import (
    DiskProjectStore,
    ExifFrame,
    FileProbe,
    InlineRunner,
    NoRectifier,
    ZipUnpacker,
)
from app.composition import Pipeline, build_pipeline
from app.composition import readers as readers_of
from app.core.ingest.ports import ContentProbe, Rectifier, Runner
from app.core.ingest.service import IngestService
from app.core.pipeline.ports import DrawingFiles, Extractor
from app.settings import Settings

MakeService = Callable[..., IngestService]


@pytest.fixture
def make_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MakeService:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change test results
    settings = Settings()
    ids = (f"p{n:03d}" for n in itertools.count(1))
    days = (f"2026-11-14T00:{n // 60:02d}:{n % 60:02d}+00:00" for n in itertools.count())

    def make(
        root: Path = tmp_path / "projects",
        runner: Runner | None = None,
        raster: Callable[[DrawingFiles], Extractor] | None = None,
        unpacker: ZipUnpacker | None = None,
        rectifier: Rectifier | None = None,
        clock: Callable[[], float] | None = None,
        probe: ContentProbe | None = None,
    ) -> IngestService:
        store = DiskProjectStore(root)

        def readers(project_id: str) -> Pipeline:
            pipeline = build_pipeline(settings, store.files_dir(project_id))
            if raster is None:
                return pipeline
            reader = raster(pipeline.files)  # the raster reader, over this project's files
            return replace(pipeline, extractors={**pipeline.extractors, "raster": reader})

        return IngestService(
            unpacker=unpacker or ZipUnpacker(),
            probe=probe or FileProbe(),
            frame=ExifFrame(),
            rectifier=rectifier or NoRectifier(),
            store=store,
            readers=readers,
            reader_names={**readers_of(settings), "raster": "test" if raster else "hello"},
            runner=runner or InlineRunner(),
            clock=clock or (lambda: 0.0),
            now=lambda: next(days),
            new_id=lambda: next(ids),
        )

    return make
