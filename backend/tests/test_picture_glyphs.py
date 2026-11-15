"""`glyphs` (DISCIPLINE_PICTURES=glyphs): the trained glyph detector's legend binding, tiling and
head decoding, with a fake detector. No model, no partner data."""

import numpy as np

from app.adapters.discipline_pictures.glyphs import TILE, Glyph, bind, decode, read_glyphs, tiled
from app.core.picture_facts import LegendEntry

W, H = 2000, 1200


def legend_row(label: str, x0: float, y0: float) -> LegendEntry:
    return LegendEntry(
        label=label, group=None, line=False, box=(x0 / W, y0 / H, (x0 + 40) / W, (y0 + 30) / H)
    )


def detector(glyphs: list[Glyph]):
    """A fake detector that knows the page's glyphs, in page pixels, and reports each tile's
    share in that tile's pixels (the tile's top-left pixel holds its page position)."""

    def detect(tile: np.ndarray) -> list[Glyph]:
        top, left = int(tile[0, 0, 0]), int(tile[0, 0, 1])
        h, w = tile.shape[:2]
        return [
            Glyph(
                g.style, g.score, (g.box[0] - left, g.box[1] - top, g.box[2] - left, g.box[3] - top)
            )
            for g in glyphs
            if left <= g.centre[0] < left + w and top <= g.centre[1] < top + h
        ]

    return detect


def page() -> np.ndarray:
    """Each pixel holds its own row and column: the fake detector reads a tile's origin."""
    rgb = np.zeros((H, W, 3), dtype=np.int32)
    rgb[..., 0] = np.arange(H)[:, None]
    rgb[..., 1] = np.arange(W)[None, :]
    return rgb


def box(x: float, y: float, r: float = 12) -> tuple[float, float, float, float]:
    return (x - r, y - r, x + r, y + r)


def test_plan_glyphs_take_the_label_of_the_legend_row_with_their_style() -> None:
    legend = (legend_row("Radiator", 1800, 100), legend_row("Valve", 1800, 200))
    glyphs = [
        Glyph(3, 0.9, box(1820, 115)),  # the radiator row's sample
        Glyph(7, 0.9, box(1820, 215)),  # the valve row's sample
        Glyph(3, 0.8, box(300, 300)),
        Glyph(3, 0.7, box(900, 800)),
        Glyph(7, 0.6, box(1500, 1000)),
        Glyph(5, 0.9, box(600, 600)),  # a style no legend row has: not read
    ]
    reading = read_glyphs(page(), legend, detector(glyphs))
    assert sorted(s.label for s in reading.sightings) == ["Radiator", "Radiator", "Valve"]
    assert reading.read == ("Radiator", "Valve")
    assert reading.notes == ()


def test_a_legend_row_with_no_detected_sample_reads_nothing_and_says_so() -> None:
    legend = (legend_row("Radiator", 1800, 100), legend_row("Pump", 1800, 200))
    glyphs = [Glyph(3, 0.9, box(1820, 115)), Glyph(3, 0.8, box(300, 300))]
    reading = read_glyphs(page(), legend, detector(glyphs))
    assert [s.label for s in reading.sightings] == ["Radiator"]
    assert "Pump" in reading.notes[0]


def test_text_right_of_a_legend_sample_is_legend_not_plan() -> None:
    legend = (legend_row("Radiator", 1500, 100),)
    glyphs = [Glyph(3, 0.9, box(1520, 115)), Glyph(3, 0.5, box(1900, 112))]  # same row, far right
    assert read_glyphs(page(), legend, detector(glyphs)).sightings == ()


def test_the_first_row_of_a_style_keeps_it() -> None:
    rows = [("A", (0, 0, 40, 30)), ("B", (0, 100, 40, 130))]
    glyphs = [Glyph(1, 0.9, box(20, 15)), Glyph(1, 0.95, box(20, 115))]
    assert bind(glyphs, rows) == {1: "A"}


def test_a_glyph_seen_by_two_overlapping_tiles_is_counted_once() -> None:
    rgb = np.zeros((H, W, 3), dtype=np.uint8)
    seen = Glyph(2, 0.9, box(900, 500))  # inside the overlap of the tiles at x 0 and x 768

    def detect(tile: np.ndarray) -> list[Glyph]:
        return [seen]  # every tile reports it at the same tile pixels: the merge must not

    found = tiled(rgb, detect)
    assert len(found) == len({(round(g.centre[0]), round(g.centre[1])) for g in found})
    one = tiled(rgb[:TILE, :TILE], detect)
    assert len(one) == 1


def test_decode_takes_each_anchors_best_class_above_the_score() -> None:
    out = np.zeros((4 + 3, 3), dtype=np.float32)
    out[:4, 0] = (100, 50, 20, 20)
    out[4 + 2, 0] = 0.9
    out[:4, 1] = (300, 60, 24, 24)
    out[4 + 0, 1] = 0.1  # below the score
    out[:4, 2] = (500, 70, 10, 30)
    out[4 + 1, 2], out[4 + 0, 2] = 0.6, 0.3
    glyphs = decode(out)
    assert [(g.style, round(g.score, 2)) for g in glyphs] == [(2, 0.9), (1, 0.6)]
    assert glyphs[0].box == (90.0, 40.0, 110.0, 60.0)
    assert glyphs[1].box == (495.0, 55.0, 505.0, 85.0)


def test_glyphs_keeps_its_sheets_apart_from_templates(tmp_path) -> None:
    from app.adapters.discipline_pictures.lane import kept_in

    assert kept_in(tmp_path, "template") == tmp_path
    assert kept_in(tmp_path, "glyphs") == tmp_path / "glyphs"
    assert kept_in(tmp_path, "gemini") == tmp_path / "gemini"
