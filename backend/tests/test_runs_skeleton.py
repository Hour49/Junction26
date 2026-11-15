"""`runs_skeleton`: run length from a greyscale raster (no colour): lines told apart by their grey
and dash pattern, measured along their skeleton."""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from app.adapters.discipline_pictures.runs_skeleton import read_runs, skeleton_length, thin
from app.core.picture_facts import LegendEntry, PictureReading

W, H = 1000, 800
M_PER_PX = 0.01
LEGEND_X = 850  # legend samples sit at x 850-950


def sample(
    draw: ImageDraw.ImageDraw, row: int, grey: int, dash: tuple[int, int] | None
) -> LegendEntry:
    y = 40 + 30 * row
    line(draw, (LEGEND_X, y), (LEGEND_X + 100, y), grey, dash)
    return LegendEntry(
        label=f"system {row}",
        group=None,
        line=True,
        box=((LEGEND_X - 5) / W, (y - 10) / H, (LEGEND_X + 105) / W, (y + 10) / H),
    )


def line(
    draw: ImageDraw.ImageDraw,
    a: tuple[float, float],
    b: tuple[float, float],
    grey: int,
    dash: tuple[int, int] | None,
    width: int = 2,
) -> None:
    """Drawn the way the bench renderer draws a run: dashes from the start, the last one cut."""
    if dash is None:
        draw.line([a, b], fill=grey, width=width)
        return
    length, (on, off) = math.dist(a, b), dash
    for start in np.arange(0, length, on + off):
        t0, t1 = start / length, min(start + on, length) / length
        draw.line(
            [
                (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1),
            ],
            fill=grey,
            width=width,
        )


def total(reading: PictureReading, label: str) -> float:
    return sum(r.length_m for r in reading.runs if r.label == label)


def page() -> tuple[Image.Image, tuple[LegendEntry, ...]]:
    """A dark grey L-shaped run (500 + 300 px), a light grey diagonal (400 px), a dashed run in the
    dark grey (400 px), a black symbol on the L and black text beside it."""
    image = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 780, 760), fill=217)  # a wall in the background's light grey
    draw.rectangle((60, 60, 760, 740), fill=255)
    legend = (sample(draw, 0, 100, None), sample(draw, 1, 150, None), sample(draw, 2, 100, (14, 6)))
    line(draw, (100, 100), (600, 100), 100, None)
    line(draw, (600, 100), (600, 400), 100, None)
    line(draw, (150, 650), (150 + 400 / math.sqrt(2), 650 - 400 / math.sqrt(2)), 150, None)
    line(draw, (300, 700), (700, 700), 100, (14, 6))
    draw.ellipse((340, 90, 360, 110), outline=0, fill=255, width=2)  # a symbol on the L
    draw.text((200, 110), "25 mm", fill=0)
    return image, legend


def test_each_grey_and_dash_is_its_own_run_measured_along_the_drawing() -> None:
    image, legend = page()
    reading = read_runs(np.asarray(image), legend, M_PER_PX)
    assert abs(total(reading, "system 0") - 8.0) <= 0.08 * 8.0  # the symbol hides a few px
    assert abs(total(reading, "system 1") - 4.0) <= 0.03 * 4.0
    assert abs(total(reading, "system 2") - 4.0) <= 0.03 * 4.0
    assert reading.read == ("system 0", "system 1", "system 2")


def test_a_scan_greyed_blurred_and_salted_reads_the_same_runs() -> None:
    image, legend = page()
    image = image.filter(ImageFilter.GaussianBlur(1))
    pixels = np.array(image)
    salt = np.random.default_rng(0).random(pixels.shape) < 0.005
    pixels[salt] = 0
    reading = read_runs(pixels, legend, M_PER_PX)
    assert abs(total(reading, "system 0") - 8.0) <= 0.1 * 8.0
    assert abs(total(reading, "system 1") - 4.0) <= 0.1 * 4.0
    assert abs(total(reading, "system 2") - 4.0) <= 0.1 * 4.0


def test_two_legend_lines_drawn_alike_are_refused_not_guessed() -> None:
    image, legend = page()
    draw = ImageDraw.Draw(image)
    twin = sample(draw, 3, 150, None)  # a second system in the light grey, solid
    reading = read_runs(np.asarray(image), (*legend, twin), M_PER_PX)
    assert "system 1" not in reading.read and "system 3" not in reading.read
    assert total(reading, "system 1") == 0 and total(reading, "system 3") == 0
    assert any("system 1" in note and "system 3" in note for note in reading.notes)
    assert "system 0" in reading.read  # the others still answer


def test_a_black_legend_line_is_not_read() -> None:
    image, legend = page()
    black = sample(ImageDraw.Draw(image), 3, 0, None)
    reading = read_runs(np.asarray(image), (*legend, black), M_PER_PX)
    assert "system 3" not in reading.read
    assert any("system 3" in note for note in reading.notes)


def test_an_rgb_page_is_read_as_its_grey() -> None:
    image, legend = page()
    reading = read_runs(np.asarray(image.convert("RGB")), legend, M_PER_PX)
    assert abs(total(reading, "system 1") - 4.0) <= 0.03 * 4.0


def test_thinning_leaves_a_one_pixel_line_whose_length_is_the_drawn_length() -> None:
    mask = np.zeros((60, 300), np.uint8)
    mask[20:24, 50:250] = 1  # 200 px long, 4 wide
    skeleton = thin(mask)
    assert skeleton.sum() <= 202
    assert abs(skeleton_length(skeleton) - 200) <= 6
    diagonal = np.zeros((300, 300), np.uint8)
    for k in range(10, 210):
        diagonal[k, k : k + 3] = 1
    assert abs(skeleton_length(thin(diagonal)) - 200 * math.sqrt(2)) <= 8
