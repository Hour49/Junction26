"""The `graph` runs reader (app/adapters/discipline_pictures/runs_graph.py) on drawn pictures of
known length: lines thinned into a graph, junctions, bridged gaps, styles kept apart."""

import math
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image, ImageDraw
from test_picture_lane import SheetKind, _ask, _ingest, _settings, heating_scan

from app import composition
from app.adapters.discipline_pictures.lane import PictureLane
from app.adapters.discipline_pictures.mask import MaskReader
from app.adapters.discipline_pictures.runs_graph import GraphReader, read_graph, thin
from app.composition import build_ingest
from app.core.picture_facts import LegendEntry, PictureReading

W, H = 800, 400
M_PER_PX = 0.01  # 1 px = 1 cm
RED, BLUE, BROWN = (214, 39, 40), (31, 119, 180), (140, 86, 75)


def legend_at(label: str, y: int) -> LegendEntry:
    """A legend line sample drawn by `picture` at the right edge, row `y`."""
    return LegendEntry(
        label=label, group=None, line=True, box=(700 / W, y / H, 780 / W, (y + 10) / H)
    )


def picture(draw: Sequence[Any]) -> np.ndarray:
    """A white page: each (label, colour, polyline, dash) drawn 3 px wide, its legend sample."""
    image = Image.new("RGB", (W, H), "white")
    pen = ImageDraw.Draw(image)
    for row, (_, colour, line, dash) in enumerate(draw):
        y = 20 + 20 * row
        segments = [((705, y + 5), (775, y + 5)), *pairwise(line)]
        for a, b in segments:
            if dash is None:
                pen.line([a, b], fill=colour, width=3)
                continue
            on, off = dash
            length = math.dist(a, b)
            for start in np.arange(0, length, on + off):
                t0, t1 = start / length, min(start + on, length) / length
                p = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
                q = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                pen.line([p, q], fill=colour, width=3)
    return np.asarray(image)


def legend_of(draw: Sequence[Any]) -> tuple[LegendEntry, ...]:
    return tuple(legend_at(label, 20 + 20 * row) for row, (label, *_) in enumerate(draw))


def lengths(reading: PictureReading) -> dict[str, list[float]]:
    found: dict[str, list[float]] = {}
    for run in reading.runs:
        found.setdefault(run.label, []).append(run.length_m)
    return {k: sorted(v, reverse=True) for k, v in found.items()}


def test_a_straight_line_is_one_run_of_its_length() -> None:
    draw = [("Supply", RED, [(50, 200), (550, 200)], None)]
    reading, graph = read_graph(picture(draw), legend_of(draw), M_PER_PX)
    assert lengths(reading)["Supply"] == [pytest.approx(5.0, rel=0.02)]
    (edge,) = graph.edges
    assert (edge.style, edge.bridged) == ("Supply", False)
    assert sorted(n.degree for n in graph.nodes) == [1, 1]
    assert graph.px_per_m == pytest.approx(100.0) and graph.size_px == (W, H)


def test_a_tee_is_one_run_with_a_junction() -> None:
    draw = [("Supply", RED, [(50, 200), (550, 200)], None), ("x", RED, [], None)]
    image = picture(draw[:1])
    pen_image = Image.fromarray(image)
    ImageDraw.Draw(pen_image).line([(300, 200), (300, 350)], fill=RED, width=3)
    reading, graph = read_graph(np.asarray(pen_image), legend_of(draw[:1]), M_PER_PX)
    assert lengths(reading)["Supply"] == [pytest.approx(6.5, rel=0.03)]
    assert sorted(n.degree for n in graph.nodes) == [1, 1, 1, 3]
    assert len(graph.edges) == 3


def test_a_gap_where_a_symbol_sits_is_bridged_up_to_the_bound() -> None:
    draw = [("Supply", RED, [(50, 200), (550, 200)], None)]
    image = Image.fromarray(picture(draw))
    ImageDraw.Draw(image).rectangle((290, 185, 310, 215), fill="white", outline="black", width=2)
    rgb = np.asarray(image)
    reading, graph = read_graph(rgb, legend_of(draw), M_PER_PX, bridge_m=0.5)
    assert lengths(reading)["Supply"] == [pytest.approx(5.0, rel=0.03)]  # the gap counted
    assert [e.bridged for e in graph.edges].count(True) == 1
    # a gap wider than the bound stays a gap: two runs, the symbol's width not counted
    reading, _ = read_graph(rgb, legend_of(draw), M_PER_PX, bridge_m=0.1)
    assert lengths(reading)["Supply"] == [
        pytest.approx(2.4, abs=0.05),
        pytest.approx(2.4, abs=0.05),
    ]


def test_ends_that_do_not_point_at_each_other_are_not_bridged() -> None:
    # two parallel lines whose ends are 20 px apart side by side, not in line
    draw = [("Supply", RED, [(50, 200), (300, 200)], None)]
    image = Image.fromarray(picture(draw))
    ImageDraw.Draw(image).line([(50, 220), (300, 220)], fill=RED, width=3)
    reading, graph = read_graph(np.asarray(image), legend_of(draw), M_PER_PX, bridge_m=0.5)
    assert lengths(reading)["Supply"] == [pytest.approx(2.5, rel=0.03)] * 2
    assert not any(e.bridged for e in graph.edges)


def test_two_styles_that_cross_stay_apart() -> None:
    draw = [
        ("Supply", RED, [(50, 200), (550, 200)], None),
        ("Return", BLUE, [(300, 50), (300, 350)], None),
    ]
    reading, graph = read_graph(picture(draw), legend_of(draw), M_PER_PX)
    found = lengths(reading)
    # the one drawn last is whole; the other is cut where it is drawn over, then bridged
    assert found["Return"] == [pytest.approx(3.0, rel=0.03)]
    assert found["Supply"] == [pytest.approx(5.0, rel=0.03)]
    styles = {e.style for e in graph.edges}
    assert styles == {"Supply", "Return"}
    for node in graph.nodes:  # no node joins edges of two styles
        assert len({e.style for e in graph.edges if node.id in (e.a, e.b)}) == 1


def test_a_dashed_line_is_one_run_across_its_gaps() -> None:
    # 4 px dashes thin to dots with no direction: only closing the gaps first joins them
    draw = [("Exhaust", RED, [(50, 200), (550, 200)], (4, 4))]
    reading, _ = read_graph(picture(draw), legend_of(draw), M_PER_PX)
    assert lengths(reading)["Exhaust"] == [pytest.approx(5.0, rel=0.03)]


def test_grey_strokes_are_not_a_dull_colour() -> None:
    # black text's anti-aliased edges are grey, and grey 115 is within 50 per channel of a dull
    # brown (140, 86, 75); without the chroma rule a grey stroke becomes a run (pics-runs.md,
    # amendment 1)
    draw = [("Supply air", BROWN, [(50, 300), (550, 300)], None)]
    image = Image.fromarray(picture(draw))
    ImageDraw.Draw(image).line([(60, 80), (460, 80)], fill=(115, 115, 115), width=2)
    reading, _ = read_graph(np.asarray(image), legend_of(draw), M_PER_PX)
    assert lengths(reading)["Supply air"] == [pytest.approx(5.0, rel=0.03)]


def test_thinning_leaves_a_one_pixel_line() -> None:
    mask = np.zeros((20, 60), np.uint8)
    mask[8:13, 5:55] = 1
    line = thin(mask)
    assert line.sum() >= 45 and line[:, 10:50].sum(axis=0).max() == 1


# --- DISCIPLINE_RUNS in the picture lane ------------------------------------------------------


def test_the_default_runs_reader_is_mask_in_its_folder_and_names_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, monkeypatch, discipline_pictures="template",
                         discipline_pictures_cache_dir=tmp_path / "facts")  # fmt: skip
    assert settings.discipline_runs == "mask"
    lane = composition._pictures(settings, object(), object(), None)  # type: ignore[arg-type]
    assert isinstance(lane, PictureLane) and isinstance(lane._mask, MaskReader)  # pyright: ignore[reportPrivateUsage]
    assert lane._sheets.path("0" * 64).parent == tmp_path / "facts"  # pyright: ignore[reportPrivateUsage]
    names = build_ingest(settings, tmp_path / "projects", background=False)._names  # pyright: ignore[reportPrivateUsage]
    assert "discipline_runs" not in names


def test_graph_reads_the_runs_and_keeps_its_own_sheets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, monkeypatch, discipline_pictures="template",
                         discipline_runs="graph",
                         discipline_pictures_cache_dir=tmp_path / "facts")  # fmt: skip
    lane = composition._pictures(settings, object(), object(), None)  # type: ignore[arg-type]
    assert isinstance(lane, PictureLane) and isinstance(lane._mask, GraphReader)  # pyright: ignore[reportPrivateUsage]
    assert lane._sheets.path("0" * 64).parent == tmp_path / "facts" / "runs-graph"  # pyright: ignore[reportPrivateUsage]
    names = build_ingest(settings, tmp_path / "projects", background=False)._names  # pyright: ignore[reportPrivateUsage]
    assert names["discipline_runs"] == "graph"
    status, files = _ingest(settings, heating_scan(), SheetKind())
    assert status.state == "done", status
    (metres,) = _ask(settings, files, "How many metres of heating pipe?")
    said = str(metres.answer)
    length = float(said.split("Total length: ")[1].split(" m")[0])
    assert abs(length - 5.0) <= 0.15, said  # the lane's mask test's 3%
    assert metres.sure is False
