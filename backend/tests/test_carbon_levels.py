"""CARBON_LEVELS=demote (brief r8 BG; integ's pre-registered rule, .agents/exp/integ.md AW
pre-registration 2): Gemini Carbon reads each raster drawing beside its reader, never counted, and
a Medium answer whose question Carbon answers with another value becomes Low. Carbon agreeing or
refusing changes nothing; a check that failed changes nothing and says so."""

import logging
from pathlib import Path
from typing import Any

import pytest

from app.adapters.carbon import CarbonChecked, CarbonExtractor
from app.composition import build_ingest, build_pipeline, uses_keys
from app.core.drawing.model import CarbonCheck, Drawing, Element, Page
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.review.check import CARBON_DEMOTED, Level, carbon_checked
from app.settings import Settings
from tests.test_levels import DOORS, ROOMS, SCAN, asked, made

KEY = "test-key-0123456789"
BOX = (0.5, 0.5, 0.6, 0.6)
THREE = (*DOORS, Element(id="e3", class_="door", page=1, box=BOX))
MEDIUM = 0.5  # the doors' score: Medium from 0.4, certified at 0.8 (tests/test_levels.py POLICY)


def checked(**fields: Any) -> Drawing:
    return SCAN.model_copy(update={"carbon_check": CarbonCheck(**fields)})


def test_a_medium_answer_carbon_counts_differently_becomes_low() -> None:
    found = asked(score=MEDIUM, drawing=checked(read=("door", "room"), elements=THREE))
    assert found.answer.answer == 2  # the answer is the reader's, never Carbon's
    assert made(found) == ("low", "carbon")
    assert found.level is not None and "Carbon" not in found.level.text  # QA R4-C10
    assert "a second AI reader counted 3 here" in found.level.text
    assert f"({CARBON_DEMOTED.exact} of {CARBON_DEMOTED.units})" in found.level.text
    assert found.check is not None  # still asks for the double-check it asked for


@pytest.mark.parametrize(
    "carbon",
    [
        {"read": ("door", "room"), "elements": DOORS},  # agrees: 2 doors
        {"read": ("window", "room")},  # refuses: it did not count doors
    ],
    ids=["agrees", "refuses"],
)
def test_carbon_agreeing_or_refusing_changes_nothing(carbon: dict[str, Any]) -> None:
    alone = asked(score=MEDIUM)
    found = asked(score=MEDIUM, drawing=checked(**carbon))
    assert made(alone) == ("medium", "score")
    assert found.level == alone.level and found.answer == alone.answer


def test_a_failed_check_keeps_the_level_and_says_carbon_did_not_check() -> None:
    alone = asked(score=MEDIUM)
    found = asked(score=MEDIUM, drawing=checked(failed="not read: the page call failed: HTTP 503"))
    assert alone.level is not None and found.level is not None
    assert made(found) == ("medium", "score")
    assert found.level.text == (
        f"{alone.level.text} A second AI reader did not check it: not read: the page call "
        "failed: HTTP 503."
    )


@pytest.mark.parametrize(("score", "level"), [(0.9, "high"), (0.1, "low")])
def test_carbon_moves_only_medium(score: float, level: str) -> None:
    alone = asked(score=score)
    found = asked(score=score, drawing=checked(read=("door", "room"), elements=THREE))
    assert found.level is not None and found.level.level == level
    assert found.level == alone.level


def test_carbon_on_a_room_question_reads_its_own_rooms() -> None:
    level = Level(level="medium", basis="score", text="Medium.")
    check = CarbonCheck(read=("room",), rooms=ROOMS)
    assert carbon_checked(level, check, 1, 1) == level
    low = carbon_checked(level, check, 2.0, 1)
    assert low.level == "low" and "counted 2 here" in low.text


# --- the adapter --------------------------------------------------------------------------------


class Reads:
    def __init__(self, found: Extracted | Exception) -> None:
        self.found = found

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        if isinstance(self.found, Exception):
            raise self.found
        return self.found


SHIPPED = Extracted(method="detector", scale=SCAN.scale, elements=DOORS, read=("door",))
SOURCE = DrawingFile(path="plan.png", kind="png", size=1, sha256="0" * 64)
SHEET = Sheet(file=SOURCE, pages=(Page(page=1, width=100, height=100, unit="px"),))


def test_the_check_keeps_the_reader_s_drawing_and_carbon_s_reading_beside_it() -> None:
    carbon = Extracted(method="detector", scale=SCAN.scale, elements=THREE, read=("door", "room"))
    found = CarbonChecked(Reads(SHIPPED), Reads(carbon)).extract(SOURCE, SHEET)
    assert found.model_copy(update={"carbon_check": None, "steps": ()}) == SHIPPED
    assert found.carbon_check == CarbonCheck(read=("door", "room"), elements=THREE)


@pytest.mark.parametrize(
    ("carbon", "why"),
    [
        (
            Extracted(method="detector", scale=SCAN.scale, read=(),
                      notes=("carbon: not read: the page call failed: HTTP 503",)),
            "not read: the page call failed: HTTP 503",
        ),
        (OSError("cannot identify image file"), "the image could not be opened: OSError"),
    ],
    ids=["failed-call", "unopenable"],
)  # fmt: skip
def test_a_failed_check_is_kept_as_failed_and_logged(
    carbon: Extracted | Exception, why: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.adapters.carbon"):
        found = CarbonChecked(Reads(SHIPPED), Reads(carbon)).extract(SOURCE, SHEET)
    assert found.carbon_check == CarbonCheck(failed=why)
    assert f"Carbon did not check plan.png: {why}" in caplog.text


@pytest.mark.parametrize("error", [ValueError("bad"), KeyError("plans"), RuntimeError("x")])
def test_any_error_in_the_check_keeps_the_reader_s_drawing(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    """codecheck's S1 (.agents/qa/r9/review-274.md): an error other than OSError from Carbon set
    the file aside, so the reader's own drawing was lost for a check that is never counted."""
    with caplog.at_level(logging.ERROR, logger="app.adapters.carbon"):
        found = CarbonChecked(Reads(SHIPPED), Reads(error)).extract(SOURCE, SHEET)
    assert found.model_copy(update={"carbon_check": None, "steps": ()}) == SHIPPED
    assert found.carbon_check == CarbonCheck(failed=f"the check failed: {type(error).__name__}")
    assert "Carbon check of plan.png raised" in caplog.text and "Traceback" in caplog.text


def test_off_writes_the_drawing_as_before() -> None:
    assert "carbon_check" not in SCAN.model_dump_json(by_alias=True)
    assert "carbon_check" in checked(failed="x").model_dump_json(by_alias=True)


# --- wiring -------------------------------------------------------------------------------------


def settings_with(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: str) -> Settings:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    values = {"EXTRACTOR_RASTER": "composite", "RASTER_COMPONENTS": "plans=one-plan",
              "GEMINI_API_KEY": KEY, **env}  # fmt: skip
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return Settings()


def test_demote_wraps_the_raster_reader_in_the_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = settings_with(monkeypatch, tmp_path, CARBON_LEVELS="demote")
    raster = build_pipeline(settings, tmp_path).extractors["raster"]
    check = raster._inner  # pyright: ignore[reportAttributeAccessIssue]
    assert isinstance(check, CarbonChecked)
    assert isinstance(check._carbon, CarbonExtractor)  # pyright: ignore[reportPrivateUsage]
    assert build_pipeline(settings, tmp_path).carbon_read is None  # nothing is flagged
    assert uses_keys(settings)
    names = build_ingest(settings, tmp_path / "projects", background=False)._names  # pyright: ignore[reportPrivateUsage]
    assert names["carbon_levels"].startswith("demote:")


def test_off_leaves_the_raster_reader_and_the_cache_names_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = settings_with(monkeypatch, tmp_path)
    raster = build_pipeline(settings, tmp_path).extractors["raster"]
    assert not isinstance(raster._inner, CarbonChecked)  # pyright: ignore[reportAttributeAccessIssue]
    names = build_ingest(settings, tmp_path / "projects", background=False)._names  # pyright: ignore[reportPrivateUsage]
    assert "carbon_levels" not in names


def test_demote_needs_the_composite_raster_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = settings_with(monkeypatch, tmp_path, EXTRACTOR_RASTER="hello",
                             CARBON_LEVELS="demote")  # fmt: skip
    with pytest.raises(InvalidInputError, match="CARBON_LEVELS needs EXTRACTOR_RASTER=composite"):
        build_pipeline(settings, tmp_path)
