"""`glyphs` (DISCIPLINE_PICTURES=glyphs): the trained glyph detector's legend binding, tiling and
head decoding, with a fake detector. No model, no partner data."""

import numpy as np

from app.adapters.discipline_pictures import page_box
from app.adapters.discipline_pictures.glyphs import (
    TILE,
    Glyph,
    bind,
    decode,
    glyph_legend,
    own_legend_reading,
    read_glyphs,
    tiled,
)
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


# --- DISCIPLINE_GLYPHS_LEGEND=glyphs: the legend read from the detector's own glyphs -----------
# A legend row is a detected glyph with a printed label right of it; the rows stack in a column.
# Label ink here is a band of short strokes (text-like: many inked rows), pipes are 2 px lines.


def white() -> np.ndarray:
    return np.full((H, W, 3), 255, dtype=np.uint8)


def label(rgb: np.ndarray, glyph: Glyph, width: int = 300) -> None:
    """Text-like ink right of the glyph: 3 px strokes every 6 px, 16 rows tall."""
    x0, cy = int(glyph.box[2]) + 20, int(glyph.centre[1])
    for x in range(x0, x0 + width, 6):
        rgb[cy - 8 : cy + 8, x : x + 3] = 0


class Recognise:
    """A fake OCR recognition: the next label for each crop, crops kept to look at."""

    def __init__(self, *labels: str) -> None:
        self.labels = list(labels)
        self.crops: list[np.ndarray] = []

    def __call__(self, crops):
        self.crops += list(crops)
        return [(self.labels.pop(0), 0.9) for _ in crops]


def test_the_legend_is_the_column_of_glyphs_with_labels_right_of_them() -> None:
    rgb = white()
    rows = [Glyph(1, 0.9, box(1700, 100)), Glyph(2, 0.9, box(1700, 140)),
            Glyph(3, 0.9, box(1700, 220))]  # fmt: skip  # 220: a line style's row between
    for g in rows:
        label(rgb, g)
    on_pipe = Glyph(2, 0.9, box(400, 600))
    rgb[599:601, 420:900] = 0  # a pipe runs right of a plan glyph: no label
    plan = [Glyph(1, 0.9, box(300, 300)), on_pipe]
    legend = glyph_legend(rgb, rows + plan, Recognise("Radiator", "Valve", "Pump"))
    assert legend is not None
    assert [e.label for e in legend] == ["Radiator", "Valve", "Pump"]
    assert not any(e.line for e in legend)
    assert legend[0].box == page_box(*rows[0].box, W, H)


def test_a_one_row_legend_is_a_legend() -> None:
    rgb = white()
    row = Glyph(4, 0.9, box(1700, 100))
    label(rgb, row)
    legend = glyph_legend(rgb, [row, Glyph(4, 0.8, box(300, 300))], Recognise("Radiator"))
    assert legend is not None and [e.label for e in legend] == ["Radiator"]


def test_no_glyph_with_a_label_is_no_legend() -> None:
    rgb = white()
    rgb[299:301, 320:900] = 0  # only a pipe
    assert glyph_legend(rgb, [Glyph(1, 0.9, box(300, 300))], Recognise()) is None


def test_a_label_crop_ends_at_its_text_not_at_scan_salt() -> None:
    rgb = white()
    row = Glyph(1, 0.9, box(1000, 100))
    label(rgb, row, width=300)
    for x in range(1400, 1900, 37):
        rgb[100, x] = 0  # one dark pixel per column: salt, not ink
    seen = Recognise("Radiator")
    glyph_legend(rgb, [row], seen)
    (crop,) = seen.crops
    assert 290 <= crop.shape[1] <= 320


def test_plan_glyphs_take_their_labels_from_the_glyph_legend() -> None:
    rgb = white()
    rows = [Glyph(1, 0.9, box(1700, 100)), Glyph(2, 0.9, box(1700, 140))]
    for g in rows:
        label(rgb, g)
    plan = [
        Glyph(1, 0.9, box(300, 300)),
        Glyph(2, 0.8, box(500, 500)),
        Glyph(2, 0.7, box(700, 900)),
    ]
    reading = own_legend_reading(rgb, rows + plan, Recognise("Radiator", "Valve"))
    assert sorted(s.label for s in reading.sightings) == ["Radiator", "Valve", "Valve"]
    assert [e.label for e in reading.legend or ()] == ["Radiator", "Valve"]


def test_the_glyph_legend_is_off_by_default_and_keeps_its_own_sheets(tmp_path, monkeypatch) -> None:
    from test_picture_lane import _settings

    from app import composition
    from app.adapters.discipline_pictures.glyphs import GlyphReader
    from app.adapters.discipline_pictures.lane import PictureLane
    from app.composition import build_ingest

    def lane(**extra):
        settings = _settings(tmp_path, monkeypatch, discipline_pictures="glyphs",
                             discipline_pictures_cache_dir=tmp_path / "facts", **extra)  # fmt: skip
        built = composition._pictures(settings, object(), object(), None)  # type: ignore[arg-type]
        assert isinstance(built, PictureLane)
        names = build_ingest(settings, tmp_path / "projects", background=False)._names  # pyright: ignore[reportPrivateUsage]
        reader = built._template  # pyright: ignore[reportPrivateUsage]
        assert isinstance(reader, GlyphReader)
        return reader, built._sheets.path("0" * 64).parent, names  # pyright: ignore[reportPrivateUsage]

    reader, kept, names = lane()
    assert reader._recognise is None  # pyright: ignore[reportPrivateUsage]
    assert kept == tmp_path / "facts" / "glyphs"
    assert "discipline_glyphs_legend" not in names
    reader, kept, names = lane(discipline_glyphs_legend="glyphs")
    assert reader._recognise is not None  # pyright: ignore[reportPrivateUsage]
    assert kept == tmp_path / "facts" / "glyphs" / "legend-glyphs"
    assert names["discipline_glyphs_legend"] == "glyphs"
