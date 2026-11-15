"""`graph`: the local reader of a raster services picture's runs as a line graph
(DISCIPLINE_RUNS=graph; pre-registered in .agents/exp/pics-runs.md).

For each legend line entry drawn in a colour of its own: the page's pixels of that colour, outside
the legend (a dashed style keeps the pieces of its dash length, as `mask` splits them; a solid
style of the same colour keeps the rest), thinned to one-pixel centre lines (Zhang-Suen), cut into
a graph: nodes at ends and junctions, edges along the pixel chains between them, each a simplified
polyline. Spurs of the thinning are pruned. A gap is bridged between two ends of one style that
point at each other, at most BRIDGE_M of the building apart: where a symbol or a printed size
interrupts the line. A dashed style's dashes are first closed into one line (a closing as wide as
the legend sample's gap); a style that shares its colour with another keeps only its own pieces.
A run is one connected component of a style; its length is the sum of its edges, bridges included,
at the sheet's scale. The graph (`app/core/picture_graph.py`) is
what `picture_graph` hangs terminals on. Black and grey lines are not read (as `mask`).
"""

import math
from collections import defaultdict
from collections.abc import Mapping
from itertools import pairwise
from typing import NamedTuple

import cv2
import numpy as np

from app.adapters.discipline_pictures import (
    NO_LEGEND,
    Dashes,
    LegendOf,
    Piece,
    ScaleOf,
    dash_pattern,
    is_dash,
    nothing,
    page_box,
    pixels,
    read_image,
)
from app.adapters.discipline_pictures.mask import size_of
from app.core.ifc_facts import Spot
from app.core.picture_facts import NO_SCALE, LegendEntry, PictureReading, Run
from app.core.picture_graph import LineEdge, LineGraph, LineNode
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles

READER = "graph"
COLOURFUL = 60  # max - min channel: a pixel with a colour (as mask)
SAME_COLOUR = 50  # per channel: a pixel drawn in the legend line's colour (as mask)
CHROMA_SHARE = 0.5  # and at least this share of its colourfulness (max - min channel)
PAD = 2  # pixels around a legend box
BRIDGE_M = 1.0  # the largest gap bridged, building metres (clinic: 22/50; 0.5: 21, 0.25: 18)
# Elbows and tees joined up to here, building metres. 0: off. 1.0 m was fit on clinic and failed its
# pre-registered line on DigitalHub (pair precision 0.73 / recall 0.19 vs 0.9 / 0.5), so off
JOIN_M = 0.0
BRIDGE_ANGLE = 30.0  # degrees between an end's direction and the gap, at both ends
BACK_PX = 8  # an end's direction: from this far back along its edge
SPUR_WIDTHS = 2.0  # an end edge on a junction this many line widths long or less is a spur
EPSILON_PX = 1.0  # polyline simplification
MAX_CLOSE_PX = 11  # the widest closing that joins a dashed style's dashes


class GraphReader:
    def __init__(self, files: DrawingFiles, legend_of: LegendOf, scale_of: ScaleOf) -> None:
        self._files = files
        self._legend_of = legend_of
        self._scale_of = scale_of

    def read(self, source: DrawingFile, sheet: Sheet) -> PictureReading:
        legend = self._legend_of(source, sheet)
        if legend is None:
            return nothing(READER, None, f"{READER}: {NO_LEGEND}")
        m_per_unit = self._scale_of(source, sheet).m_per_unit
        if m_per_unit is None:
            return nothing(READER, legend, NO_SCALE)
        rgb = read_image(READER, self._files.read(source.path), source, sheet)
        if isinstance(rgb, PictureReading):
            return rgb.model_copy(update={"legend": legend})
        reading, _ = read_graph(rgb, legend, m_per_unit * sheet.pages[0].width / rgb.shape[1])
        return reading


def read_graph(
    rgb: np.ndarray,
    legend: tuple[LegendEntry, ...],
    m_per_px: float,
    bridge_m: float = BRIDGE_M,
    join_m: float | None = None,
) -> tuple[PictureReading, LineGraph]:
    """The picture's runs, one per connected component of each legend line style, and the graph
    they were read from."""
    height, width = rgb.shape[:2]
    on_legend = [pixels(e.box, width, height, PAD) for e in legend if e.box is not None]
    notes: list[str] = []
    styles: list[tuple[LegendEntry, np.ndarray, Dashes | None]] = []
    for entry in legend:
        if not entry.line or entry.box is None:
            continue
        colour = _colour(rgb, entry.box)
        if colour is None:
            notes.append(f"{READER}: the legend's {entry.label!r} has no colour of its own")
            continue
        x0, y0, x1, y1 = pixels(entry.box, width, height)
        sample = [piece for piece, _ in _pieces(_mask(rgb[y0:y1, x0:x1], colour))]
        styles.append((entry, colour, dash_pattern(sample)))
    masks: dict[str, np.ndarray] = {}
    for entry, colour, dashes in styles:
        mask = _mask(rgb, colour)
        for x0, y0, x1, y1 in on_legend:
            mask[y0:y1, x0:x1] = 0
        same = [d for e, c, d in styles if e is not entry and _same(c, colour)]
        ink = _own_pieces(mask, dashes, [dashes, *same]) if same else mask
        if dashes is not None:  # the dashes closed into one line, across their gaps
            k = min(MAX_CLOSE_PX, round(dashes.gap) + 2)
            ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
        masks[entry.label] = ink
    runs, graph = graph_of_masks(masks, (width, height), m_per_px, bridge_m, join_m)
    reading = PictureReading(
        reader=READER,
        legend=legend,
        read=tuple(entry.label for entry, _, _ in styles),
        runs=runs,
        notes=tuple(notes),
    )
    return reading, graph


def graph_of_masks(
    masks: Mapping[str, np.ndarray],
    size_px: tuple[int, int],
    m_per_px: float,
    bridge_m: float = BRIDGE_M,
    join_m: float | None = None,
) -> tuple[tuple[Run, ...], LineGraph]:
    """Runs and their graph from ready line masks: style label (a legend line's label) -> its
    pixels (height x width = `size_px` reversed, nonzero = the line), at `m_per_px`. Each mask is
    thinned, cut into nodes and edges, its gaps bridged up to `bridge_m` of the building; a run
    is one connected network of a style. The entry for a mask made by another reader (a learned
    line segmenter): legend-less pixels, any style names."""
    builder = _Builder(m_per_px)
    width, height = size_px
    for style, mask in masks.items():
        if mask.shape[:2] != (height, width):
            raise ValueError(f"the mask of {style!r} is {mask.shape[:2]}, not {(height, width)}")
        ink = (np.asarray(mask) > 0).astype(np.uint8)
        join = JOIN_M if join_m is None else join_m
        builder.add(style, ink, max(1, int(bridge_m / m_per_px)), int(join / m_per_px))
    graph = builder.graph(width, height)
    joins = builder.uncounted()
    runs = tuple(
        Run(
            label=style,
            size=size_of(style),
            length_m=sum(e.length_m or 0.0 for e in edges if e.id not in joins),
            spots=(Spot(page=1, box=page_box(*_bounds(edges), width, height), reader=READER),),
        )
        for style, edges in _components(graph)
    )
    return runs, graph


# --- pixels -------------------------------------------------------------------------------


def _mask(rgb: np.ndarray, colour: np.ndarray) -> np.ndarray:
    """The pixels of the line's colour, and as colourful: the grey edge of black text is near a
    dull colour channel by channel (brown 140,86,75 against grey 120), but has no colour."""
    pixels = rgb.astype(np.int16)
    near = np.all(np.abs(pixels - colour) <= SAME_COLOUR, axis=2)
    chroma = pixels.max(axis=2) - pixels.min(axis=2)
    return (near & (chroma >= CHROMA_SHARE * (colour.max() - colour.min()))).astype(np.uint8)


def _same(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(np.all(np.abs(a - b) <= SAME_COLOUR))


def _colour(rgb: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray | None:
    """The median colour of the coloured pixels in `box`; None when it has none."""
    x0, y0, x1, y1 = pixels(box, rgb.shape[1], rgb.shape[0])
    crop = rgb[y0:y1, x0:x1].reshape(-1, 3).astype(np.int16)
    coloured = crop[crop.max(axis=1) - crop.min(axis=1) >= COLOURFUL]
    return np.median(coloured, axis=0) if len(coloured) else None


def _pieces(mask: np.ndarray) -> list[tuple[Piece, int]]:
    """Each connected piece of `mask` as a strip (length in px, centre, pixel box), its label."""
    count, labels, stats, centres = cv2.connectedComponentsWithStats(mask, connectivity=8)
    found: list[tuple[Piece, int]] = []
    for k in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[k])
        piece = (labels[y : y + h, x : x + w] == k).astype(np.uint8)
        contours, _ = cv2.findContours(piece, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        half = (sum(cv2.arcLength(c, closed=True) for c in contours) + 4) / 2
        length = (half + math.sqrt(max(0.0, half * half - 4 * area))) / 2
        cx, cy = centres[k]
        found.append((Piece(length, (float(cx), float(cy)), (x, y, x + w, y + h)), k))
    return found


def _own_pieces(
    mask: np.ndarray, dashes: Dashes | None, same_colour: list[Dashes | None]
) -> np.ndarray:
    """The pieces of `mask` that are this style's: a dashed style's pieces of its dash length; a
    solid style's pieces that are no dash of a dashed style in its colour."""
    dashed = [d for d in same_colour if d is not None]
    if dashes is None and not dashed:
        return mask
    count, found = cv2.connectedComponents(mask, connectivity=8)
    labels = np.asarray(found, dtype=np.intp)
    keep = np.zeros(count, dtype=bool)
    for piece, k in _pieces(mask):
        if dashes is not None:
            nearest = min(dashed, key=lambda d: abs(piece.length - d.dash))
            keep[k] = nearest == dashes and is_dash(piece, dashes)
        else:
            keep[k] = not any(is_dash(piece, d) for d in dashed)
    return keep[labels].astype(np.uint8)


def thin(mask: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning of a 0/1 mask to one-pixel centre lines (8-connected)."""
    img = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p = img
            p2, p3, p4 = p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:]
            p5, p6, p7 = p[2:, 2:], p[2:, 1:-1], p[2:, :-2]
            p8, p9 = p[1:-1, :-2], p[:-2, :-2]
            ring = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            b = sum(n.astype(np.int16) for n in ring[:-1])
            a = sum(((x == 0) & (y == 1)).astype(np.int16) for x, y in pairwise(ring))
            if step == 0:
                c, d = p2 * p4 * p6, p4 * p6 * p8
            else:
                c, d = p2 * p4 * p8, p2 * p6 * p8
            gone = (p[1:-1, 1:-1] == 1) & (b >= 2) & (b <= 6) & (a == 1) & (c == 0) & (d == 0)
            if gone.any():
                img[1:-1, 1:-1][gone] = 0
                changed = True
        if not changed:
            return img[1:-1, 1:-1]


# --- graph --------------------------------------------------------------------------------

_STEPS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


class _Builder:
    """Nodes and edges of every style: the ink, then the bridges, then the joins."""

    def __init__(self, m_per_px: float) -> None:
        self._m_per_px = m_per_px
        self.nodes: list[LineNode] = []
        self.edges: list[LineEdge] = []
        self.counted: list[bool] = []  # per edge: its length is a run's (a join's is not)

    def add(self, style: str, ink: np.ndarray, bridge_px: int, join_px: int = 0) -> None:
        if not ink.any():
            return
        ys, xs = np.nonzero(ink)
        y0, x0 = max(0, int(ys.min()) - 1), max(0, int(xs.min()) - 1)
        crop = ink[y0 : int(ys.max()) + 2, x0 : int(xs.max()) + 2]
        skeleton = thin(crop)
        width = float(crop.sum()) / max(1.0, float(skeleton.sum()))  # the line's width in px
        nodes, edges = _trace(skeleton)
        nodes, edges = _pruned(nodes, edges, SPUR_WIDTHS * width)
        at = {k: (float(x + x0), float(y + y0)) for k, (x, y) in nodes.items()}
        degree: dict[int, int] = defaultdict(int)
        for a, b, _ in edges:
            degree[a] += 1
            degree[b] += 1
        local: list[_Local] = []
        for a, b, chain in edges:
            points = [at[a], *((float(x + x0), float(y + y0)) for x, y in chain), at[b]]
            local.append(_Local(a, b, _simplified(points), "ink"))
        ends = {k for k in nodes if degree[k] == 1}
        for a, b in _bridges(ends, at, edges, x0, y0, bridge_px):
            degree[a] += 1
            degree[b] += 1
            local.append(_Local(a, b, [at[a], at[b]], "bridge"))
        if join_px > 0:
            local = _joined(local, at, degree, join_px)
        base = len(self.nodes)
        ids = {k: f"n{base + i + 1}" for i, k in enumerate(at)}
        self.nodes += [LineNode(id=ids[k], at=at[k], degree=degree[k]) for k in at]
        for edge in local:
            bridged = edge.kind != "ink"
            self.edges.append(self._edge(style, ids[edge.a], ids[edge.b], edge.points, bridged))
            self.counted.append(edge.kind != "join")

    def _edge(
        self, style: str, a: str, b: str, points: list[tuple[float, float]], bridged: bool
    ) -> LineEdge:
        length = sum(math.dist(p, q) for p, q in pairwise(points))
        return LineEdge(
            id=f"e{len(self.edges) + 1}",
            a=a,
            b=b,
            style=style,
            points=tuple((round(x, 1), round(y, 1)) for x, y in points),
            length_m=length * self._m_per_px,
            bridged=bridged,
        )

    def graph(self, width: int, height: int) -> LineGraph:
        return LineGraph(
            nodes=tuple(self.nodes),
            edges=tuple(self.edges),
            px_per_m=1.0 / self._m_per_px,
            size_px=(width, height),
        )

    def uncounted(self) -> set[str]:
        """The ids of the joins: edges whose length is no run's."""
        return {
            edge.id for edge, counted in zip(self.edges, self.counted, strict=True) if not counted
        }


class _Local(NamedTuple):
    a: int
    b: int
    points: list[tuple[float, float]]
    kind: str  # "ink", "bridge" (facing ends: a symbol's or a label's gap), "join" (elbow, tee)


def _joined(
    local: list[_Local],
    at: dict[int, tuple[float, float]],
    degree: dict[int, int],
    join_px: int,
) -> list[_Local]:
    """`local` with the joins of one style: an end to another end at any angle (an elbow), or to
    the nearest point inside an edge, split there at a new node (a tee); within `join_px`, only
    between parts not yet connected, nearest first, each end once. New nodes go into `at` and
    `degree`."""
    parent = {k: k for k in at}

    def root(n: int) -> int:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for edge in local:
        parent[root(edge.a)] = root(edge.b)
    ends = sorted(k for k in at if degree[k] == 1)
    found: list[tuple[float, int, int, int, float, tuple[float, float]]] = []
    for i, p in enumerate(ends):  # elbows: (gap, end, other end, -1, 0, its point)
        for q in ends[i + 1 :]:
            gap = math.dist(at[p], at[q])
            if gap <= join_px and root(p) != root(q):
                found.append((gap, p, q, -1, 0.0, at[q]))
    segments = [
        (e, s, edge.points[s], edge.points[s + 1])
        for e, edge in enumerate(local)
        if edge.kind == "ink"
        for s in range(len(edge.points) - 1)
    ]
    if segments:
        a = np.array([seg[2] for seg in segments])
        b = np.array([seg[3] for seg in segments])
        ab = b - a
        lengths = np.maximum((ab * ab).sum(axis=1), 1e-9)
        for p in ends:  # tees: (gap, end, -1, edge index, its segment + share along it, point)
            t = np.clip(((np.array(at[p]) - a) * ab).sum(axis=1) / lengths, 0.0, 1.0)
            near = a + ab * t[:, None]
            gaps = np.hypot(*(near - np.array(at[p])).T)
            for j in np.argsort(gaps):
                if gaps[j] > join_px:
                    break
                e, s = segments[j][0], segments[j][1]
                if root(local[e].a) != root(p):
                    point = (float(near[j][0]), float(near[j][1]))
                    found.append((float(gaps[j]), p, -1, e, s + float(t[j]), point))
                    break
    used: set[int] = set()
    cuts: dict[int, list[tuple[float, int]]] = defaultdict(list)  # edge -> (where, new node)
    joins: list[_Local] = []
    for _gap, p, q, e, where, point in sorted(found):
        if p in used or (q >= 0 and q in used):
            continue
        target = q if q >= 0 else local[e].a
        if root(p) == root(target):
            continue
        if q < 0:
            first, last = local[e].a, local[e].b
            if where <= 0.0:
                q = first
            elif where >= len(local[e].points) - 1:
                q = last
            else:
                q = max(at) + 1
                at[q] = point
                parent[q] = q
                cuts[e].append((where, q))
        used |= {p, q} if degree[q] == 1 else {p}
        degree[p] += 1
        degree[q] += 1
        parent[root(p)] = root(q)
        joins.append(_Local(p, q, [at[p], at[q]], "join"))
    out: list[_Local] = []
    for e, edge in enumerate(local):
        if e not in cuts:
            out.append(edge)
            continue
        prev_node, prev_at = edge.a, 0.0
        for where, node in [*sorted(cuts[e]), (float(len(edge.points) - 1), edge.b)]:
            degree[node] += 2 if node != edge.b else 0
            piece = _cut(edge.points, prev_at, where)
            out.append(_Local(prev_node, node, piece, "ink"))
            prev_node, prev_at = node, where
    return out + joins


def _cut(points: list[tuple[float, float]], start: float, stop: float) -> list[tuple[float, float]]:
    """The polyline between two places along it (segment index + share along that segment)."""

    def place(where: float) -> tuple[float, float]:
        s = min(int(where), len(points) - 2)
        t = where - s
        (ax, ay), (bx, by) = points[s], points[s + 1]
        return (ax + (bx - ax) * t, ay + (by - ay) * t)

    inner = [points[i] for i in range(math.floor(start) + 1, math.ceil(stop))]
    return [place(start), *inner, place(stop)]


Chain = list[tuple[int, int]]  # (x, y) pixels between two nodes, in order


def _trace(
    skeleton: np.ndarray,
) -> tuple[dict[int, tuple[float, float]], list[tuple[int, int, Chain]]]:
    """The skeleton's nodes (key -> (x, y)): every end pixel and every cluster of junction pixels;
    and its edges (node, node, the chain of pixels between them)."""
    s = skeleton.astype(np.uint8)
    kernel = np.ones((3, 3), np.float32)
    kernel[1, 1] = 0
    neighbours = cv2.filter2D(s, cv2.CV_16S, kernel, borderType=cv2.BORDER_CONSTANT) * s
    is_node = (neighbours == 1) | (neighbours >= 3) | ((neighbours == 0) & (s == 1))
    count, clusters = cv2.connectedComponents(is_node.astype(np.uint8), connectivity=8)
    nodes: dict[int, tuple[float, float]] = {}
    node_of: dict[tuple[int, int], int] = {}
    ys, xs = np.nonzero(is_node)
    members: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for y, x in zip(ys.tolist(), xs.tolist(), strict=True):
        members[int(clusters[y, x])].append((x, y))
    for k, pts in members.items():
        nodes[k] = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        for p in pts:
            node_of[p] = k
    h, w = s.shape

    def around(x: int, y: int) -> list[tuple[int, int]]:
        return [
            (x + dx, y + dy)
            for dy, dx in _STEPS
            if 0 <= x + dx < w and 0 <= y + dy < h and s[y + dy, x + dx]
        ]

    edges: list[tuple[int, int, Chain]] = []
    seen: set[tuple[int, int]] = set()
    linked: set[tuple[int, int]] = set()
    for (x, y), k in node_of.items():
        for start in around(x, y):
            if start in node_of:
                j = node_of[start]
                if j != k and (min(j, k), max(j, k)) not in linked:
                    linked.add((min(j, k), max(j, k)))
                    edges.append((k, j, []))
                continue
            if start in seen:
                continue
            chain, end = [start], None
            seen.add(start)
            prev, here = (x, y), start
            while end is None:
                step = [p for p in around(*here) if p != prev and p not in seen]
                nxt = next((p for p in step if p in node_of and node_of[p] != k), None)
                nxt = nxt or next((p for p in step if p not in node_of), None)
                nxt = nxt or next((p for p in step if p in node_of), None)
                if nxt is None:  # back on its own node (a loop) or a dead pixel
                    back = [p for p in around(*here) if p in node_of]
                    end = node_of[back[0]] if back else k
                elif nxt in node_of:
                    end = node_of[nxt]
                else:
                    seen.add(nxt)
                    chain.append(nxt)
                    prev, here = here, nxt
            edges.append((k, end, chain))
    rest = (s == 1) & ~is_node  # loops with no node on them
    for y, x in zip(*np.nonzero(rest), strict=True):
        p = (int(x), int(y))
        if p in seen:
            continue
        k = count + len(nodes)
        nodes[k] = (float(p[0]), float(p[1]))
        chain, here, prev = [], p, None
        seen.add(p)
        while True:
            step = [q for q in around(*here) if q != prev and q not in seen]
            if not step:
                break
            prev, here = here, step[0]
            seen.add(here)
            chain.append(here)
        edges.append((k, k, chain))
    return nodes, edges


def _pruned(
    nodes: dict[int, tuple[float, float]], edges: list[tuple[int, int, Chain]], spur_px: float
) -> tuple[dict[int, tuple[float, float]], list[tuple[int, int, Chain]]]:
    """Without the thinning's spurs: an edge from an end to a junction no longer than `spur_px`."""
    degree: dict[int, int] = defaultdict(int)
    for a, b, _ in edges:
        degree[a] += 1
        degree[b] += 1
    kept = [
        (a, b, chain)
        for a, b, chain in edges
        if not (
            a != b
            and min(degree[a], degree[b]) == 1
            and max(degree[a], degree[b]) >= 3
            and len(chain) + 1 <= spur_px
        )
    ]
    used = {k for a, b, _ in kept for k in (a, b)}
    return {k: v for k, v in nodes.items() if k in used}, kept


def _bridges(
    ends: set[int],
    at: dict[int, tuple[float, float]],
    edges: list[tuple[int, int, Chain]],
    x0: int,
    y0: int,
    bridge_px: int,
) -> list[tuple[int, int]]:
    """Pairs of ends to join: no more than `bridge_px` apart, each pointing at the other within
    BRIDGE_ANGLE; nearest pairs first, each end once."""
    heading: dict[int, tuple[float, float]] = {}
    for a, b, chain in edges:
        for end, inner in ((a, chain), (b, chain[::-1])):
            if end not in ends:
                continue
            other = at[b if end == a else a]
            back = inner[min(len(inner), BACK_PX) - 1] if inner else None
            bx, by = (float(back[0] + x0), float(back[1] + y0)) if back else other
            heading[end] = (at[end][0] - bx, at[end][1] - by)
    order = sorted(ends)
    pairs: list[tuple[float, int, int]] = []
    cos_max = math.cos(math.radians(BRIDGE_ANGLE))
    for i, p in enumerate(order):
        for q in order[i + 1 :]:
            gap = (at[q][0] - at[p][0], at[q][1] - at[p][1])
            length = math.hypot(*gap)
            if length == 0 or length > bridge_px:
                continue
            if (
                _cos(heading.get(p), gap) >= cos_max
                and _cos(heading.get(q), (-gap[0], -gap[1])) >= cos_max
            ):
                pairs.append((length, p, q))
    used: set[int] = set()
    found: list[tuple[int, int]] = []
    for _, p, q in sorted(pairs):
        if p not in used and q not in used:
            used |= {p, q}
            found.append((p, q))
    return found


def _cos(u: tuple[float, float] | None, v: tuple[float, float]) -> float:
    if u is None:
        return -1.0
    nu, nv = math.hypot(*u), math.hypot(*v)
    return -1.0 if nu == 0 or nv == 0 else (u[0] * v[0] + u[1] * v[1]) / (nu * nv)


def _simplified(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    curve = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
    kept = cv2.approxPolyDP(curve, EPSILON_PX, False).reshape(-1, 2)
    return [(float(x), float(y)) for x, y in kept]


def _components(graph: LineGraph) -> list[tuple[str, list[LineEdge]]]:
    """Each style's connected runs: (style, its edges)."""
    parent = {node.id: node.id for node in graph.nodes}

    def root(n: str) -> str:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for edge in graph.edges:
        parent[root(edge.a)] = root(edge.b)
    runs: dict[str, list[LineEdge]] = defaultdict(list)
    for edge in graph.edges:
        runs[root(edge.a)].append(edge)
    return [(edges[0].style, edges) for edges in runs.values()]


def _bounds(edges: list[LineEdge]) -> tuple[float, float, float, float]:
    xs = [x for e in edges for x, _ in e.points]
    ys = [y for e in edges for _, y in e.points]
    return min(xs), min(ys), max(xs), max(ys)
