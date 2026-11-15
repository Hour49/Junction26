"""A Carbon reply read from the cache is counted as a hit on the calling thread, so the Carbon
reader and check steps say so (detail's audit of the real run: "Gemini Carbon reader (things
drawn) 15.7 ms" with no word of the cache). Only a cached file that parses is a hit: a paid call,
a failed or unpaid call and a cached file that does not parse are not. What is read, charged and
counted as failed stays as it was. Synthetic."""

from pathlib import Path

import pytest
from test_ingest_carbon import FakeCarbon, page_form, page_image, tile_form

from app.adapters.carbon import CarbonChecked, CarbonReader
from app.core import cost
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.steps import timed
from tests.test_carbon_levels import SHEET, SHIPPED, SOURCE, Reads


def read(reader: CarbonReader) -> tuple[Extracted, int, float]:
    """One read of a small page (one page call, one tile call): what it read, its hits on this
    thread and what it charged here."""
    hits, paid = cost.hits(), cost.mark()
    found = reader.read(page_image(900, 700))
    return found, cost.hits_since(hits), cost.since(paid)


def test_a_cached_page_and_tile_are_two_hits_and_a_paid_read_none(tmp_path: Path) -> None:
    model = FakeCarbon(page_form(), [tile_form()])
    reader = CarbonReader(model, tmp_path)
    first, hits, paid = read(reader)
    assert (hits, paid, len(model.calls)) == (0, pytest.approx(0.02), 2)
    again, hits, paid = read(reader)
    assert (hits, paid, len(model.calls)) == (2, 0, 2)  # both from the pool's threads
    assert again == first  # the same reading


def test_a_cached_file_that_does_not_parse_is_no_hit(tmp_path: Path) -> None:
    model = FakeCarbon(page_form(), [tile_form()])
    read(CarbonReader(model, tmp_path))
    for path in tmp_path.iterdir():
        path.write_text("{not json")
    _, hits, paid = read(CarbonReader(model, tmp_path))
    assert (hits, paid, len(model.calls)) == (0, pytest.approx(0.02), 4)  # asked again, paid


def test_a_failed_call_is_no_hit(tmp_path: Path) -> None:
    # a spent budget costs 0 too: a failed call must not read "from the cache"
    model = FakeCarbon(RuntimeError("budget used up"), [tile_form()])
    found, hits, _ = read(CarbonReader(model, tmp_path))
    assert hits == 0 and not found.read


class ReadsWith:
    """The Carbon extractor over a fixed small page."""

    def __init__(self, reader: CarbonReader) -> None:
        self.reader = reader

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return self.reader.read(page_image(900, 700))


def test_the_carbon_check_step_says_its_replies_came_from_the_cache(tmp_path: Path) -> None:
    reader = CarbonReader(FakeCarbon(page_form(), [tile_form()]), tmp_path)

    def check() -> str:
        found = CarbonChecked(Reads(SHIPPED), ReadsWith(reader)).extract(SOURCE, SHEET)
        (step,) = [s for s in found.steps if s.id == "carbon_check"]
        return step.did

    assert "from the cache" not in check()  # asked and paid
    did, span = timed(check)
    assert did.endswith("; 2 replies from the cache"), did
    assert span.cached == 2 and span.cost_usd == 0  # handed back to the caller by `beside`
