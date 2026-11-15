"""`inline`: symbols that do not stand alone (a valve on its pipe, a valve and a meter drawn on one
spot of a riser). Every page is drawn in the test: no partner data."""

import numpy as np
from PIL import Image, ImageDraw

from app.adapters.discipline_pictures.inline import read_inline
from app.adapters.discipline_pictures.template import read_symbols
from app.core.picture_facts import LegendEntry

W, H, R = 1200, 900, 12
LEGEND_X = 1050
PIPED = [(150, 200), (400, 200), (650, 200), (300, 500)]  # circles on a horizontal or vertical pipe
STACKED = [(700, 450), (900, 300)]  # a circle and a square drawn on one spot
SQUARES = [(500, 700)]


def circle(draw: ImageDraw.ImageDraw, x: float, y: float) -> None:
    draw.ellipse((x - R, y - R, x + R, y + R), outline=0, width=3)


def square(draw: ImageDraw.ImageDraw, x: float, y: float) -> None:
    draw.rectangle((x - R + 2, y - R + 2, x + R - 2, y + R - 2), outline=0, width=3)


def page() -> tuple[np.ndarray, tuple[LegendEntry, ...]]:
    image = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(image)
    draw.line((60, 200, 900, 200), fill=90, width=3)  # a pipe through the first three circles
    draw.line((300, 300, 300, 850), fill=90, width=3)  # and one through the last
    draw.line((700, 380, 700, 520), fill=90, width=3)  # a riser under a stack
    for x, y in PIPED + STACKED:
        circle(draw, x, y)
    for x, y in STACKED:
        square(draw, x + 4, y + 3)
    for x, y in SQUARES:
        square(draw, x, y)
    draw.text((850, 750), "WTW-3 HT", fill=0)  # text is not a symbol
    legend = []
    for i, (label, draw_it) in enumerate((("Meter", circle), ("Valve", square))):
        y = 60 + 40 * i
        draw_it(draw, LEGEND_X + 20, y + 15)
        box = (LEGEND_X / W, y / H, (LEGEND_X + 40) / W, (y + 30) / H)
        legend.append(LegendEntry(label=label, group=None, line=False, box=box))
    y = 150
    draw.line((LEGEND_X, y, LEGEND_X + 120, y), fill=90, width=3)
    line = (LEGEND_X / W, (y - 8) / H, (LEGEND_X + 120) / W, (y + 8) / H)
    legend.append(LegendEntry(label="Heating supply", group=None, line=True, box=line))
    return np.asarray(image), tuple(legend)


def found(reader, label: str) -> list[tuple[float, float]]:
    gray, legend = page()
    return [
        ((s.spot.box[0] + s.spot.box[2]) / 2 * W, (s.spot.box[1] + s.spot.box[3]) / 2 * H)
        for s in reader(gray, legend).sightings
        if s.label == label
    ]


def hits(spots: list, points: list) -> int:
    return sum(any(abs(x - px) < 5 and abs(y - py) < 5 for x, y in spots) for px, py in points)


def test_the_template_alone_loses_one_of_a_stack() -> None:
    meters, valves = found(read_symbols, "Meter"), found(read_symbols, "Valve")
    assert hits(meters, STACKED) + hits(valves, [(x + 4, y + 3) for x, y in STACKED]) < 4


def test_finds_every_circle_on_a_pipe_or_under_a_square_and_no_more() -> None:
    meters = found(read_inline, "Meter")
    assert hits(meters, PIPED + STACKED) == len(PIPED + STACKED)
    assert len(meters) == len(PIPED + STACKED)


def test_finds_every_square_alone_or_on_a_circle_and_no_more() -> None:
    valves = found(read_inline, "Valve")
    want = SQUARES + [(x + 4, y + 3) for x, y in STACKED]
    assert hits(valves, want) == len(want)
    assert len(valves) == len(want)


def test_a_legend_without_symbols_reads_nothing() -> None:
    gray, legend = page()
    reading = read_inline(gray, legend[2:])
    assert reading.sightings == () and reading.read == ()


def test_a_symbol_inside_a_larger_one_is_the_larger_one() -> None:
    image = Image.new("L", (600, 400), 255)
    draw = ImageDraw.Draw(image)

    def block(x: float, y: float) -> None:
        draw.rectangle((x - R, y - R, x + R, y + R), fill=0)

    def bar(x: float, y: float) -> None:
        draw.rectangle((x - R, y - R / 3, x + R, y + R / 3), outline=0, width=3)

    block(100, 100)
    block(250, 300)
    bar(400, 150)
    legend = []
    for i, (label, draw_it) in enumerate((("Block", block), ("Bar", bar))):
        draw_it(520, 40 + 40 * i)
        box = (490 / 600, (25 + 40 * i) / 400, 550 / 600, (55 + 40 * i) / 400)
        legend.append(LegendEntry(label=label, group=None, line=False, box=box))
    labels = sorted(s.label for s in read_inline(np.asarray(image), tuple(legend)).sightings)
    assert labels == ["Bar", "Block", "Block"]


def test_lighter_pipes_crossing_are_not_a_cross_symbol() -> None:
    image = Image.new("L", (600, 400), 255)
    draw = ImageDraw.Draw(image)

    def cross(x: float, y: float, tone: int = 0) -> None:
        draw.line((x - R, y, x + R, y), fill=tone, width=3)
        draw.line((x, y - R, x, y + R), fill=tone, width=3)

    draw.line((50, 300, 450, 300), fill=110, width=3)  # two grey pipes crossing at (250, 300)
    draw.line((250, 100, 250, 380), fill=110, width=3)
    cross(150, 120)
    cross(520, 40)
    legend = (LegendEntry(label="Cross", group=None, line=False, box=(490 / 600, 0.0, 0.92, 0.2)),)
    spots = [s.spot.box for s in read_inline(np.asarray(image), legend).sightings]
    assert len(spots) == 1 and abs((spots[0][0] + spots[0][2]) / 2 * 600 - 150) < 3
