"""What connects to what on a services picture: the line graph a picture's runs are read into
(adapters/discipline_pictures/runs_graph.py builds it), contract .agents/exp/pics-graph-contract.md.

Pixels are the picture's: x right, y down. A system is the edges of one style (a legend line
label) connected through nodes."""

from app.core.model import Frozen

Px = tuple[float, float]


class LineNode(Frozen):
    id: str  # "n1", ... unique in the graph
    at: Px
    degree: int  # 1: an end; 3 or more: a junction; 2 where a style changes or a gap was bridged


class LineEdge(Frozen):
    id: str  # "e1", ...
    a: str  # LineNode ids
    b: str
    style: str  # the legend line label it was read as (LegendEntry.label)
    points: tuple[Px, ...]  # the polyline a..b, its ends included
    length_m: float | None  # at the sheet scale; None without one
    bridged: bool = False  # it closes a gap (a symbol, a text), not drawn ink


class LineGraph(Frozen):
    nodes: tuple[LineNode, ...]
    edges: tuple[LineEdge, ...]
    px_per_m: float | None  # the scale the lengths were measured with
    size_px: tuple[int, int]  # width, height of the picture the px are in
