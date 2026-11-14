"""The local readers of a services or structural plan (docs/specs/backend/discipline-pictures.md,
AC-9, AC-11, AC-12): `template` over a raster, `paths` over a vector PDF, `mask` for runs. Every
page is drawn in the test: no partner data."""

import io
import math
import time

from pdf_sheets import BLACK, Point, SheetPdf, rect, ring
from PIL import Image, ImageDraw

from app.adapters.discipline_pictures.mask import MaskReader
from app.adapters.discipline_pictures.paths import PathsReader
from app.adapters.discipline_pictures.template import TemplateReader
from app.adapters.vector_pdf.objects import read_page
from app.adapters.vector_pdf.scale import M_PER_PT_ON_PAPER
from app.core.drawing.model import Box, Page, Scale
from app.core.picture_facts import NO_SCALE, LegendEntry, PictureReading
from app.core.pipeline.model import DrawingFile, Sheet

NEAR = 0.006 * math.sqrt(2)  # double_check's reach, in page fractions


class Files:
    def __init__(self, content: dict[str, bytes]) -> None:
        self.content = content

    def read(self, path: str) -> bytes:
        return self.content[path]


def sheet_of(path: str, kind: str, page: Page) -> tuple[DrawingFile, Sheet]:
    source = DrawingFile(path=path, size=1, sha256="0" * 64, kind=kind)  # type: ignore[arg-type]
    return source, Sheet(file=source, pages=(page,))


def png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def fractions(x0: float, y0: float, x1: float, y1: float, w: float, h: float) -> Box:
    return (x0 / w, y0 / h, x1 / w, y1 / h)


def centre(box: Box) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


# --------------------------------------------------------------------------- template (AC-9)

W, H, TILE = 2000, 1400, 40


def radiator(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((6, 14, 32, 26), outline=0, width=2)
    for x in (12, 18, 24):
        draw.line((x, 14, x, 26), fill=0, width=2)
    draw.line((32, 20, 39, 20), fill=0, width=2)


def diffuser(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse((8, 8, 32, 32), outline=0, width=2)
    draw.line((20, 20, 20, 1), fill=0, width=2)
    draw.rectangle((17, 22, 23, 28), fill=0)


def socket(draw: ImageDraw.ImageDraw) -> None:
    draw.polygon(((6, 34), (34, 34), (20, 8)), outline=0, width=2)
    draw.line((6, 34, 6, 38), fill=0, width=2)


SYMBOLS = {"Radiator": radiator, "Supply air diffuser": diffuser, "Socket outlet 2x": socket}


def tile(draw_symbol: object) -> Image.Image:
    image = Image.new("L", (TILE, TILE), 255)
    draw_symbol(ImageDraw.Draw(image))  # type: ignore[operator]
    return image


def symbol_page() -> tuple[bytes, tuple[LegendEntry, ...], list[tuple[str, tuple[float, float]]]]:
    """A 2000x1400 page: 25 symbols of 3 kinds turned 0/90/180/270, a few walls, a legend."""
    page = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(page)
    draw.rectangle((20, 20, W - 20, H - 20), outline=0, width=3)
    for row in range(5):
        y = 150 + 240 * row + 120
        draw.line((60, y, 1550, y), fill=120, width=4)
    labels = list(SYMBOLS)
    placed: list[tuple[str, tuple[float, float]]] = []
    for at in range(25):
        col, row = at % 5, at // 5
        x, y = 150 + 280 * col, 150 + 240 * row
        label = labels[at % 3]
        page.paste(tile(SYMBOLS[label]).rotate(90 * (at % 4)), (x, y))
        placed.append((label, ((x + TILE / 2) / W, (y + TILE / 2) / H)))
    legend: list[LegendEntry] = []
    for number, label in enumerate(labels):
        x, y = 1700, 950 + 120 * number
        page.paste(tile(SYMBOLS[label]), (x, y))
        draw.text((x + 60, y + 15), label, fill=0)
        box = fractions(x - 6, y - 6, x + TILE + 6, y + TILE + 6, W, H)  # loose, as a VLM's
        legend.append(LegendEntry(label=label, group=None, line=False, box=box))
    legend.append(LegendEntry(label="Heating flow", group="Heating", line=True, box=None))
    return png(page), tuple(legend), placed


def test_template_finds_every_symbol_turned_any_quarter_and_none_on_the_legend() -> None:
    data, legend, placed = symbol_page()
    source, sheet = sheet_of("plan.png", "png", Page(page=1, width=W, height=H, unit="px"))
    reading = TemplateReader(Files({"plan.png": data}), lambda _s, _p: legend).read(source, sheet)
    found_all(reading, placed)


def found_all(reading: PictureReading, placed: list[tuple[str, tuple[float, float]]]) -> None:
    """AC-9: every placed symbol once, with its label, and nothing else."""
    assert reading.reader == "template"
    assert set(reading.read or ()) == set(SYMBOLS)
    assert len(reading.sightings) == len(placed)
    left = list(placed)
    for seen in reading.sightings:
        match = next((p for p in left if math.dist(p[1], centre(seen.spot.box)) <= NEAR), None)
        assert match is not None, f"{seen.label} at {centre(seen.spot.box)} is no placed symbol"
        assert seen.label == match[0]
        assert seen.spot.reader == "template" and seen.spot.page == 1
        assert seen.score is not None and 0 < seen.score <= 1
        left.remove(match)


def test_template_without_a_legend_reads_nothing_and_says_why() -> None:
    data, _, _ = symbol_page()
    source, sheet = sheet_of("plan.png", "png", Page(page=1, width=W, height=H, unit="px"))
    reading = TemplateReader(Files({"plan.png": data}), lambda _s, _p: None).read(source, sheet)
    assert reading.read == () and reading.sightings == ()
    assert reading.legend is None and reading.notes


A1_W, A1_H = 4967, 3508  # A1 at 150 dpi
PER_SYMBOL_S = 2.0  # target 0.5 s; 4x margin so a busy CI machine does not flake it


def test_template_stays_under_two_seconds_a_symbol_on_an_a1_page() -> None:
    """The AC-9 page in the corner of an A1 sheet: still every symbol, and quick."""
    data, legend, placed = symbol_page()
    with Image.open(io.BytesIO(data)) as small:
        page = Image.new("L", (A1_W, A1_H), 255)
        page.paste(small, (0, 0))
    big = [
        e.model_copy(
            update={
                "box": (
                    e.box[0] * W / A1_W,
                    e.box[1] * H / A1_H,
                    e.box[2] * W / A1_W,
                    e.box[3] * H / A1_H,
                )
            }
        )
        if e.box
        else e
        for e in legend
    ]
    moved = [(label, (x * W / A1_W, y * H / A1_H)) for label, (x, y) in placed]
    source, sheet = sheet_of("a1.png", "png", Page(page=1, width=A1_W, height=A1_H, unit="px"))
    reader = TemplateReader(Files({"a1.png": png(page)}), lambda _s, _p: tuple(big))
    found_all(reader.read(source, sheet), moved)  # also warms imports and caches
    seconds = []
    for _ in range(2):  # best of two
        start = time.perf_counter()
        reader.read(source, sheet)
        seconds.append(time.perf_counter() - start)
    assert min(seconds) / len(SYMBOLS) <= PER_SYMBOL_S, seconds


# --------------------------------------------------------------------------- paths (AC-11)

M_PER_PT = 100 * M_PER_PT_ON_PAPER  # 1:100
BLUE, RED, GREEN = (20, 60, 200), (200, 30, 30), (30, 150, 60)


def turned(points: list[Point], degrees: float, about: Point) -> list[Point]:
    cos, sin = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return [
        (
            about[0] + (x - about[0]) * cos - (y - about[1]) * sin,
            about[1] + (x - about[0]) * sin + (y - about[1]) * cos,
        )
        for x, y in points
    ]


def heater(sheet: SheetPdf, x: float, y: float, degrees: float = 0) -> None:
    sheet.path(turned(ring(x, y, 4, 9), degrees, (x, y)), stroke=BLUE, width=0.5)
    sheet.path(turned([(x + 4, y), (x + 9, y)], degrees, (x, y)), stroke=BLUE, width=0.5)


def services_pdf() -> tuple[bytes, tuple[LegendEntry, ...], dict[str, float]]:
    """A 600x400 pt sheet at 1:100: 6 heaters (3 turned), a red and a green run, walls, a
    legend with one symbol and two line styles."""
    sheet = SheetPdf(600, 400)
    sheet.path(rect(20, 20, 470, 380), stroke=BLACK, width=1.5)
    for x, y, degrees in (
        (60, 60, 0),
        (120, 60, 0),
        (180, 60, 0),
        (60, 300, 90),
        (120, 300, 180),
        (180, 300, 37),
    ):
        heater(sheet, x, y, degrees)
    sheet.path([(60, 100), (260, 100), (260, 250)], stroke=RED, width=1.0)  # 350 pt
    sheet.path([(300, 120), (420, 120)], stroke=RED, width=1.0)  # 120 pt
    sheet.path([(60, 200), (300, 200)], stroke=GREEN, width=1.0)  # 240 pt
    heater(sheet, 500, 300)
    sheet.path([(490, 330), (520, 330)], stroke=RED, width=1.0)
    sheet.path([(490, 360), (520, 360)], stroke=GREEN, width=1.0)
    sheet.text("Radiator", 530, 302)
    sheet.text("Heating flow", 530, 332)
    sheet.text("Cold water", 530, 362)
    sheet.text("1:100", 500, 390)
    legend = (
        LegendEntry(
            label="Radiator",
            group="Heating",
            line=False,
            box=fractions(492, 292, 512, 308, 600, 400),
        ),
        LegendEntry(
            label="Heating flow",
            group="Heating",
            line=True,
            box=fractions(488, 326, 522, 334, 600, 400),
        ),
        LegendEntry(
            label="Cold water",
            group="Cold water",
            line=True,
            box=fractions(488, 356, 522, 364, 600, 400),
        ),
    )
    return sheet.pdf(), legend, {"Heating flow": 470 * M_PER_PT, "Cold water": 240 * M_PER_PT}


def pdf_sheet(pdf: bytes) -> tuple[DrawingFile, Sheet]:
    page = read_page(pdf)
    return sheet_of(
        "plan.pdf", "pdf", Page(page=1, width=page.width, height=page.height, unit="pt")
    )


def read_paths(pdf: bytes, legend: tuple[LegendEntry, ...]) -> PictureReading:
    source, sheet = pdf_sheet(pdf)
    return PathsReader(Files({"plan.pdf": pdf}), lambda _s, _p: legend).read(source, sheet)


def test_paths_finds_six_copies_of_a_legend_symbol_turned_or_not() -> None:
    pdf, legend, _ = services_pdf()
    reading = read_paths(pdf, legend)
    assert reading.reader == "paths"
    assert [s.label for s in reading.sightings] == ["Radiator"] * 6
    seen = [centre(s.spot.box) for s in reading.sightings]
    for x, y in ((60, 60), (120, 60), (180, 60), (60, 300), (120, 300), (180, 300)):
        assert min(math.dist((x / 600, y / 400), at) for at in seen) <= NEAR


def test_paths_measures_each_line_style_within_half_a_percent() -> None:
    pdf, legend, lengths = services_pdf()
    reading = read_paths(pdf, legend)
    assert set(reading.read or ()) == {"Radiator", "Heating flow", "Cold water"}
    for label, metres in lengths.items():
        got = sum(r.length_m for r in reading.runs if r.label == label)
        assert abs(got - metres) <= 0.005 * metres, (label, got, metres)
    assert len([r for r in reading.runs if r.label == "Heating flow"]) == 2


def test_paths_without_a_scale_counts_but_measures_nothing() -> None:
    sheet = SheetPdf(600, 400)
    heater(sheet, 60, 60)
    heater(sheet, 500, 300)
    sheet.path([(60, 100), (260, 100)], stroke=RED, width=1.0)
    sheet.path([(490, 330), (520, 330)], stroke=RED, width=1.0)
    _, legend, _ = services_pdf()
    reading = read_paths(sheet.pdf(), legend)
    assert [s.label for s in reading.sightings] == ["Radiator"]
    assert reading.runs == () and NO_SCALE in reading.notes


# --------------------------------------------------------------------------- mask (AC-12)

MW, MH, M_PER_PX = 1000, 600, 0.01
PIPE_RED = (220, 30, 30)


def run_page() -> tuple[bytes, tuple[LegendEntry, ...]]:
    """A red L-shaped run of 500 px (5.00 m at 0.01 m/px), black walls and text, a legend."""
    page = Image.new("RGB", (MW, MH), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    draw.rectangle((20, 20, 760, 580), outline=(0, 0, 0), width=3)
    draw.line((100, 300, 400, 300), fill=PIPE_RED, width=4)
    draw.line((400, 298, 400, 500), fill=PIPE_RED, width=4)
    draw.line((100, 200, 700, 200), fill=(0, 0, 0), width=4)
    draw.line((800, 550, 850, 550), fill=PIPE_RED, width=4)
    draw.text((860, 545), "Heating flow", fill=(0, 0, 0))
    legend = (
        LegendEntry(
            label="Heating flow",
            group="Heating",
            line=True,
            box=fractions(795, 540, 855, 560, MW, MH),
        ),
    )
    return png(page), legend


def read_mask(scale: Scale) -> PictureReading:
    data, legend = run_page()
    source, sheet = sheet_of("plan.png", "png", Page(page=1, width=MW, height=MH, unit="px"))
    return MaskReader(Files({"plan.png": data}), lambda _s, _p: legend, lambda _s, _p: scale).read(
        source, sheet
    )


def test_mask_measures_a_coloured_run_within_three_percent() -> None:
    reading = read_mask(Scale(status="scaled", m_per_unit=M_PER_PX))
    assert reading.reader == "mask" and reading.read == ("Heating flow",)
    length = sum(r.length_m for r in reading.runs if r.label == "Heating flow")
    assert abs(length - 5.0) <= 0.03 * 5.0, length
    assert all(r.spots for r in reading.runs)


def test_mask_without_a_scale_gives_no_run_and_says_no_scale() -> None:
    reading = read_mask(Scale(status="no_scale"))
    assert reading.runs == () and NO_SCALE in reading.notes


# --------------------------------------------------------------------------- dashed line styles


def dashes(start: Point, step: Point, count: int, dash: float, gap: float) -> list[list[Point]]:
    """`count` dashes of length `dash` from `start` along the unit vector `step`."""
    (x, y), (dx, dy), pitch = start, step, dash + gap
    return [
        [
            (x + dx * pitch * k, y + dy * pitch * k),
            (x + dx * (pitch * k + dash), y + dy * (pitch * k + dash)),
        ]
        for k in range(count)
    ]


def test_paths_tells_a_dashed_run_from_a_solid_one_of_the_same_colour() -> None:
    """CAD exports draw a dashed line as its dashes: a solid red flow and a dashed red return,
    each measured on its own; the dashed one from its first dash to its last."""
    sheet = SheetPdf(600, 400)
    sheet.text("1:100", 500, 390)
    sheet.path([(60, 100), (360, 100)], stroke=RED, width=1.0)  # 300 pt solid
    sheet.path(*dashes((60, 150), (1, 0), 25, 6, 3), stroke=RED, width=1.0)  # 222 pt dashed
    for one in dashes((420, 60), (0, 1), 12, 6, 3):  # 105 pt dashed, a path per dash
        sheet.path(one, stroke=RED, width=1.0)
    sheet.path([(490, 330), (520, 330)], stroke=RED, width=1.0)
    sheet.path(*dashes((490, 360), (1, 0), 4, 6, 3), stroke=RED, width=1.0)
    legend = (
        LegendEntry(
            label="Heating flow",
            group="Heating",
            line=True,
            box=fractions(488, 326, 522, 334, 600, 400),
        ),
        LegendEntry(
            label="Heating return",
            group="Heating",
            line=True,
            box=fractions(488, 356, 528, 364, 600, 400),
        ),
    )
    reading = read_paths(sheet.pdf(), legend)
    flow = [r.length_m for r in reading.runs if r.label == "Heating flow"]
    back = sorted(r.length_m for r in reading.runs if r.label == "Heating return")
    assert len(flow) == 1 and abs(flow[0] - 300 * M_PER_PT) <= 0.005 * 300 * M_PER_PT
    assert len(back) == 2
    for got, drawn in zip(back, (105 * M_PER_PT, 222 * M_PER_PT), strict=True):
        assert abs(got - drawn) <= 0.02 * drawn, (got, drawn)


def test_mask_tells_a_dashed_run_from_a_solid_one_of_the_same_colour() -> None:
    page = Image.new("RGB", (MW, MH), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    draw.rectangle((20, 20, 760, 580), outline=(0, 0, 0), width=3)
    draw.line((100, 300, 499, 300), fill=PIPE_RED, width=3)  # 400 px solid
    for (x0, y0), (x1, y1) in dashes((600, 100), (0, 1), 20, 11, 7):  # 12 px dashes, 6 px gaps
        draw.line((x0, y0, x1, y1), fill=PIPE_RED, width=3)  # 354 px dashed
    draw.line((800, 500, 849, 500), fill=PIPE_RED, width=3)
    for (x0, y0), (x1, y1) in dashes((800, 550), (1, 0), 4, 11, 7):
        draw.line((x0, y0, x1, y1), fill=PIPE_RED, width=3)
    legend = (
        LegendEntry(
            label="Heating flow",
            group="Heating",
            line=True,
            box=fractions(795, 490, 855, 510, MW, MH),
        ),
        LegendEntry(
            label="Heating return",
            group="Heating",
            line=True,
            box=fractions(795, 540, 875, 560, MW, MH),
        ),
    )
    source, sheet = sheet_of("plan.png", "png", Page(page=1, width=MW, height=MH, unit="px"))
    scale = Scale(status="scaled", m_per_unit=M_PER_PX)
    reading = MaskReader(
        Files({"plan.png": png(page)}), lambda _s, _p: legend, lambda _s, _p: scale
    ).read(source, sheet)
    flow = [r.length_m for r in reading.runs if r.label == "Heating flow"]
    back = [r.length_m for r in reading.runs if r.label == "Heating return"]
    assert len(flow) == 1 and abs(flow[0] - 4.0) <= 0.03 * 4.0, flow
    assert len(back) == 1 and abs(back[0] - 3.54) <= 0.03 * 3.54, back
