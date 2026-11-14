"""`paths`: the exact reader of a drawn (vector) PDF's symbols and runs, page 1, no model call.

- A symbol is the group of paths drawn in a legend entry's box. A copy of it on the plan is a
  path shaped and styled like the group's largest path (its points' distances to their centre,
  which turning and moving keep) with each other path of the group, likewise shaped, at the same
  distance from it.
- A run is a path stroked like a legend line entry's sample (colour and width); its length is
  its drawn length at the sheet's scale (scale.py). Without a scale there are no runs and the
  notes say `NO_SCALE`. A sample drawn as dashes is a dashed line: its runs are rows of dashes of
  its length (`chained`), and a solid line of the same stroke leaves those dashes alone.
  shortcut: a dash set by the PDF's dash array (`d` operator) is not seen, `PdfPath` does not
  carry it; add it to objects.py when a sheet draws dashes that way.

Paths inside a legend box are the legend, never the plan.
"""

import math
from collections.abc import Sequence
from itertools import pairwise

import pypdfium2

from app.adapters.discipline_pictures import (
    NO_LEGEND,
    Dashes,
    LegendOf,
    Piece,
    chained,
    dash_pattern,
    is_dash,
    nothing,
)
from app.adapters.vector_pdf import (
    _page_behind,  # pyright: ignore[reportPrivateUsage]
    frame,
)
from app.adapters.vector_pdf.objects import (
    FILL_NONE,
    Bounds,
    PdfPage,
    PdfPath,
    Point,
    bounds_of,
)
from app.adapters.vector_pdf.scale import read_scale
from app.core.drawing.model import Box
from app.core.ifc_facts import Spot
from app.core.picture_facts import NO_SCALE, LegendEntry, PictureReading, Run, Sighting
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles

READER = "paths"
PAD = 1.0  # points around a legend box
TOLERANCE = 0.1  # points, plus 1% of the size: two shapes or distances are the same
WIDTH = 0.01  # points: two stroke widths are the same


class PathsReader:
    def __init__(self, files: DrawingFiles, legend_of: LegendOf) -> None:
        self._files = files
        self._legend_of = legend_of

    def read(self, source: DrawingFile, sheet: Sheet) -> PictureReading:
        legend = self._legend_of(source, sheet)
        if legend is None:
            return nothing(READER, None, f"{READER}: {NO_LEGEND}")
        try:
            page = _page_behind(self._files, source, sheet)
        except pypdfium2.PdfiumError as error:
            return nothing(READER, legend, f"{READER}: the PDF cannot be read ({error})")
        if isinstance(page, str):
            return nothing(READER, legend, f"{READER}: {page}")
        return read_vector(page, legend)


def read_vector(page: PdfPage, legend: tuple[LegendEntry, ...]) -> PictureReading:
    boxes = [(entry, _points(entry.box, page)) for entry in legend if entry.box is not None]
    plan = [p for p in page.paths if not any(_inside(p.bounds, at) for _, at in boxes)]
    used: set[int] = set()
    read: list[str] = []
    notes: list[str] = []
    sightings: list[Sighting] = []
    for entry, at in boxes:
        if entry.line:
            continue
        group = [p for p in page.paths if _inside(p.bounds, at)]
        if not group:
            notes.append(f"{READER}: nothing is drawn at the legend's {entry.label!r}")
            continue
        read.append(entry.label)
        for copy in _copies(group, plan, used):
            sightings.append(
                Sighting(
                    label=entry.label,
                    spot=Spot(page=1, box=_box([p.bounds for p in copy], page), reader=READER),
                )
            )
    runs: list[Run] = []
    scale, _ = read_scale(page)
    if scale.m_per_unit is None:
        notes.append(NO_SCALE)
    else:
        m_per_pt = scale.m_per_unit

        def run(label: str, length: float, bounds: Bounds) -> Run:
            return Run(
                label=label,
                size=None,  # shortcut: sizes printed along runs are not read; VLM tiles will
                length_m=length * m_per_pt,
                spots=(Spot(page=1, box=_box([bounds], page), reader=READER),),
            )

        lines: list[tuple[LegendEntry, PdfPath, Dashes | None]] = []
        for entry, at in boxes:
            if not entry.line:
                continue
            drawn = [p for p in page.paths if p.stroked and _inside(p.bounds, at)]
            if not drawn:
                notes.append(f"{READER}: no line is drawn at the legend's {entry.label!r}")
                continue
            sample = max(drawn, key=_length)
            pieces = [_piece(r) for p in drawn if _styled_like(p, sample) for r in _rings(p)]
            lines.append((entry, sample, dash_pattern(pieces)))
        free = [p for i, p in enumerate(plan) if i not in used]
        for entry, sample, dashes in lines:
            read.append(entry.label)
            styled = [p for p in free if _styled_like(p, sample)]
            if dashes is not None:
                pieces = [_piece(r) for p in styled for r in _rings(p)]
                runs += [run(entry.label, n, box) for n, box in chained(pieces, dashes)]
                continue
            # a solid line leaves the dashes of a dashed line in its style to that line
            dashed = [d for _, s, d in lines if d is not None and _styled_like(s, sample)]
            runs += [
                run(entry.label, _length(p), p.bounds)
                for p in styled
                if not any(all(is_dash(_piece(r), d) for r in _rings(p)) for d in dashed)
            ]
    return PictureReading(
        reader=READER,
        legend=legend,
        read=tuple(read),
        sightings=tuple(sightings),
        runs=tuple(runs),
        notes=tuple(notes),
    )


def _copies(group: list[PdfPath], plan: list[PdfPath], used: set[int]) -> list[list[PdfPath]]:
    """The copies of the legend's `group` of paths on the plan; their indexes join `used`."""
    anchor = max(group, key=lambda p: len(p.points))
    rest = [p for p in group if p is not anchor]
    home = _centre(anchor.points)
    copies: list[list[PdfPath]] = []
    for i, candidate in enumerate(plan):
        if i in used or not _alike(candidate, anchor):
            continue
        here = _centre(candidate.points)
        found = [i]
        for part in rest:
            reach = math.dist(_centre(part.points), home)
            match = next(
                (
                    j
                    for j, p in enumerate(plan)
                    if j not in used
                    and j not in found
                    and _alike(p, part)
                    and _close(math.dist(_centre(p.points), here), reach)
                ),
                None,
            )
            if match is None:
                break
            found.append(match)
        else:
            used.update(found)
            copies.append([plan[j] for j in found])
    return copies


def _alike(a: PdfPath, b: PdfPath) -> bool:
    """The same style and the same shape, wherever and however turned."""
    if (a.stroked, a.fill_mode, a.segments) != (b.stroked, b.fill_mode, b.segments):
        return False
    if a.stroked and not _styled_like(a, b):
        return False
    if a.fill_mode != FILL_NONE and a.fill != b.fill:
        return False
    da, db = _spread(a), _spread(b)
    return len(da) == len(db) and all(_close(x, y) for x, y in zip(da, db, strict=True))


def _styled_like(a: PdfPath, b: PdfPath) -> bool:
    return a.stroked and a.stroke == b.stroke and abs(a.width - b.width) <= WIDTH


def _spread(path: PdfPath) -> list[float]:
    centre = _centre(path.points)
    return sorted(math.dist(point, centre) for point in path.points)


def _centre(points: Sequence[Point]) -> Point:
    return sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points)


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE + 0.01 * max(a, b)


def _length(path: PdfPath) -> float:
    """Drawn length in points (a curve as its end points: their control points are not read)."""
    return sum(math.dist(p, q) for ring in path.rings for p, q in pairwise(ring))


def _rings(path: PdfPath) -> list[tuple[Point, ...]]:
    return [ring for ring in path.rings if len(ring) > 1]


def _piece(ring: tuple[Point, ...]) -> Piece:
    x0, y0, x1, y1 = bounds = bounds_of(ring)
    length = sum(math.dist(p, q) for p, q in pairwise(ring))
    return Piece(length=length, centre=((x0 + x1) / 2, (y0 + y1) / 2), box=bounds)


def _points(box: Box, page: PdfPage) -> Bounds:
    x0, y0, x1, y1 = box
    return (
        x0 * page.width - PAD,
        y0 * page.height - PAD,
        x1 * page.width + PAD,
        y1 * page.height + PAD,
    )


def _inside(bounds: Bounds, box: Bounds) -> bool:
    return (
        box[0] <= bounds[0] and box[1] <= bounds[1] and bounds[2] <= box[2] and bounds[3] <= box[3]
    )


def _box(bounds: list[Bounds], page: PdfPage) -> Box:
    return frame.box([corner for b in bounds for corner in (b[:2], b[2:])], page)
