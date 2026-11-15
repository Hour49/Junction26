"""What connects to what on a services picture: the line graph a picture's runs are read into
(adapters/discipline_pictures/runs_graph.py builds it), contract .agents/exp/pics-graph-contract.md.

Pixels are the picture's: x right, y down. A system is the edges of one style (a legend line
label) connected through nodes."""

import itertools
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from app.core.ifc_facts import Discipline, Fact, Spot
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


class Terminal(Frozen):
    """A located terminal (radiator, air terminal, sanitary, valve) or a piece of equipment
    (boiler, manifold, AHU, riser): a picture's Sighting at its centre in px."""

    id: str
    label: str
    at: Px
    equipment: bool = False  # where a system starts, when it is seen


class Attached(Frozen):
    terminal: str
    equipment: bool
    edge: str | None  # the nearest edge within the bound; None: refused
    system: str | None  # the System it is on
    distance_px: float | None
    why: str | None = None  # refused: why


class System(Frozen):
    id: str  # "s1", ... in the order of the graph's edges
    style: str
    edges: tuple[str, ...]
    length_m: float | None  # the edges' sum; None when one has no length
    terminals: tuple[str, ...] = ()  # attached terminals, not equipment
    sources: tuple[str, ...] = ()  # attached equipment: where the system starts, when seen


def _components(graph: LineGraph) -> list[list[LineEdge]]:
    """One style's edges joined through shared nodes, in the order of their first edge. Two
    styles meeting at a node stay apart: a system is one line style."""
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def root(key: tuple[str, str]) -> tuple[str, str]:
        while parent.setdefault(key, key) != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for e in graph.edges:
        parent[root((e.style, e.a))] = root((e.style, e.b))
    groups: dict[tuple[str, str], list[LineEdge]] = {}
    for e in graph.edges:
        groups.setdefault(root((e.style, e.a)), []).append(e)
    return list(groups.values())


def _system_of(graph: LineGraph) -> tuple[list[System], dict[str, str]]:
    found: list[System] = []
    of_edge: dict[str, str] = {}
    for n, edges in enumerate(_components(graph), start=1):
        lengths = [e.length_m for e in edges]
        known = [m for m in lengths if m is not None]
        length = round(sum(known), 3) if len(known) == len(lengths) else None
        made = System(id=f"s{n}", style=edges[0].style, edges=tuple(e.id for e in edges),
                      length_m=length)  # fmt: skip
        found.append(made)
        of_edge.update((e.id, made.id) for e in edges)
    return found, of_edge


def systems(graph: LineGraph, attached: Sequence[Attached] = ()) -> tuple[System, ...]:
    """The graph's systems, each with the terminals and equipment `attach` put on it."""
    found, _ = _system_of(graph)
    terminals: dict[str, list[str]] = defaultdict(list)
    sources: dict[str, list[str]] = defaultdict(list)
    for a in attached:
        if a.system is not None:
            (sources if a.equipment else terminals)[a.system].append(a.terminal)
    return tuple(
        s.model_copy(update={"terminals": tuple(terminals[s.id]), "sources": tuple(sources[s.id])})
        for s in found
    )


def _to_segment(p: Px, a: Px, b: Px) -> float:
    """The distance from `p` to the segment a..b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    span = dx * dx + dy * dy
    t = 0.0 if span == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / span))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _to_edge(p: Px, edge: LineEdge) -> float:
    points = edge.points
    if len(points) == 1:
        return math.dist(p, points[0])
    return min(_to_segment(p, a, b) for a, b in itertools.pairwise(points))


def attach(graph: LineGraph, terminals: Sequence[Terminal], max_px: float) -> tuple[Attached, ...]:
    """Each terminal on the nearest edge (a bridged one too) within `max_px` of its centre, and
    the system of that edge; beyond the bound it is refused, never put on a far line."""
    _, of_edge = _system_of(graph)
    out: list[Attached] = []
    for t in terminals:
        near = min(((_to_edge(t.at, e), e.id) for e in graph.edges), default=None)
        if near is None or near[0] > max_px:
            why = f"no line within {max_px:g} px"
            out.append(Attached(terminal=t.id, equipment=t.equipment, edge=None, system=None,
                                distance_px=None, why=why))  # fmt: skip
            continue
        out.append(Attached(terminal=t.id, equipment=t.equipment, edge=near[1],
                            system=of_edge[near[1]], distance_px=round(near[0], 4)))  # fmt: skip
    return tuple(out)


def connected(attached: Sequence[Attached], a: str, b: str) -> bool | None:
    """True when terminals `a` and `b` are on one system; else None (not known), never False: a
    line read with a gap splits one system in two, so two systems on the picture do not say
    the pipes are apart (5% of pieces lost: pair recall 0.41, precision 1.0; pics-graph.md)."""
    on = {x.terminal: x.system for x in attached}
    if on.get(a) is None or on.get(a) != on.get(b):
        return None
    return True


def names(found: Sequence[System]) -> dict[str, str]:
    """Each system's name: its style, numbered when the style has several pieces ("Supply 2")."""
    of_style = Counter(s.style for s in found)
    seen: Counter[str] = Counter()
    out: dict[str, str] = {}
    for s in found:
        seen[s.style] += 1
        out[s.id] = s.style if of_style[s.style] == 1 else f"{s.style} {seen[s.style]}"
    return out


def graph_facts(
    found: Sequence[System],
    terminals: Sequence[Terminal],
    spots: Mapping[str, Spot],
    *,
    discipline: Discipline,
    source: str,
) -> list[Fact]:
    """What connects to what as facts: per system its terminals (`system.terminal_count`) and its
    length (`system.length`, when every piece has one), per attached terminal its system
    (`terminal.system`, text). `spots`: each terminal's mark on the page, by terminal id."""
    label = {t.id: t.label for t in terminals}
    named = names(found)
    facts: list[Fact] = []
    for s in found:
        marks = tuple(spots[t] for t in s.terminals if t in spots)
        count = len(s.terminals)
        facts.append(Fact(topic="system.terminal_count", subject=named[s.id], value=count,
                          unit="count", system=named[s.id], discipline=discipline, source=source,
                          spots=marks))  # fmt: skip
        if s.length_m is not None:
            facts.append(Fact(topic="system.length", subject=named[s.id], value=s.length_m,
                              unit="m", system=named[s.id], discipline=discipline,
                              source=source))  # fmt: skip
        for t in s.terminals:
            facts.append(Fact(topic="terminal.system", subject=f"{label[t]} ({t})",
                              value=named[s.id], unit=None, system=named[s.id],
                              discipline=discipline, source=source,
                              spots=(spots[t],) if t in spots else ()))  # fmt: skip
    return facts
