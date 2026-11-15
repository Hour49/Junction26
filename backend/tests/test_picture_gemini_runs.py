"""`vlm-runs` (DISCIPLINE_RUNS=gemini): one Carbon call per page reads each pipe or duct system's
runs as polylines; lengths at the sheet's scale. A fake client gives recorded-shape replies; no key,
no network, no partner data."""

import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image
from pydantic import SecretStr

from app.adapters.discipline_pictures import gemini_runs
from app.adapters.discipline_pictures.gemini_runs import GeminiRunReader, reading_of
from app.adapters.discipline_pictures.lane import PictureLane, PictureSheets, kept_in
from app.adapters.discipline_pictures.mask import MaskReader
from app.adapters.raster_ocr.gemini import GeminiError, NoAnswerError
from app.core.drawing.model import Page, Scale
from app.core.picture_facts import NO_SCALE
from app.core.pipeline.model import DrawingFile, Sheet
from app.settings import Settings

W, H = 400, 200  # the fake page, px
M_PER_PX = 0.02  # 1:100 at 127 dpi


def reply(found: Any) -> dict[str, Any]:
    return {
        "candidates": [{"content": {"parts": [{"text": json.dumps(found)}]}}],
        "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 2000},
    }


# Supply: a run from x 100 to 300 px at y 100 (200 px = 4 m) printed DN20, and an L of 50 + 50 px
# (2 m) with no size; Return: one run of 100 px (2 m) printed DN20.
SYSTEMS = {
    "systems": [
        {
            "label": "Supply",
            "sizes": ["DN20"],
            "runs": [
                {"size": "DN20", "points": [[500, 250], [500, 750]]},
                {"size": None, "points": [[250, 100], [500, 100], [500, 225]]},
            ],
            "length_m": 99.0,  # the model's own metres: never used
        },
        {
            "label": "Return",
            "sizes": ["DN20"],
            "runs": [{"size": "DN20", "points": [[800, 250], [800, 500]]}],
            "length_m": 1.0,
        },
    ]
}


def test_polylines_become_runs_per_system_and_size_at_the_sheet_scale() -> None:
    reading = reading_of(reply(SYSTEMS), W, H, M_PER_PX)
    assert reading.reader == "vlm-runs"
    assert [(e.label, e.line) for e in reading.legend or ()] == [("Supply", True), ("Return", True)]
    got = {(r.label, r.size): (r.length_m, len(r.spots)) for r in reading.runs}
    assert got == {
        ("Supply", "DN20"): (4.0, 1),
        ("Supply", None): (2.0, 1),
        ("Return", "DN20"): (2.0, 1),
    }
    (supply,) = [r for r in reading.runs if (r.label, r.size) == ("Supply", "DN20")]
    assert supply.spots[0].box == pytest.approx((0.25, 0.5, 0.75, 0.5))


def test_malformed_points_are_dropped_and_no_system_reads_nothing() -> None:
    bad = {"systems": [{"label": "Supply", "sizes": [], "length_m": 0, "runs": [
        {"size": None, "points": [[1, 2, 3], ["a", 5], [500, 250]]},  # one good point: no run
        {"size": "DN15", "points": [[True, 1], [500, 250], [500, 500.5]]},
    ]}]}  # fmt: skip
    reading = reading_of(reply(bad), W, H, M_PER_PX)
    assert [(r.size, r.length_m) for r in reading.runs] == [("DN15", pytest.approx(2.004))]
    empty = reading_of(reply({"systems": []}), W, H, M_PER_PX)
    assert empty.legend is None and not empty.runs and "no legend" in empty.notes[0]
    with pytest.raises(ValueError, match="not the asked JSON"):
        reading_of({"candidates": [{"content": {"parts": [{"text": "sorry"}]}}]}, W, H, 1.0)


class Client:
    def __init__(self, answer: dict[str, Any] | Exception) -> None:
        self.answer = answer
        self.calls = 0

    def generate(self, jpeg: bytes, prompt: str, schema: dict, max_tokens: int) -> dict[str, Any]:
        self.calls += 1
        assert prompt == gemini_runs.PROMPT and schema == gemini_runs.SCHEMA
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


class Files:
    def read(self, path: str) -> bytes:
        out = io.BytesIO()
        Image.new("RGB", (W, H), "white").save(out, format="PNG")
        return out.getvalue()


def scale(m_per_unit: float | None) -> Any:
    if m_per_unit is None:
        return lambda source, sheet: Scale(status="no_scale")
    return lambda source, sheet: Scale(status="scaled", m_per_unit=m_per_unit)


def sheet() -> tuple[DrawingFile, Sheet]:
    source = DrawingFile(path="h.png", size=1, sha256="0" * 64, kind="png")
    return source, Sheet(file=source, pages=(Page(page=1, width=W, height=H, unit="px"),))


def reader(client: Client, tmp_path: Path, m_per_unit: float | None = M_PER_PX) -> GeminiRunReader:
    return GeminiRunReader(Files(), client, tmp_path / "replies", scale(m_per_unit))  # type: ignore[arg-type]


def test_the_reader_sends_the_page_once_measures_at_the_scale_and_charges(tmp_path: Path) -> None:
    client = Client(reply(SYSTEMS))
    reading = reader(client, tmp_path).read(*sheet())
    assert client.calls == 1 and reading.cost_usd > 0
    assert sum(r.length_m for r in reading.runs) == pytest.approx(8.0)
    doubled = reader(Client(reply(SYSTEMS)), tmp_path / "b", 2 * M_PER_PX).read(*sheet())
    assert sum(r.length_m for r in doubled.runs) == pytest.approx(16.0)


def test_no_scale_makes_no_call_and_says_so(tmp_path: Path) -> None:
    client = Client(reply(SYSTEMS))
    reading = reader(client, tmp_path, None).read(*sheet())
    assert client.calls == 0 and not reading.runs and NO_SCALE in reading.notes[0]


def test_a_page_is_paid_for_once_and_a_new_version_asks_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = Client(reply(SYSTEMS))
    first = reader(client, tmp_path).read(*sheet())
    again = reader(client, tmp_path).read(*sheet())
    assert client.calls == 1 and again.runs == first.runs and again.cost_usd == 0.0
    monkeypatch.setattr(gemini_runs, "VERSION", gemini_runs.VERSION + "-next")
    reader(client, tmp_path).read(*sheet())
    assert client.calls == 2


def test_a_failed_call_or_a_bad_reply_raises_and_caches_nothing(tmp_path: Path) -> None:
    with pytest.raises(GeminiError, match="HTTP 503"):
        reader(Client(NoAnswerError("HTTP 503")), tmp_path).read(*sheet())
    bad = Client({"candidates": [{"content": {"parts": [{"text": "sorry"}]}}]})
    with pytest.raises(GeminiError, match="not the asked JSON"):
        reader(bad, tmp_path).read(*sheet())
    assert (
        not list((tmp_path / "replies").glob("*.json")) if (tmp_path / "replies").exists() else True
    )


def test_a_reply_with_no_system_is_not_cached(tmp_path: Path) -> None:
    client = Client(reply({"systems": []}))
    reader(client, tmp_path).read(*sheet())
    reader(client, tmp_path).read(*sheet())
    assert client.calls == 2


class Inner:
    def extract(self, source: Any, sheet: Any) -> str:
        return "drawing"


class NoSymbols:
    def read(self, source: Any, sheet: Any) -> Any:
        from app.core.picture_facts import PictureReading

        return PictureReading(reader="template", legend=None, read=())


def test_the_lane_takes_its_runs_from_the_given_run_reader(tmp_path: Path) -> None:
    sheets = PictureSheets(Files(), tmp_path / "sheets")  # type: ignore[arg-type]
    legend = SimpleNamespace(legend=lambda source, sheet: None, scale=scale(M_PER_PX))
    made = PictureLane(
        Inner(),  # type: ignore[arg-type]
        Files(),  # type: ignore[arg-type]
        lambda path: None,
        sheets,
        legend,  # type: ignore[arg-type]
        NoSymbols(),
        reader(Client(reply(SYSTEMS)), tmp_path),
    )
    source = DrawingFile(path="H-101 heating.png", size=1, sha256="1" * 64, kind="png")
    made.extract(source, Sheet(file=source, pages=(Page(page=1, width=W, height=H, unit="px"),)))
    kept = sheets.sheet("1" * 64)
    assert kept is not None
    lengths = {f.subject: f.value for f in kept.facts if f.unit == "m"}
    assert lengths and all("vlm-runs" in f.source for f in kept.facts if f.unit == "m")


def test_runs_gemini_keeps_its_sheets_apart_and_mask_stays_the_default(tmp_path: Path) -> None:
    from app.composition import _pictures_cache  # pyright: ignore[reportPrivateUsage]

    base: dict[str, Any] = {"_env_file": None, "discipline_pictures_cache_dir": tmp_path}
    assert Settings(**base).discipline_runs == "mask"
    on = Settings(**base, discipline_pictures="gemini", discipline_runs="gemini")
    assert _pictures_cache(on) == kept_in(tmp_path, "gemini") / "runs-gemini"


def test_the_setting_picks_the_run_reader(tmp_path: Path) -> None:
    from app.composition import _pictures  # pyright: ignore[reportPrivateUsage]

    base: dict[str, Any] = {
        "_env_file": None,
        "discipline_pictures": "template",
        "discipline_pictures_cache_dir": tmp_path,
        "gemini_api_key": SecretStr("test-key-not-real"),
    }
    default = _pictures(Settings(**base), Inner(), Files(), None)  # type: ignore[arg-type]
    assert isinstance(default._mask, MaskReader)  # pyright: ignore[reportAttributeAccessIssue]
    on = _pictures(Settings(**base, discipline_runs="gemini"), Inner(), Files(), None)  # type: ignore[arg-type]
    assert isinstance(on._mask, GeminiRunReader)  # pyright: ignore[reportAttributeAccessIssue]
