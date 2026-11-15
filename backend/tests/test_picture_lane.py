"""The discipline-picture lane in ingest (discipline-pictures.md; brief pic-1): a scanned services
plan that triage names a discipline is read by the local readers (legend by OCR, template
symbols, mask runs) into a fact sheet beside its drawing; a question is answered from it, Low,
with its spots as evidence. Off (the default), nothing is built and ingest is unchanged (AC-14).
Every page is drawn in the test: no partner data."""

import io
import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.adapters.discipline_pictures.lane import FROM_FILE_NAME, PictureLane
from app.adapters.discipline_pictures.legend import read_legend
from app.adapters.raster_ocr import RapidOcrEngine
from app.composition import build_ingest, build_pipeline
from app.core.answering.facts import FACTS
from app.core.answering.model import Answer, Question
from app.core.drawing.model import Page
from app.core.ingest.model import Classified
from app.core.ingest.triage import TriageSteps
from app.core.picture_facts import storey_of_title
from app.core.pipeline.printed import printed_scale
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


def _ask(settings: Settings, files: str, *texts: str, file: str = "heating.png") -> list[Answer]:
    pipeline = build_pipeline(settings, Path(files))
    sink = _Sink()
    asked = [Question(id=n, file=file, text=t) for n, t in enumerate(texts, 1)]
    pipeline.answer_questions(asked, _NoDrawings(), sink)
    return sink.answers


# --- the parts ---------------------------------------------------------------------------------


def test_the_legend_is_read_by_ocr_with_its_group_symbols_and_line() -> None:
    rgb = Image.open(io.BytesIO(heating_scan())).convert("RGB")
    import numpy as np

    legend, printed = read_legend(np.asarray(rgb), RapidOcrEngine())
    assert legend is not None
    by = {e.label: e for e in legend}
    assert set(by) == {"Radiator", "Valve", "Heating pipe DN20"}
    assert all(e.group and e.group.lower() == "heating" for e in legend)
    assert by["Heating pipe DN20"].line and not by["Radiator"].line and not by["Valve"].line
    x0, y0, x1, y1 = by["Radiator"].box or (0, 0, 0, 0)
    assert 1560 / W - 0.01 < x0 < x1 < 1600 / W + 0.01 and 990 / H < y0 < y1 < 1030 / H
    assert printed.printed_scale is not None and "1:50" in printed.printed_scale
    assert printed.bars == ()  # no bar printed: the ratio at the file's dpi is the scale


def test_a_blank_page_has_no_legend_and_no_scale() -> None:
    import numpy as np

    blank = np.full((400, 600, 3), 255, dtype=np.uint8)
    legend, printed = read_legend(blank, RapidOcrEngine())
    assert legend is None and printed.printed_scale is None and printed.bars == ()


GREEN = (30, 160, 30)
BAR_PX = 591  # a 5 m bar at 1:50 and 150 dpi


def revit_sheet() -> tuple[bytes, dict[str, tuple[int, int, int, int]]]:
    """A services plan as Revit exports it: a legend with no heading word, its rows tight (system
    headings without a sample, line samples, symbols left of family names), a printed scale bar
    "5 m 1:50", and no dpi in the file. Returns the png and each symbol's drawn box."""
    page = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    for y in (300, 800):
        draw.line((60, y, 1000, y), fill=(0, 0, 0), width=4)
    draw.ellipse((400, 500, 430, 530), outline=(0, 0, 0), width=2)  # a radiator on the plan
    x, step = 1150, 34
    rows = [
        (None, "Unit A Hydronic Supply In", 0),
        ("red", "Unit A Hydronic Supply In", 130),
        ("square", "M_Ball Valve - 50 mm", 75),
        (None, "Unit A Hydronic Supply In,Unit A Hydronic Supply Out", 0),
        ("circle", "M_Radiator - Hosted:Readiator - 25", 75),
        ("green", "Unit B Hydronic Supply In", 130),
    ]
    symbols: dict[str, tuple[int, int, int, int]] = {}
    for n, (sample, label, indent) in enumerate(rows):
        y = 60 + n * step
        mid = y + 15
        if sample in ("red", "green"):
            draw.line((x, mid, x + 100, mid), fill=RED if sample == "red" else GREEN, width=3)
        elif sample == "square":
            symbols[label] = (x + 15, mid - 11, x + 37, mid + 11)
            draw.rectangle(symbols[label], outline=(0, 0, 0), width=2)
        elif sample == "circle":
            symbols[label] = (x + 15, mid - 11, x + 37, mid + 11)
            draw.ellipse(symbols[label], outline=(0, 0, 0), width=2)
        draw.text((x + indent, y), label, fill=(0, 0, 0), font=FONT)
    draw.rectangle((30, 1320, 30 + BAR_PX - 1, 1329), fill=(0, 0, 0))
    draw.text((30 + BAR_PX + 15, 1308), "5 m   1:50", fill=(0, 0, 0), font=FONT)
    out = io.BytesIO()
    page.save(out, "PNG")  # no dpi: the bar is the only scale
    return out.getvalue(), symbols


def test_a_legend_with_no_heading_word_is_read_with_tight_symbol_crops() -> None:
    import numpy as np

    data, symbols = revit_sheet()
    legend, _ = read_legend(
        np.asarray(Image.open(io.BytesIO(data)).convert("RGB")), RapidOcrEngine()
    )
    assert legend is not None
    by = {e.label.split(" - ")[0]: e for e in legend}
    assert set(by) == {"Unit A Hydronic Supply In", "M_Ball Valve", "M_Radiator",
                       "Unit B Hydronic Supply In"}, legend  # fmt: skip
    assert by["Unit A Hydronic Supply In"].line and by["Unit B Hydronic Supply In"].line
    assert not by["M_Ball Valve"].line and not by["M_Radiator"].line
    assert by["M_Ball Valve"].group == "Unit A Hydronic Supply In"
    assert (by["M_Radiator"].group or "").startswith("Unit A Hydronic Supply In,")
    for name, drawn in symbols.items():  # the symbol only: no heading or label ink in the crop
        x0, y0, x1, y1 = by[name.split(" - ")[0]].box or (0, 0, 0, 0)
        dx0, dy0, dx1, dy1 = drawn
        pad = 4
        assert (dx0 - pad) / W <= x0 <= dx0 / W and dx1 / W <= x1 <= (dx1 + pad) / W, name
        assert (dy0 - pad) / H <= y0 <= dy0 / H and dy1 / H <= y1 <= (dy1 + pad) / H, name


def test_a_printed_scale_bar_gives_metres_without_a_dpi() -> None:
    import numpy as np

    data, _ = revit_sheet()
    _, printed = read_legend(
        np.asarray(Image.open(io.BytesIO(data)).convert("RGB")), RapidOcrEngine()
    )
    assert [bar.length_m for bar in printed.bars] == [5.0]
    scale = printed_scale(printed, [Page(page=1, width=W, height=H, unit="px")], None)
    assert scale is not None and scale.m_per_unit == pytest.approx(5.0 / BAR_PX, rel=0.01)


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


# --- no sheet-kind reply: the discipline from the file name (sheet code or strong word) ----------


def _untriaged(settings: Settings, name: str) -> tuple[Any, str]:
    """`name` ingested with triage off (no sheet-kind step), as the no-keys backend does."""
    ingest = build_ingest(settings, settings.projects_dir, background=False)
    status = ingest.wait(ingest.start(name, heating_scan()))
    return status, str(settings.projects_dir / status.id / "files")


def test_a_picture_no_sheet_kind_step_saw_is_routed_by_its_file_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, monkeypatch, discipline_pictures="template",
                         discipline_pictures_cache_dir=tmp_path / "facts")  # fmt: skip
    _, files = _untriaged(settings, "H-102 heating plan.png")
    [sheet] = (tmp_path / "facts").glob("*.json")
    sources = {f["source"] for f in json.loads(sheet.read_text())["facts"]}
    assert sources and all(FROM_FILE_NAME in s and s.startswith("picture:") for s in sources)
    # Low, as every picture fact
    [answer] = _ask(settings, files, "How many radiators are there?", file="H-102 heating plan.png")
    assert answer.method == FACTS and answer.sure is False
    assert "confidence is Low" in (answer.explanation or "")


def test_a_file_name_that_names_no_discipline_leaves_the_picture_unread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, monkeypatch, discipline_pictures="template",
                         discipline_pictures_cache_dir=tmp_path / "facts")  # fmt: skip
    _untriaged(settings, "pipe layout 7.png")  # "pipe" is a weak word: plumbing or heating
    assert not any((tmp_path / "facts").glob("*.json"))


def test_off_the_file_name_changes_no_route_flag_or_drawing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, tuple[Any, ...]] = {}
    for mode in ("off", "template"):
        (tmp_path / mode).mkdir()
        settings = _settings(tmp_path / mode, monkeypatch, discipline_pictures=mode,
                             discipline_pictures_cache_dir=tmp_path / mode / "facts")  # fmt: skip
        status, _ = _untriaged(settings, "H-102 heating plan.png")
        drawings = sorted(p.read_bytes() for p in (settings.projects_dir / "drawings").glob("*"))
        flags = [(f.path, f.state, f.route, f.reason) for f in status.files]
        seen[mode] = (flags, drawings)
    assert seen["off"] == seen["template"]
    assert not (tmp_path / "off" / "facts").exists()


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
