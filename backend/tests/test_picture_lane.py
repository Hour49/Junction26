"""The discipline-picture lane in ingest (discipline-pictures.md; brief pic-1): a scanned services
plan that triage names a discipline is read by the local readers (legend by OCR, template
symbols, mask runs) into a fact sheet beside its drawing; a question is answered from it, Low,
with its spots as evidence. Off (the default), nothing is built and ingest is unchanged (AC-14).
Every page is drawn in the test: no partner data."""

import io
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.adapters.discipline_pictures.lane import PictureLane
from app.adapters.discipline_pictures.legend import read_legend
from app.adapters.raster_ocr import RapidOcrEngine
from app.composition import build_ingest, build_pipeline
from app.core.answering.facts import FACTS
from app.core.answering.model import Answer, Question
from app.core.ingest.model import Classified
from app.core.ingest.triage import TriageSteps
from app.core.picture_facts import storey_of_title
from app.settings import Settings
from scripts.make_sample_archive import build_archive

W, H, TILE, DPI = 2000, 1400, 40, 150
M_PER_PX = 50 * 0.0254 / DPI  # printed 1:50 at the file's 150 dpi
RUN_PX = round(5.0 / M_PER_PX)  # a 5.00 m heating run
RED = (220, 30, 30)
FONT = ImageFont.load_default(size=26)


def radiator(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((6, 14, 32, 26), outline=0, width=2)
    for x in (12, 18, 24):
        draw.line((x, 14, x, 26), fill=0, width=2)
    draw.line((32, 20, 39, 20), fill=0, width=2)


def valve(draw: ImageDraw.ImageDraw) -> None:
    draw.polygon(((6, 8), (20, 20), (6, 32)), fill=0)
    draw.polygon(((34, 8), (20, 20), (34, 32)), fill=0)


def tile(draw_symbol: Any) -> Image.Image:
    image = Image.new("L", (TILE, TILE), 255)
    draw_symbol(ImageDraw.Draw(image))
    return image


RADIATORS = [(200, 200, 0), (600, 200, 90), (1000, 200, 180), (200, 700, 270), (600, 700, 0),
             (1000, 700, 0)]  # fmt: skip
VALVES = [(300, 450), (800, 450), (1200, 450)]


def heating_scan() -> bytes:
    """A scanned heating plan: grey walls, 6 radiators, 3 valves, a red 5.00 m run, a legend
    headed LEGEND with a group heading, the printed scale, the file's own 150 dpi."""
    page = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    draw.rectangle((20, 20, W - 20, H - 20), outline=(0, 0, 0), width=3)
    for y in (150, 650, 1150):
        draw.line((60, y, 1450, y), fill=(150, 150, 150), width=6)
    for x, y, turn in RADIATORS:
        page.paste(tile(radiator).rotate(turn).convert("RGB"), (x, y))
    for x, y in VALVES:
        page.paste(tile(valve).convert("RGB"), (x, y))
    draw.line((300, 1000, 300 + RUN_PX, 1000), fill=RED, width=4)
    x = 1560
    draw.text((x, 880), "LEGEND", fill=(0, 0, 0), font=FONT)
    draw.text((x, 940), "HEATING", fill=(0, 0, 0), font=FONT)
    page.paste(tile(radiator).convert("RGB"), (x, 990))
    draw.text((x + 70, 996), "Radiator", fill=(0, 0, 0), font=FONT)
    page.paste(tile(valve).convert("RGB"), (x, 1050))
    draw.text((x + 70, 1056), "Valve", fill=(0, 0, 0), font=FONT)
    draw.line((x, 1130, x + 50, 1130), fill=RED, width=4)
    draw.text((x + 70, 1116), "Heating pipe DN20", fill=(0, 0, 0), font=FONT)
    draw.text((60, 1300), "SCALE 1:50", fill=(0, 0, 0), font=FONT)
    out = io.BytesIO()
    page.save(out, "PNG", dpi=(DPI, DPI))
    return out.getvalue()


class SheetKind:
    """Triage's classifier with the sheet-kind step's reply: a heating plan read as a doubt."""

    def __init__(self, discipline: str | None = "heating") -> None:
        self.discipline = discipline

    def classify(self, image: bytes, probed: Any) -> Classified:
        sheet = {
            "kind": "mep_plan", "kind_words": "a services plan", "decision": "doubt",
            "takeoff_possible": False, "confidence": 0.9, "title": "HEATING PLAN 2ND FLOOR",
            "sheet_number": "H-102", "printed_scale": "1:50", "advanced": False,
            "advanced_why": None, "seen": "a heating plan", "model": "fake sheet kind",
            "discipline": self.discipline,
        }  # fmt: skip
        return Classified.model_validate(
            {"class": "floor_plan", "p_plan": 0.9, "method": "fake", "sheet": sheet}
        )


def _settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **more: Any) -> Settings:
    monkeypatch.chdir(tmp_path)  # a developer's backend/.env can't change the result
    return Settings(projects_dir=tmp_path / "projects", **more)


def _ingest(settings: Settings, data: bytes, kind: SheetKind) -> tuple[Any, str]:
    triage = TriageSteps(classifier=kind, describer=None, judge=None, name="fakes")
    ingest = build_ingest(settings, settings.projects_dir, background=False, triage=triage)
    status = ingest.wait(ingest.start("heating.png", data))
    return status, str(settings.projects_dir / status.id / "files")


class _Sink:
    def __init__(self) -> None:
        self.answers: list[Answer] = []

    def write(self, answer: Answer) -> None:
        self.answers.append(answer)


class _NoDrawings:
    def drawing(self, file: str) -> None:
        return None


def _ask(settings: Settings, files: str, *texts: str) -> list[Answer]:
    pipeline = build_pipeline(settings, Path(files))
    sink = _Sink()
    asked = [Question(id=n, file="heating.png", text=t) for n, t in enumerate(texts, 1)]
    pipeline.answer_questions(asked, _NoDrawings(), sink)
    return sink.answers


# --- the parts ---------------------------------------------------------------------------------


def test_the_legend_is_read_by_ocr_with_its_group_symbols_and_line() -> None:
    rgb = Image.open(io.BytesIO(heating_scan())).convert("RGB")
    import numpy as np

    legend, scale_text = read_legend(np.asarray(rgb), RapidOcrEngine())
    assert legend is not None
    by = {e.label: e for e in legend}
    assert set(by) == {"Radiator", "Valve", "Heating pipe DN20"}
    assert all(e.group and e.group.lower() == "heating" for e in legend)
    assert by["Heating pipe DN20"].line and not by["Radiator"].line and not by["Valve"].line
    x0, y0, x1, y1 = by["Radiator"].box or (0, 0, 0, 0)
    assert 1560 / W - 0.01 < x0 < x1 < 1600 / W + 0.01 and 990 / H < y0 < y1 < 1030 / H
    assert scale_text is not None and "1:50" in scale_text


def test_a_page_with_no_legend_header_has_no_legend() -> None:
    import numpy as np

    blank = np.full((400, 600, 3), 255, dtype=np.uint8)
    assert read_legend(blank, RapidOcrEngine()) == (None, None)


def test_the_storey_is_the_one_the_title_names() -> None:
    assert storey_of_title("HEATING PLAN 2ND FLOOR") == "2ND FLOOR"
    assert storey_of_title("LVI-pohjapiirustus 2. krs") == "2. krs"
    assert storey_of_title("Heizung Grundriss 1. OG") == "1. OG"
    assert storey_of_title("HEATING PLAN") is None
    assert storey_of_title(None) is None


# --- through ingest ----------------------------------------------------------------------------


def test_a_scanned_heating_plan_answers_counts_and_lengths_low_with_marks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, monkeypatch, discipline_pictures="template",
                         discipline_pictures_cache_dir=tmp_path / "facts")  # fmt: skip
    status, files = _ingest(settings, heating_scan(), SheetKind())
    assert status.state == "done", status
    radiators, metres, sockets, on_floor, dn20 = _ask(
        settings, files, "How many radiators are there?", "How many metres of heating pipe?",
        "How many sockets are there?", "How many radiators on floor 2?",
        "What is the total length of DN20 pipe?",
    )  # fmt: skip
    assert radiators.method == FACTS and radiators.sure is False
    assert "Total space heaters: 6" in str(radiators.answer), radiators
    assert len(radiators.evidence) == 6 and radiators.evidence[0].file == "heating.png"
    assert "confidence is Low" in (radiators.explanation or "")
    said = str(metres.answer)
    length = float(said.split("Total length: ")[1].split(" m")[0])
    assert abs(length - 5.0) <= 0.15, said  # AC-12's 3%
    assert metres.sure is False and len(metres.evidence) == 1  # the run's one piece
    assert "DN20" in str(dn20.answer), dn20
    assert sockets.answer is None and sockets.abstain and "not read" in (sockets.explanation or "")
    assert "Total space heaters on 2ND FLOOR: 6" in str(on_floor.answer), on_floor


def test_a_sheet_triage_names_no_discipline_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, monkeypatch, discipline_pictures="template",
                         discipline_pictures_cache_dir=tmp_path / "facts")  # fmt: skip
    _, files = _ingest(settings, heating_scan(), SheetKind(discipline=None))  # mep_plan alone
    [answer] = _ask(settings, files, "How many radiators are there?")
    assert answer.method != FACTS
    assert not any((tmp_path / "facts").glob("*.json"))


# --- AC-14: off is the default and changes nothing ----------------------------------------------


def test_ac14_off_builds_no_reader_and_names_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    off = _settings(tmp_path, monkeypatch)
    assert off.discipline_pictures == "off"
    pipeline = build_pipeline(off, tmp_path)
    assert not isinstance(pipeline.extractors["raster"], PictureLane) and pipeline.facts is None
    names = build_ingest(off, tmp_path / "projects", background=False)._names  # pyright: ignore[reportPrivateUsage]
    assert "discipline_pictures" not in names
    on = off.model_copy(update={"discipline_pictures": "template"})
    assert isinstance(build_pipeline(on, tmp_path).extractors["raster"], PictureLane)


def test_ac14_ingest_output_is_byte_identical_with_the_lane_on_or_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = build_archive()
    stored: dict[str, list[bytes]] = {}
    for mode in ("off", "template"):
        (tmp_path / mode).mkdir()
        settings = _settings(tmp_path / mode, monkeypatch, discipline_pictures=mode,
                             discipline_pictures_cache_dir=tmp_path / "facts")  # fmt: skip
        ingest = build_ingest(settings, settings.projects_dir, background=False)
        assert ingest.wait(ingest.start("sample.zip", archive)).state == "done"
        drawings = settings.projects_dir / "drawings"  # named by key: the readers' names differ
        stored[mode] = sorted(p.read_bytes() for p in drawings.glob("*.json"))
    assert stored["off"] and stored["off"] == stored["template"]
