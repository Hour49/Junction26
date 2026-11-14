"""The services graph and its operations (spec SV-10, SV-11, SV-4): an element adjacency over the
model's port connections in plain Python (dict, deque, heapq), and the closed list of questions
`ask` answers with ids. Pure: reads the model's JSON document only.

Definitions (SV-11):
- Equipment: boilers, chillers, air handling units, pumps, fans, tanks, treatment devices,
  distribution boards, and anything the file's category calls equipment. Equipment pieces that
  touch form one unit ("boiler + pump" is one source).
- A walk does not pass equipment, except pumps and fans (flow-moving devices sit inline in a
  run); it stops at any other piece it reaches.
- "What feeds X" is the set of equipment X's walk reaches, not the nearest by hops; a unit with
  a heat or air source is preferred over pumps alone, the others are listed under "also".
- "What closing a valve cuts off" follows the stated flow direction, so it needs a direction on
  at least 90% of the ports of the valve's systems; else it is unknown. It is unknown too when
  an outlet of the valve or of anything it passes downstream is open, or connected with no
  stated direction ("both", none) on one side (each with its own reason), and when nothing
  lies downstream: it never says "0" from a gap.
- A junction is any element with three or more ports.

Connectivity (SV-4): with `none`, every question that walks the network is unknown with the
model's reason. With `partial`, an operation refuses only when its own answer depends on the
loose part: one that needs equipment (feeds, terminals served, trace,
run length from an element, farthest terminal) is
unknown for an element with no connected port or on a piece reaching no equipment; cut-off needs
only the stated flow, and controllers-between only a path between its two elements.
"""

import heapq
import re
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterable, Mapping
from typing import Any

Doc = Mapping[str, Any]
Answer = dict[str, Any]

EQUIPMENT_GROUPS = frozenset(
    {
        "energy_conversion_device",
        "flow_moving_device",
        "flow_storage_device",
        "flow_treatment_device",
    }
)
EQUIPMENT_CATEGORIES = frozenset(
    {"Mechanical Equipment", "Electrical Equipment", "Plumbing Equipment"}
)
INLINE = "flow_moving_device"  # pumps and fans
HEAT_OR_AIR = re.compile(r"boiler|chiller|heat|air_handling|unitary|furnace|burner|coil")
# PredefinedTypes of a heat or air source whatever the class: an electric water heater, an AHU
HEAT_OR_AIR_TYPE = re.compile(r"WATERHEATER|AIRHANDLER|AIRCONDITIONING|BOILER|HEATER")
# A tank stores water to heat or to hand on, so it is a source; an expansion vessel is not
NOT_A_STORE = frozenset({"EXPANSION", "FEEDANDEXPANSION", "BREAKPRESSURE", "BASIN"})
NO_EQUIPMENT = "its network reaches no equipment"
NO_FLOW = "this model does not say which way the water flows here"
NO_NETWORK = "the model has no port connections"
MAX_ELEMENTS = 30  # elements listed with an answer (SV-24)


class UnknownAnswerError(Exception):
    """The model cannot answer this question; the message says why, in plain words."""


def _order(ids: Iterable[str]) -> list[str]:
    """E2 before E10."""
    return sorted(
        ids, key=lambda i: (re.sub(r"\d+", "", i), [int(n) for n in re.findall(r"\d+", i)])
    )


class ServicesGraph:
    def __init__(self, doc: Doc) -> None:
        self.doc = doc
        self.el: dict[str, Mapping[str, Any]] = {e["id"]: e for e in doc.get("elements", ())}
        self.adj: dict[str, set[str]] = defaultdict(set)
        self.linked: set[str] = set()
        self.peer: dict[str, str] = {}  # port -> the port it connects to
        self.flow = {p["id"]: p.get("flow") for e in self.el.values() for p in e.get("ports") or ()}
        self.down: dict[str, set[str]] = defaultdict(set)  # along a stated flow direction
        for c in doc.get("connections", ()):
            a, b = _host(c["a"]), _host(c["b"])
            if a == b or a not in self.el or b not in self.el:
                continue
            self.linked |= {c["a"], c["b"]}
            self.peer |= {c["a"]: c["b"], c["b"]: c["a"]}
            self.adj[a].add(b)
            self.adj[b].add(a)
            if self.flow.get(c["a"]) == "source" and self.flow.get(c["b"]) == "sink":
                self.down[a].add(b)
            elif self.flow.get(c["a"]) == "sink" and self.flow.get(c["b"]) == "source":
                self.down[b].add(a)
        self.equipment = {i for i, e in self.el.items() if _is_equipment(e)}
        self.unit: dict[str, frozenset[str]] = {}
        for i in _order(self.equipment):
            if i not in self.unit:
                piece = frozenset(self._walk({i}, lambda v: v in self.equipment, stop=None))
                self.unit |= dict.fromkeys(piece, piece)
        connectivity: Mapping[str, Any] = doc.get("connectivity") or {}
        self.state: str = connectivity.get("state", "connected")
        self.reason: str = connectivity.get("reason") or NO_NETWORK

    # --- reading ---------------------------------------------------------------------------

    def element(self, element_id: str) -> Mapping[str, Any]:
        if element_id not in self.el:
            raise UnknownAnswerError(f"no element {element_id} in this model")
        return self.el[element_id]

    def members(self, system: str) -> set[str]:
        found = {i for i, e in self.el.items() if system in (e.get("systems") or ())}
        if not found:
            raise UnknownAnswerError(f"no system '{system}' in this model")
        return found

    def junctions(self) -> list[str]:
        return _order(i for i, e in self.el.items() if len(e.get("ports") or ()) >= 3)

    def connected_ports(self, element_id: str) -> int:
        return sum(p["id"] in self.linked for p in self.el[element_id].get("ports") or ())

    # --- walking ---------------------------------------------------------------------------

    def _walk(
        self,
        starts: set[str],
        keep: Callable[[str], bool] = lambda _: True,
        stop: Callable[[str], bool] | None = None,
        edges: Mapping[str, set[str]] | None = None,
    ) -> set[str]:
        """Elements reached from `starts` over `edges` (the adjacency), through elements
        `keep` allows; one `stop` allows is reached but not passed."""
        edges = self.adj if edges is None else edges
        seen, queue = set(starts), deque(_order(starts))
        while queue:
            v = queue.popleft()
            if v not in starts and stop is not None and stop(v):
                continue
            for w in _order(edges.get(v, ())):
                if w not in seen and keep(w):
                    seen.add(w)
                    queue.append(w)
        return seen

    def stops(self, element_id: str) -> bool:
        return element_id in self.equipment and self.el[element_id]["group"] != INLINE

    def start(self, element_id: str) -> set[str]:
        """Where a walk from this element starts: its equipment unit, else itself."""
        self.network(element_id)
        return set(self.unit.get(element_id, {element_id}))

    def reach(self, starts: set[str], keep: Callable[[str], bool] = lambda _: True) -> set[str]:
        return self._walk(starts, keep, self.stops)

    def walkable(self, element_id: str) -> None:
        """Unknown when the model has no network at all (SV-4 `none`)."""
        self.element(element_id)
        if self.state == "none":
            raise UnknownAnswerError(self.reason)

    def network(self, element_id: str) -> None:
        """Unknown when the network the question walks is not in the model (SV-4)."""
        self.walkable(element_id)
        if self.state == "partial":
            piece = self._walk({element_id})
            if not self.connected_ports(element_id) or not piece & self.equipment:
                raise UnknownAnswerError(self.reason)

    def length(self, ids: Iterable[str], size: str | None = None) -> tuple[float, dict[str, float]]:
        by: Counter[str] = Counter()
        for i in ids:
            e = self.el[i]
            if e.get("length_m") is not None and (size is None or e.get("size") == size):
                by[e.get("size") or ""] += e["length_m"]
        return round(sum(by.values()), 3), {k: round(v, 3) for k, v in by.items()}


def _host(port_id: str) -> str:
    return port_id.split(".p")[0]


def _is_equipment(e: Mapping[str, Any]) -> bool:
    return (
        e.get("group") in EQUIPMENT_GROUPS
        or str(e.get("kind", "")).startswith("electric_distribution")
        or e.get("category") in EQUIPMENT_CATEGORIES
    )


def _terminal(e: Mapping[str, Any]) -> bool:
    return e.get("group") == "flow_terminal"


# --- the operations (SV-10): (graph, **ids and words) -> {"value", "elements", ...} -------------


def terminals_served(g: ServicesGraph, element_id: str, kind: str | None = None) -> Answer:
    start = g.start(element_id)
    found = [
        v for v in g.reach(start) - start if _terminal(g.el[v]) and kind in (None, g.el[v]["kind"])
    ]
    return {"value": len(found), "elements": _order(found)}


def trace(g: ServicesGraph, element_id: str, system: str | None = None) -> Answer:
    start = g.start(element_id)
    inside = g.members(system) | start if system else None
    reached = g.reach(start, (lambda v: v in inside) if inside else (lambda _: True)) - start
    return {
        "value": len(reached),
        "elements": _order(reached),
        "terminals": sum(_terminal(g.el[v]) for v in reached),
        "run_m": g.length(reached)[0],
    }


def feeds(g: ServicesGraph, element_id: str) -> Answer:
    start = g.start(element_id)
    units = {g.unit[v] for v in g.reach(start) - start if v in g.equipment} - {frozenset(start)}
    if not units:
        raise UnknownAnswerError(NO_EQUIPMENT)
    ranked = sorted(units, key=lambda u: (not _heat_or_air(g, u), _order(u)))
    best = [u for u in ranked if _heat_or_air(g, u)] or ranked  # no source: all it reaches
    value = _order(v for u in best for v in u)
    return {"value": value, "elements": value, "also": [_order(u) for u in ranked if u not in best]}


def _heat_or_air(g: ServicesGraph, unit: Iterable[str]) -> bool:
    """A heat or air source by its IFC class or PredefinedType: an energy conversion device
    (boiler, heater, coil, heat exchanger, AHU), a water heater, a storage tank or vessel."""
    return any(_source(g.el[v]) for v in unit)


def _source(e: Mapping[str, Any]) -> bool:
    predefined = str(e.get("predefined") or "")
    return (
        e.get("group") == "energy_conversion_device"
        or HEAT_OR_AIR.search(str(e.get("kind", ""))) is not None
        or HEAT_OR_AIR_TYPE.search(predefined) is not None
        or (e.get("group") == "flow_storage_device" and predefined not in NOT_A_STORE)
    )


def run_length(
    g: ServicesGraph,
    system: str | None = None,
    element_id: str | None = None,
    size: str | None = None,
) -> Answer:
    if element_id is not None:
        start = g.start(element_id)
        nodes = g.reach(start) - start
    elif system is not None:
        nodes = g.members(system)
    else:
        raise UnknownAnswerError("say a system, or an element to measure from")
    total, by_size = g.length(nodes, size)
    runs = [v for v in nodes if g.el[v].get("length_m") is not None]
    return {"value": total, "by_size": by_size, "elements": _order(runs)}


def farthest_terminal(g: ServicesGraph, element_id: str) -> Answer:
    """The terminal with the most metres of run on the way from this element."""
    start = g.start(element_id)
    inside = g.reach(start)
    dist = dict.fromkeys(start, 0.0)
    heap = [(0.0, v) for v in _order(start)]
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist[v] or (v not in start and g.stops(v)):
            continue
        for w in g.adj[v] & inside:
            nd = d + (g.el[w].get("length_m") or 0.0)
            if nd < dist.get(w, float("inf")):
                dist[w] = nd
                heapq.heappush(heap, (nd, w))
    terminals = [v for v in dist if v not in start and _terminal(g.el[v])]
    if not terminals:
        return {"value": None, "run_m": None, "elements": []}
    far = max(_order(terminals), key=lambda v: dist[v])  # the first of a tie
    return {"value": far, "run_m": round(dist[far], 3), "elements": [far]}


def controllers_between(g: ServicesGraph, element_id: str, to_element_id: str) -> Answer:
    g.walkable(element_id)  # a path answers it, loose part or not (SV-4)
    g.walkable(to_element_id)
    prev: dict[str, str | None] = {element_id: None}
    queue = deque([element_id])
    while queue and to_element_id not in prev:
        v = queue.popleft()
        for w in _order(g.adj[v]):
            if w not in prev:
                prev[w] = v
                queue.append(w)
    if to_element_id not in prev:
        raise UnknownAnswerError("no connection between them in the model")
    path: list[str] = []
    v = prev[to_element_id]
    while v is not None and v != element_id:
        path.append(v)
        v = prev[v]
    found = [v for v in reversed(path) if g.el[v]["group"] == "flow_controller"]
    return {"value": found, "elements": found, "hops": len(path) + 1}


def cut_off(g: ServicesGraph, element_id: str) -> Answer:
    g.walkable(element_id)  # the stated flow answers it, not connected equipment (SV-4)
    systems = g.el[element_id].get("systems") or ()
    around: set[str] = set()
    for system in systems:
        around |= g.members(system)
    around = around or g._walk({element_id})  # pyright: ignore[reportPrivateUsage]
    ports = [p["id"] for v in around for p in g.el[v].get("ports") or ()]
    stated = sum(g.flow.get(p) in ("source", "sink") for p in ports)
    if not ports or stated < 0.9 * len(ports):
        raise UnknownAnswerError(NO_FLOW)
    down = g._walk({element_id}, stop=g.stops, edges=g.down) - {element_id}  # pyright: ignore[reportPrivateUsage]
    # Every outlet of the valve and of what it passes must lead on along a stated flow: an
    # open end or an undirected outlet hides what lies beyond, so the count would be short.
    for v in _order({element_id} | {d for d in down if not g.stops(d)}):
        for p in g.el[v].get("ports") or ():
            flow, peer = g.flow.get(p["id"]), g.peer.get(p["id"])
            if flow == "sink" or (flow == "source" and g.flow.get(peer) == "sink"):
                continue
            if peer is None:
                raise UnknownAnswerError(
                    f"the model does not show what lies downstream of {element_id}: "
                    f"at {v} a connection is missing"
                )
            at = _host(peer) if flow == "source" else v  # the side that states no direction
            raise UnknownAnswerError(
                f"the model does not say which way the flow goes at {at}, "
                f"so it cannot tell what lies downstream of {element_id}"
            )
    if not down:  # a connected valve always has something downstream: its flow is mis-stated
        raise UnknownAnswerError(NO_FLOW)
    return {
        "value": len(down),
        "elements": _order(down),
        "terminals": sum(_terminal(g.el[v]) for v in down),
    }


def system_storeys(g: ServicesGraph, system: str) -> Answer:
    names = {s["id"]: s.get("name") or s["id"] for s in g.doc.get("storeys", ())}
    per = Counter(
        names.get(g.el[v].get("storey"), g.el[v].get("storey")) for v in g.members(system)
    )
    per.pop(None, None)
    return {"value": len(per), "per_storey": dict(per), "elements": []}


def systems_crossing_storeys(
    g: ServicesGraph, system_type: str | None = None, min_storeys: int = 2
) -> Answer:
    """A system's type is the stored system's own (`systems[].type`; a system the file names
    only in its members' properties has their most common `system_type`); it matches the asked
    type whole or one of its comma-separated parts ("Domestic Cold Water,Sanitary")."""
    storeys: dict[str, set[str]] = defaultdict(set)
    said: dict[str, Counter[str]] = defaultdict(Counter)
    for e in g.el.values():
        for s in e.get("systems") or ():
            if e.get("storey"):
                storeys[s].add(e["storey"])
            said[s][e.get("system_type") or ""] += 1
    stored: dict[str, set[str]] = defaultdict(set)
    for system in g.doc.get("systems") or ():
        stored[system["name"]].add(system["type"])

    def typed(name: str) -> bool:
        if system_type is None:
            return True
        types = stored.get(name) or {said[name].most_common(1)[0][0]}
        asked = system_type.strip().lower()
        return any(
            asked in (t.lower(), *(part.strip().lower() for part in t.split(","))) for t in types
        )

    found = sorted(s for s, at in storeys.items() if len(at) >= min_storeys and typed(s))
    return {"value": len(found), "systems": found, "elements": []}


def open_ends(g: ServicesGraph, system: str | None = None) -> Answer:
    nodes = g.members(system) if system else set(g.el)
    found = [
        v
        for v in nodes
        if g.el[v]["group"] in ("flow_segment", "flow_fitting")
        and g.connected_ports(v) < len(g.el[v].get("ports") or ())
    ]
    return {"value": len(found), "elements": _order(found)}


def unconnected(g: ServicesGraph, kind: str | None = None, storey: str | None = None) -> Answer:
    names = {s["id"]: s.get("name") or "" for s in g.doc.get("storeys", ())}

    def on(e: Mapping[str, Any]) -> bool:
        at = e.get("storey") or ""
        return storey is None or storey == at or storey.lower() in names.get(at, "").lower()

    found = [
        i
        for i, e in g.el.items()
        if e.get("ports")
        and not g.connected_ports(i)
        and kind in (None, e["kind"], e["group"])
        and on(e)
    ]
    return {
        "value": len(found),
        "elements": _order(found),
        "by_kind": dict(Counter(g.el[i]["kind"] for i in found)),
    }


def circuit_of(g: ServicesGraph, element_id: str) -> Answer:
    """The stored "<panel>/<circuit>" (or "<panel>" alone) of a device."""
    stated = str(g.element(element_id).get("circuit") or "").strip()
    if not stated:
        raise UnknownAnswerError(f"the model states no panel or circuit for {element_id}")
    panel, _, number = stated.partition("/")
    return {"value": stated, "panel": panel, "circuit": number or None, "elements": [element_id]}


def system_info(g: ServicesGraph, system: str) -> Answer:
    members = g.members(system)
    first = _order(members)[0]
    return {
        "value": len(members),
        "by_kind": dict(Counter(g.el[v]["kind"] for v in members)),
        "equipment": _order(members & g.equipment),
        "connected": g._walk({first}, lambda v: v in members) == members,  # pyright: ignore[reportPrivateUsage]
        "elements": [],
    }


OPERATIONS: dict[str, Callable[..., Answer]] = {
    f.__name__: f
    for f in (
        terminals_served,
        farthest_terminal,
        feeds,
        trace,
        run_length,
        controllers_between,
        cut_off,
        system_storeys,
        systems_crossing_storeys,
        open_ends,
        unconnected,
        circuit_of,
        system_info,
    )
}


def ask(g: ServicesGraph, op: str, **args: Any) -> Answer:
    """One operation's answer, `{"status": "ok", "value", "elements" (at most 30, then "more"),
    ...}`, or `{"status": "unknown", "reason"}`; never raises for a bad id or argument."""
    if op not in OPERATIONS:
        return {"status": "unknown", "reason": f"no operation '{op}'"}
    try:
        said = OPERATIONS[op](g, **{k: v for k, v in args.items() if v is not None})
    except UnknownAnswerError as e:
        return {"status": "unknown", "reason": str(e)}
    except TypeError:
        return {"status": "unknown", "reason": f"wrong arguments for {op}"}
    except Exception as error:  # SV-24: a tool never raises; the reason names what broke
        return {
            "status": "unknown",
            "reason": f"{op} failed on this model ({type(error).__name__})",
        }
    elements: list[str] = said.get("elements") or []
    if len(elements) > MAX_ELEMENTS:
        said |= {"elements": elements[:MAX_ELEMENTS], "more": len(elements) - MAX_ELEMENTS}
    return {"status": "ok", **said}
