"""Page cleanup before the picture readers (discipline-pictures.md; picture bar 2): a scan's salt
taken out, uneven light flattened, a page turned by a degree or two turned back, and a clean
page left as it is. Every page is drawn in the test: no partner data."""

import io
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from app.adapters.discipline_pictures.cleanup import clean_page
from app.adapters.discipline_pictures.template import read_symbols
from app.core.picture_facts import LegendEntry
from tests.test_discipline_pictures import H, W, found_all, symbol_page

INK = 200


def _page() -> tuple[np.ndarray, tuple[LegendEntry, ...], list[tuple[str, tuple[float, float]]]]:
    data, legend, placed = symbol_page()
    return np.asarray(Image.open(io.BytesIO(data)).convert("L")), legend, placed


def _salted(gray: np.ndarray, share: float, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = gray.copy()
    salt = rng.random(out.shape) < share
    out[salt] = rng.choice(np.array([0, 255], dtype=np.uint8), size=int(salt.sum()))
    return out


def _jpeg(gray: np.ndarray, quality: int = 40) -> np.ndarray:
    _, data = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, quality])
    out = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    assert out is not None
    return out


def test_salt_is_taken_out_and_the_drawing_stays() -> None:
    gray, _, _ = _page()
    cleaned = clean_page(_salted(gray, 0.005)).gray
    ink, kept = gray < INK, cleaned < INK
    assert (kept & ~ink).sum() < 0.0005 * gray.size  # specks left on the paper
    assert (kept & ink).sum() >= 0.95 * ink.sum()  # the drawing's ink kept


def test_light_falling_off_to_one_corner_is_flattened() -> None:
    gray, _, _ = _page()
    ys, xs = np.mgrid[0:H, 0:W]
    light = 1 - 0.35 * (xs / W + ys / H) / 2  # 35% darker in the far corner
    dim = (gray * light).astype(np.uint8)
    paper = gray == 255
    assert np.percentile(dim[paper], 1) < 190  # the dim corner reads as near ink before
    cleaned = clean_page(dim).gray
    assert np.percentile(cleaned[paper], 1) >= 235
    assert (cleaned[gray < 100] < INK).mean() >= 0.95


def test_a_clean_page_keeps_its_one_pixel_lines() -> None:
    page = Image.new("L", (800, 600), 255)
    draw = ImageDraw.Draw(page)
    for y in range(50, 550, 40):
        draw.line((40, y, 760, y), fill=0, width=1)
    gray = np.asarray(page)
    cleaned = clean_page(gray)
    assert cleaned.angle == 0
    assert ((cleaned.gray < INK) == (gray < INK)).all()


def _turned(gray: np.ndarray, degrees: float) -> tuple[np.ndarray, np.ndarray]:
    """The page turned about its centre with the canvas expanded (as a scan), and the 3x3 map of
    the clean page's pixels to the turned one's."""
    image = Image.fromarray(gray).rotate(
        degrees, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255
    )
    cx, cy, nx, ny = W / 2, H / 2, image.width / 2, image.height / 2
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    to = np.array([[c, s, nx - cx * c - cy * s], [-s, c, ny + cx * s - cy * c], [0, 0, 1]])
    return np.asarray(image), to


def test_a_page_turned_a_degree_or_two_is_turned_back() -> None:
    gray, _, _ = _page()
    for degrees in (1.7, -1.2, 0.6):
        turned, _ = _turned(gray, degrees)
        cleaned = clean_page(turned)
        assert abs(cleaned.angle - degrees) <= 0.15, (degrees, cleaned.angle)


def test_template_reads_a_noisy_turned_page_with_its_spots_on_the_page_as_given() -> None:
    """The registration's noisy look: grey, turned 1.5 degrees, blur 1.5, 0.5% salt, JPEG 40."""
    gray, legend, placed = _page()
    turned, to = _turned(gray, 1.5)
    noisy = np.asarray(Image.fromarray(turned).filter(ImageFilter.GaussianBlur(1.5)))
    noisy = _salted(noisy, 0.005)
    noisy = _jpeg(noisy)
    h, w = noisy.shape

    def moved(x: float, y: float) -> tuple[float, float]:
        px, py, _ = to @ (x * W, y * H, 1)
        return px / w, py / h

    def box(b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        corners = [moved(x, y) for x in (b[0], b[2]) for y in (b[1], b[3])]
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        return min(xs), min(ys), max(xs), max(ys)

    on_page = tuple(e.model_copy(update={"box": e.box and box(e.box)}) for e in legend)
    reading = read_symbols(noisy, on_page)
    found_all(reading, [(label, moved(*at)) for label, at in placed])


def test_a_match_in_a_legend_row_s_label_is_the_legend_not_the_plan() -> None:
    """A label may print the symbol's shape again ("▭ TTB"): the whole legend row is the legend."""
    gray, legend, placed = _page()
    page = gray.copy()
    for entry in legend:
        if entry.box is not None:  # the symbol again in the label, 200 px right of the sample
            x0, y0, x1, y1 = (round(v * s) for v, s in zip(entry.box, (W, H, W, H), strict=True))
            page[y0:y1, x0 + 200 : x1 + 200] = gray[y0:y1, x0:x1]
    found_all(read_symbols(page, legend), placed)


def test_on_a_scanned_page_a_symbol_s_near_misses_are_dropped_its_instances_kept() -> None:
    """Blur lifts every correlation on a scan; a template's own instances score alike, near its
    best, and a shape that only looks like it (a triangle with half its base) scores lower."""
    gray, legend, placed = _page()
    page = Image.fromarray(gray)
    draw = ImageDraw.Draw(page)
    for x in range(290, 1550, 280):  # decoys between the symbols' rows and columns
        draw.polygon(((x + 6, 334), (x + 34, 334), (x + 20, 308)), outline=0, width=2)
        draw.line((x + 21, 334, x + 35, 334), fill=255, width=3)
    noisy = np.asarray(page.filter(ImageFilter.GaussianBlur(1.5)))
    noisy = _salted(noisy, 0.005)
    found_all(read_symbols(_jpeg(noisy), legend), placed)
