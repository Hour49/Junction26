"""Reader settings that cannot be built fail when ingest is built (app startup), naming the
setting, instead of setting every file of each upload aside."""

from pathlib import Path

import pytest

from app.composition import build_ingest
from app.core.errors import InvalidInputError
from app.settings import Settings

NO_ARM = "elements=detector:no-such-arm,plans=one-plan"


def test_a_raster_component_that_does_not_build_fails_at_startup_naming_the_setting(
    tmp_path: Path,
) -> None:
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        extractor_raster="composite",
        raster_components=NO_ARM,
    )
    with pytest.raises(InvalidInputError, match=r"^RASTER_COMPONENTS='elements=detector:no-such"):
        build_ingest(settings, tmp_path, background=False)


def test_readers_that_build_still_start(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        extractor_raster="composite",
        raster_components="plans=one-plan",
    )
    build_ingest(settings, tmp_path, background=False).close()
