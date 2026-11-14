"""Hard services questions with programmatic truth (research slice 5): multi-hop questions over an
IFC model's port graph, asked by exact id and by description, plus questions the model cannot
answer (the truth is a refusal with its reason), scored per template, anchor and phrasing.

- Graph: `services_graph_v1`, written per model by `eval/services_backend.py` in backend/'s
  environment (nodes from the backend's element reader, edges from raw IfcRelConnectsPorts).
- Truth: computed here, in plain Python, sharing no code with the backend's graph operations
  (those come later, slice 2), so agreement between the two means something.
- Equipment ("a source"): an energy conversion, flow moving, flow storage or flow treatment
  device, an electric distribution element, or a Revit Mechanical / Electrical / Plumbing
  Equipment category (some exports write their units as controllers or proxies).
- An element's handle: its Revit family (the type name before ":") and its Revit id (the
  trailing ":<id>" of its IFC Name, else its STEP id). A description names the family plus the
  top floor, a storey or a system, and is used only when it fits exactly one element.
- Split by building (the model stem minus its last "_<discipline>" part), from a manifest
  {"dev": [...], "heldout": [...]}; the held-out buildings are scored at milestones only.
- Phrasings: s1, s2 are "seen" (a template parser may be tuned on them), h1, h2 "held-out".

What each template means (`MEANINGS`), and the reasons a question is unanswerable (`REASONS`),
are written below; tests/test_services.py traces each on a small graph by hand.
"""

import heapq
import random
import re
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Truth = int | float | str | list[int] | None
Anchor = Literal["id", "descriptive", "none"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class GraphNode(_Model):
    guid: str
    step: int
    name: str | None
    type_name: str
    kind: str
    group: str
    category: str | None
    storey: str | None
    length_m: float | None
    size: str | None
    ports: int
    connected: int
    panel: str | None
    circuit: str | None
    systems: tuple[str, ...]


class GraphStorey(_Model):
    name: str
    elevation: float | None


class ServicesGraph(_Model):
    schema_: Literal["services_graph_v1"] = Field(alias="schema")
    model: str
    storeys: tuple[GraphStorey, ...]
    nodes: tuple[GraphNode, ...]
    edges: tuple[tuple[str, str], ...]
    system_types: dict[str, str | None]


class ServicesQuestion(_Model):
    id: str
    model: str
    building: str
    split: str
    template: str
    op: str
    args: dict[str, Any]
    anchor: Anchor
    hops: int
    phrasing_set: str
    text: str
    answerable: bool
    truth: Truth
    reason: str | None = None


class ServicesAnswer(_Model):
    model_config = ConfigDict(frozen=True, extra="ignore")
    id: str
    value: Truth = None
    refused: bool = False
    reason: str | None = None


SRC_GROUPS = (
    "energy_conversion_device", "flow_moving_device", "flow_storage_device",
    "flow_treatment_device",
)  # fmt: skip
SRC_CATS = ("Mechanical Equipment", "Electrical Equipment", "Plumbing Equipment")
ELECTRIC_KINDS = ("light_fixture", "outlet", "switching_device", "electric_appliance", "lamp")
SETS = ("s1", "s2", "h1", "h2")
SEEN = ("s1", "s2")

MEANINGS = {
    "terminals_served": "flow terminals reached from the equipment without passing through other "
    "equipment",
    "farthest_terminal": "of those terminals, the one farthest along the run (each hop weighs half "
    "of each end's segment length); a tie goes to the lowest Revit id",
    "feeds": "the equipment fewest port hops away from the element; asked only when one is nearest",
    "trace": "elements reached from the equipment without passing through other equipment (the "
    "equipment it stops at included, itself not)",
    "run_length_source": "the summed segment length of those elements, in metres",
    "run_length_system": "the summed segment length of the system's members, in metres",
    "system_storeys": "the storeys the system's members are on",
    "systems_crossing_storeys": "systems whose type, or one of its comma-separated types (Revit "
    "writes 'Domestic Cold Water,Sanitary'), is exactly that type, with members on two or more "
    "storeys",
    "dead_ends": "segments and fittings of the system with fewer connected ports than ports",
    "unconnected": "elements of that kind on exactly that storey with ports, none connected",
    "controllers_between": "the valves and dampers on the shortest port path between the two "
    "elements; asked only when that path is unique",
    "cut_off": "elements connected to the valve that lose every path to the named element when the "
    "valve is removed",
    "circuit_of": "the Revit panel and circuit number the element's properties state, as "
    "panel/circuit",
}
REASONS = {
    "no_connectivity": "the model states no port connections at all",
    "unconnected": "the element has no connected port",
    "no_source": "the element's network holds no equipment",
    "no_circuit_data": "no element of the model states a panel or circuit",
}

KIND_WORDS = {
    "air_terminal": "air terminals", "pipe_segment": "pipes", "duct_segment": "ducts",
    "pipe_fitting": "pipe fittings", "duct_fitting": "duct fittings", "valve": "valves",
    "damper": "dampers", "light_fixture": "light fixtures",
    "cable_carrier_segment": "cable tray segments", "flow_segment": "segments",
    "flow_fitting": "fittings", "flow_terminal": "terminals",
    "flow_controller": "valves and dampers", "waste_terminal": "waste terminals",
    "sanitary_terminal": "sanitary fixtures",
}  # fmt: skip

TEMPLATES: dict[str, tuple[int, tuple[str, str, str, str]]] = {
    "terminals_served": (2, (
        "How many terminals does the {eq} serve?",
        "Count the terminals connected downstream of the {eq}.",
        "What is the number of outlets fed by the {eq}?",
        "If I follow the network from the {eq}, how many end devices do I reach before any other "
        "equipment?")),
    "farthest_terminal": (3, (
        "Which terminal served by the {eq} has the longest run from it?",
        "Find the farthest terminal (by run length) from the {eq}.",
        "Of all outlets fed by the {eq}, which one sits at the end of the longest duct or pipe "
        "run?",
        "What's the most remote end device, measured along the run, on the {eq}'s network?")),
    "feeds": (2, (
        "Which piece of equipment feeds the {el}?",
        "What is the nearest upstream equipment of the {el}?",
        "Trace the {el} back: which unit supplies it?",
        "Where does the {el} get its supply from, i.e. which equipment is it hooked up to?")),
    "trace": (2, (
        "How many elements are connected downstream of the {eq}?",
        "Trace the network from the {eq}: how many components does it reach?",
        "How big is the branch hanging off the {eq}, in number of parts?",
        "Starting at the {eq}, how many pipes, fittings and accessories can you walk to before "
        "hitting other equipment?")),
    "run_length_source": (3, (
        "What is the total pipe/duct length reachable from the {eq}?",
        "How many metres of run are connected to the {eq}?",
        "Add up the length of every segment on the branch of the {eq}: how many metres?",
        "How much pipe in metres hangs off the {eq} before the next piece of equipment?")),
    "run_length_system": (2, (
        "What is the total segment length of system {sys}?",
        "How many metres of pipe or duct does system {sys} have?",
        "Give me the run length in metres for the {sys} system.",
        "Summing all segments assigned to {sys}, what length do we get?")),
    "system_storeys": (2, (
        "On how many storeys does system {sys} have elements?",
        "How many floors does system {sys} span?",
        "Across how many levels is the {sys} system spread?",
        "Count the distinct floors that parts of {sys} sit on.")),
    "systems_crossing_storeys": (2, (
        "How many {stype} systems span more than one storey?",
        "Count the {stype} systems that cross floors.",
        "How many systems of type {stype} run over two or more levels?",
        "Of the {stype} systems, how many are not confined to a single floor?")),
    "dead_ends": (2, (
        "How many segments or fittings in system {sys} have an open, unconnected end?",
        "Count the open ends (unconnected pipe/duct pieces) in system {sys}.",
        "For model QA: how many pieces of {sys} have a port left dangling?",
        "Where {sys} isn't closed off properly: how many segments or fittings have a free "
        "connection?")),
    "unconnected": (2, (
        "How many {kindw} on {storey} are not connected to anything?",
        "Count the unconnected {kindw} on {storey}.",
        "On {storey}, how many {kindw} have none of their connectors hooked up?",
        "QA check for {storey}: number of {kindw} floating free of the network?")),
    "controllers_between": (3, (
        "Which valves or dampers are on the run between the {a} and the {b}?",
        "List the control devices on the path from the {a} to the {b}.",
        "Walking the network from the {a} to the {b}, which valves or dampers do I pass?",
        "What valves/dampers sit in line between the {a} and the {b}?")),
    "cut_off": (3, (
        "If the {valve} is closed, how many elements are cut off from the {src}?",
        "How many components lose their connection to the {src} when the {valve} is shut?",
        "Closing the {valve}: how many parts on the far side from the {src} get isolated?",
        "Seen from the {src}, how many elements does shutting the {valve} isolate?")),
    "circuit_of": (2, (
        "Which panel and circuit serve the {dev}?",
        "What panel/circuit number feeds the {dev}?",
        "The {dev} is on which board and which circuit?",
        "Tell me the distribution panel and circuit for the {dev}.")),
}  # fmt: skip


def _family(type_name: str) -> str:
    return type_name.split(":")[0].strip()


class Net:
    """The truth over one model's graph (undirected port connections)."""

    def __init__(self, graph: ServicesGraph) -> None:
        self.graph = graph
        self.nodes = {n.guid: n for n in graph.nodes}
        self.adj: dict[str, set[str]] = defaultdict(set)
        for a, b in graph.edges:
            if a in self.nodes and b in self.nodes and a != b:
                self.adj[a].add(b)
                self.adj[b].add(a)
        self.members: dict[str, list[str]] = defaultdict(list)
        for n in graph.nodes:
            for system in dict.fromkeys(n.systems):
                self.members[system].append(n.guid)
        held = {n.storey for n in graph.nodes if n.storey}
        levels = [s for s in graph.storeys if s.name in held and s.elevation is not None]
        self.top = max(levels, key=lambda s: s.elevation or 0.0).name if levels else None

    def rid(self, guid: str) -> int:
        n = self.nodes[guid]
        found = re.search(r":(\d+)$", n.name or "")
        return int(found.group(1)) if found else n.step

    def src(self, guid: str) -> bool:
        n = self.nodes[guid]
        return (
            n.group in SRC_GROUPS
            or n.kind.startswith("electric_distribution")
            or n.category in SRC_CATS
        )

    def reach(self, s: str, avoid: str | None = None, stop_at_src: bool = True) -> set[str]:
        """s and every element reached from it, never entering `avoid`; with stop_at_src, other
        equipment is reached but not walked through."""
        seen, todo = {s}, deque([s])
        while todo:
            v = todo.popleft()
            if stop_at_src and v != s and self.src(v):
                continue
            for w in self.adj[v]:
                if w not in seen and w != avoid:
                    seen.add(w)
                    todo.append(w)
        return seen

    def hops(self, s: str, cutoff: int | None = None) -> dict[str, int]:
        dist, todo = {s: 0}, deque([s])
        while todo:
            v = todo.popleft()
            if cutoff is not None and dist[v] >= cutoff:
                continue
            for w in self.adj[v]:
                if w not in dist:
                    dist[w] = dist[v] + 1
                    todo.append(w)
        return dist

    def trace(self, s: str) -> int:
        return len(self.reach(s)) - 1

    def terminals_served(self, s: str) -> int:
        return sum(self.nodes[g].group == "flow_terminal" for g in self.reach(s) - {s})

    def feeds(self, s: str) -> tuple[int | None, int]:
        """(Revit id of the nearest equipment, how many equipment tie at that distance)."""
        found = sorted((h, g) for g, h in self.hops(s).items() if g != s and self.src(g))
        if not found:
            return None, 0
        tied = [g for h, g in found if h == found[0][0]]
        return self.rid(tied[0]), len(tied)

    def run_length(self, s: str | None = None, system: str | None = None) -> float:
        guids = self.reach(s) if s is not None else self.members.get(system or "", [])
        return round(sum(self.nodes[g].length_m or 0.0 for g in guids), 3)

    def controllers_between(self, a: str, b: str) -> tuple[list[int] | None, int, bool]:
        """(sorted controller Revit ids, hops, the shortest path is unique)."""
        da, db = self.hops(a), self.hops(b)
        if b not in da:
            return None, 0, False
        d = da[b]
        on = [g for g in da if g in db and da[g] + db[g] == d]
        unique = all(sum(1 for g in on if da[g] == k) == 1 for k in range(d + 1))
        ctl = sorted(
            self.rid(g) for g in on if g not in (a, b) and self.nodes[g].group == "flow_controller"
        )
        return ctl, d, unique

    def system_storeys(self, system: str) -> int:
        return len({self.nodes[g].storey for g in self.members.get(system, ())} - {None, ""})

    def systems_crossing_storeys(self, system_type: str) -> int:
        want = system_type.casefold()
        return sum(
            1
            for system, kind in self.graph.system_types.items()
            if want in {part.strip().casefold() for part in (kind or "").split(",")}
            and self.system_storeys(system) >= 2
        )

    def circuit_of(self, guid: str) -> str | None:
        n = self.nodes[guid]
        return None if n.panel is None and n.circuit is None else f"{n.panel}/{n.circuit}"

    def unconnected(self, kind: str, storey: str) -> int:
        return sum(
            1
            for n in self.graph.nodes
            if n.ports and not n.connected and kind in (n.kind, n.group) and n.storey == storey
        )

    def dead_ends(self, system: str) -> int:
        return sum(
            1
            for g in self.members.get(system, ())
            if self.nodes[g].group in ("flow_segment", "flow_fitting")
            and self.nodes[g].ports > self.nodes[g].connected
        )

    def farthest_terminal(self, s: str) -> int | None:
        r = self.reach(s)
        w = {g: self.nodes[g].length_m or 0.0 for g in r}
        dist, heap = {s: 0.0}, [(0.0, s)]
        while heap:
            d, v = heapq.heappop(heap)
            if d > dist[v]:
                continue
            for x in self.adj[v]:
                nd = d + (w[v] + w.get(x, 0.0)) / 2
                if x in r and nd < dist.get(x, float("inf")) - 1e-12:
                    dist[x] = nd
                    heapq.heappush(heap, (nd, x))
        terms = [
            (dist[g], -self.rid(g))
            for g in dist
            if g != s and self.nodes[g].group == "flow_terminal"
        ]
        return -max(terms)[1] if terms else None

    def cut_off(self, valve: str, source: str) -> int:
        keep = self.reach(source, avoid=valve, stop_at_src=False)
        return len(self.reach(valve, stop_at_src=False) - {valve} - keep)

    def handle(self, guid: str) -> str:
        return f"{_family(self.nodes[guid].type_name)} (Revit id {self.rid(guid)})"

    def resolve(self, desc: Mapping[str, Any]) -> list[str]:
        """Every element a description fits."""
        return [
            n.guid
            for n in self.graph.nodes
            if _family(n.type_name) == desc["family"]
            and (not desc.get("top") or (n.storey is not None and n.storey == self.top))
            and ("storey" not in desc or n.storey == desc["storey"])
            and ("system" not in desc or desc["system"] in n.systems)
        ]

    def describe(self, guid: str) -> tuple[str, dict[str, Any]] | None:
        """(text, description) of the first description that fits only this element."""
        n = self.nodes[guid]
        family = _family(n.type_name)
        tries: list[tuple[str, dict[str, Any]]] = []
        if n.storey and n.storey == self.top:
            tries.append((f"{family} on the top floor", {"family": family, "top": True}))
        if n.storey:
            tries.append((f"{family} on {n.storey}", {"family": family, "storey": n.storey}))
        tries += [(f"{family} in system {s}", {"family": family, "system": s}) for s in n.systems]
        return next(((t, d) for t, d in tries if self.resolve(d) == [guid]), None)


def building_of(model: str) -> str:
    """The model stem minus its discipline: tower_ventilation -> tower."""
    return model.rsplit("_", 1)[0] if "_" in model else model


def split_of(model: str, manifest: Mapping[str, Sequence[str]]) -> str:
    building = building_of(model)
    found = [split for split, buildings in manifest.items() if building in buildings]
    if len(found) != 1:
        raise ValueError(f"{model}: building {building!r} is in {len(found)} manifest splits")
    return found[0]


# (template, op, args, anchors: slot -> guid, text slots, truth, reason)
_Item = tuple[str, str, dict[str, Any], dict[str, str], dict[str, str], Truth, str | None]


def _sample[T](rng: random.Random, xs: Iterable[T], k: int) -> list[T]:
    pool = sorted(xs, key=str)
    return rng.sample(pool, min(k, len(pool)))


def _answerable(net: Net, rng: random.Random) -> list[_Item]:
    out: list[_Item] = []
    nodes = net.nodes
    srcs = [g for g in nodes if net.src(g)]
    serving = [g for g in srcs if net.terminals_served(g) > 0]
    for v in _sample(rng, serving, 10):
        rid = net.rid(v)
        out.append(("terminals_served", "terminals_served", {"equipment": rid}, {"eq": v}, {},
                    net.terminals_served(v), None))  # fmt: skip
        out.append(("farthest_terminal", "farthest_terminal", {"source": rid}, {"eq": v}, {},
                    net.farthest_terminal(v), None))  # fmt: skip
    terms = {t for v in serving for t in net.reach(v) if nodes[t].group == "flow_terminal"}
    for t in _sample(rng, terms, 10):
        rid, tied = net.feeds(t)
        if tied == 1:
            out.append(("feeds", "feeds", {"element": net.rid(t)}, {"el": t}, {}, rid, None))
    big = [v for v in srcs if v not in serving and net.trace(v) >= 3]
    for v in _sample(rng, big, 6) + _sample(rng, serving, 3):
        rid = net.rid(v)
        out.append(("trace", "trace", {"source": rid}, {"eq": v}, {}, net.trace(v), None))
        if (m := net.run_length(v)) > 0:
            out.append(("run_length_source", "run_length", {"source": rid}, {"eq": v}, {}, m,
                        None))  # fmt: skip
    systems = sorted(net.members)
    for s in _sample(rng, [s for s in systems if net.run_length(system=s) > 0], 6):
        out.append(("run_length_system", "run_length", {"system": s}, {}, {"sys": s},
                    net.run_length(system=s), None))  # fmt: skip
    for s in _sample(rng, [s for s in systems if net.system_storeys(s) >= 2], 6):
        out.append(("system_storeys", "system_storeys", {"system": s}, {}, {"sys": s},
                    net.system_storeys(s), None))  # fmt: skip
    types = Counter(t for s, t in net.graph.system_types.items() if t and "," not in t
                    and s in net.members)  # fmt: skip
    for st, _ in types.most_common(4):
        out.append(("systems_crossing_storeys", "systems_crossing_storeys", {"system_type": st},
                    {}, {"stype": st}, net.systems_crossing_storeys(st), None))  # fmt: skip
    for s in _sample(rng, [s for s in systems if net.dead_ends(s) > 0], 5):
        out.append(("dead_ends", "dead_ends", {"system": s}, {}, {"sys": s}, net.dead_ends(s),
                    None))  # fmt: skip
    loose = {(n.kind, n.storey) for n in net.graph.nodes
             if n.ports and not n.connected and n.kind in KIND_WORDS and n.storey}  # fmt: skip
    for kind, storey in _sample(rng, loose, 6):
        out.append(("unconnected", "unconnected", {"kind": kind, "storey": storey}, {},
                    {"kindw": KIND_WORDS[kind], "storey": storey},
                    net.unconnected(kind, storey), None))  # fmt: skip
    ends = {g for g in nodes if nodes[g].group in ("flow_terminal", "flow_controller")
            and net.adj[g]}  # fmt: skip
    pairs = 0
    for a in _sample(rng, ends, 400):
        if pairs >= 6:
            break
        near = [b for b in net.hops(a, cutoff=40) if b != a and b in ends]
        for b in _sample(rng, near, 3):
            ctl, d, unique = net.controllers_between(a, b)
            if unique and ctl and d >= 4:
                out.append(
                    (
                        "controllers_between",
                        "controllers_between",
                        {"a": net.rid(a), "b": net.rid(b)},
                        {"a": a, "b": b},
                        {},
                        ctl,
                        None,
                    )
                )
                pairs += 1
                break  # fmt: skip
    valves = [g for g in nodes if nodes[g].group == "flow_controller" and len(net.adj[g]) >= 2
              and not net.src(g)]  # fmt: skip
    cuts = 0
    for v in _sample(rng, valves, 200):
        if cuts >= 6:
            break
        # the source side is the nearest meter (some exports never connect their equipment)
        meters = sorted((h, x) for x, h in net.hops(v).items()
                        if x != v and "meter" in nodes[x].type_name.lower())  # fmt: skip
        if meters and (len(meters) == 1 or meters[0][0] < meters[1][0]):
            src = meters[0][1]
            if c := net.cut_off(v, src):
                out.append(("cut_off", "cut_off", {"valve": net.rid(v), "source": net.rid(src)},
                            {"valve": v, "src": src}, {}, c, None))  # fmt: skip
                cuts += 1
    devs = [g for g in nodes if net.circuit_of(g)]
    for v in _sample(rng, devs, 10):
        out.append(("circuit_of", "circuit_of", {"device": net.rid(v)}, {"dev": v}, {},
                    net.circuit_of(v), None))  # fmt: skip
    return out


def _unanswerable(net: Net, rng: random.Random) -> list[_Item]:
    """Questions the model cannot answer; the truth is a refusal with the reason."""
    out: list[_Item] = []
    nodes = net.nodes
    srcs = [g for g in nodes if net.src(g)]
    terms = [g for g in nodes if nodes[g].group == "flow_terminal"]
    if not any(net.adj.values()):
        for v in _sample(rng, srcs, 5):
            out.append(("terminals_served", "terminals_served", {"equipment": net.rid(v)},
                        {"eq": v}, {}, None, "no_connectivity"))  # fmt: skip
        for t in _sample(rng, terms, 5):
            out.append(("feeds", "feeds", {"element": net.rid(t)}, {"el": t}, {}, None,
                        "no_connectivity"))  # fmt: skip
    else:
        for v in _sample(rng, [g for g in srcs if not nodes[g].connected], 5):
            out.append(("terminals_served", "terminals_served", {"equipment": net.rid(v)},
                        {"eq": v}, {}, None, "unconnected"))  # fmt: skip
        alone = [t for t in terms if nodes[t].connected and net.feeds(t)[0] is None]
        for t in _sample(rng, alone, 5):
            out.append(("feeds", "feeds", {"element": net.rid(t)}, {"el": t}, {}, None,
                        "no_source"))  # fmt: skip
    if not any(net.circuit_of(g) for g in nodes):
        devs = [g for g in nodes if nodes[g].kind in ELECTRIC_KINDS]
        for v in _sample(rng, devs, 5):
            out.append(("circuit_of", "circuit_of", {"device": net.rid(v)}, {"dev": v}, {},
                        None, "no_circuit_data"))  # fmt: skip
    return out


def generate(graph: ServicesGraph, split: str, seed: int = 14) -> list[ServicesQuestion]:
    """Every question of one model, each in the four phrasings; an anchored question once by id
    and once more by description when every anchor has one."""
    net = Net(graph)
    rng = random.Random(f"{seed}-{graph.model}")
    rows: list[ServicesQuestion] = []
    items = _answerable(net, rng) + _unanswerable(net, rng)
    for template, op, args, anchors, slots, truth, reason in items:
        hops, texts = TEMPLATES[template]
        kinds: list[tuple[Anchor, dict[str, str], dict[str, Any]]] = []
        if not anchors:
            kinds.append(("none", slots, {}))
        else:
            kinds.append(("id", {k: net.handle(g) for k, g in anchors.items()}, {}))
            described = {k: net.describe(g) for k, g in anchors.items()}
            if all(described.values()):
                texts_ = {k: d[0] for k, d in described.items() if d}
                kinds.append(("descriptive", texts_, {k: d[1] for k, d in described.items() if d}))
        for anchor, filled, desc in kinds:
            base = f"{graph.model}-{len(rows) // 4:04d}"
            for phrasing, text in zip(SETS, texts, strict=True):
                rows.append(ServicesQuestion(
                    id=f"{base}-{phrasing}", model=graph.model, building=building_of(graph.model),
                    split=split, template=template, op=op,
                    args={**args, **({"described": desc} if desc else {})}, anchor=anchor,
                    hops=hops, phrasing_set=phrasing, text=text.format(**filled),
                    answerable=reason is None, truth=truth, reason=reason,
                ))  # fmt: skip
    return rows


def _number(x: Truth) -> float | None:
    if isinstance(x, bool) or x is None or isinstance(x, list):
        return None
    try:
        return float(x)
    except ValueError:
        return None


def same(answer: Truth, truth: Truth) -> bool:
    """Lengths within 2 %, counts and ids exactly, id lists as sets, text case-blind."""
    if isinstance(truth, list):
        return isinstance(answer, list) and sorted(map(str, answer)) == sorted(map(str, truth))
    if isinstance(truth, str):
        return isinstance(answer, str) and answer.strip().casefold() == truth.casefold()
    a, t = _number(answer), _number(truth)
    if a is None or t is None:
        return False
    if isinstance(truth, float):
        return abs(a - t) <= 0.02 * max(abs(t), 1e-9)
    return a == t


def _right(q: ServicesQuestion, a: ServicesAnswer | None) -> bool:
    if a is None:
        return False
    if not q.answerable:
        return a.refused
    return not a.refused and same(a.value, q.truth)


def _rate(n: int, right: int) -> dict[str, Any]:
    return {"n": n, "right": right, "rate": right / n if n else 0.0}


DIMENSIONS: dict[str, Callable[[ServicesQuestion], str]] = {
    "template": lambda q: q.template,
    "anchor": lambda q: q.anchor,
    "phrasing": lambda q: "seen" if q.phrasing_set in SEEN else "held-out",
    "hops": lambda q: str(q.hops),
    "answerable": lambda q: "answerable" if q.answerable else "unanswerable",
}


def score(
    questions: Sequence[ServicesQuestion], answers: Sequence[ServicesAnswer]
) -> dict[str, Any]:
    """Aggregates only (no model or element names): overall, per dimension, and the refusals
    (refused when it should, with the right reason, and refusals of answerable questions)."""
    by_id = {a.id: a for a in answers}
    right = {q.id: _right(q, by_id.get(q.id)) for q in questions}
    by: dict[str, dict[str, dict[str, Any]]] = {}
    for dim, key in DIMENSIONS.items():
        groups: dict[str, list[bool]] = defaultdict(list)
        for q in questions:
            groups[key(q)].append(right[q.id])
        by[dim] = {k: _rate(len(v), sum(v)) for k, v in sorted(groups.items())}
    no = [q for q in questions if not q.answerable]
    refused = [q for q in no if (a := by_id.get(q.id)) is not None and a.refused]
    return {
        "overall": _rate(len(questions), sum(right.values())),
        "refusal": {
            "unanswerable": len(no),
            "refused": len(refused),
            "reason_right": sum(by_id[q.id].reason == q.reason for q in refused),
            "false_refusals": sum(
                1
                for q in questions
                if q.answerable and (a := by_id.get(q.id)) is not None and a.refused
            ),
        },
        "by": by,
    }


def format_report(report: Mapping[str, Any]) -> str:
    o, r = report["overall"], report["refusal"]
    lines = [
        f"right {o['right']}/{o['n']} ({o['rate']:.1%})",
        f"refusals: {r['refused']}/{r['unanswerable']} refused, {r['reason_right']} with the "
        f"right reason; {r['false_refusals']} answerable questions refused",
    ]
    for dim, groups in report["by"].items():
        lines.append(f"{dim}:")
        lines += [f"  {k:26s} {g['right']}/{g['n']} ({g['rate']:.1%})" for k, g in groups.items()]
    return "\n".join(lines)
