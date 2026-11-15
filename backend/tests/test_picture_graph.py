"""What connects to what on a services picture (app/core/picture_graph.py): terminals attached to
the line graph's edges, systems as one style's connected edges."""

from app.core.ifc_facts import Spot
from app.core.picture_graph import (
    LineEdge,
    LineGraph,
    LineNode,
    Terminal,
    attach,
    connected,
    graph_facts,
    systems,
)


def edge(
    id_: str, a: str, b: str, style: str, *points: tuple[float, float], m: float | None = None
) -> LineEdge:
    return LineEdge(id=id_, a=a, b=b, style=style, points=points, length_m=m)


def graph() -> LineGraph:
    """Two supply branches from one junction (n2), and a separate return line, 10 px per m.

    n1 (0,0) --e1-- n2 (100,0) --e2-- n3 (200,0)       supply
                     |
                     e3
                     |
                    n4 (100,100)                       supply
    n5 (0,50) --e4-- n6 (200,50)                       return (no shared node with supply)
    """
    nodes = (
        LineNode(id="n1", at=(0, 0), degree=1),
        LineNode(id="n2", at=(100, 0), degree=3),
        LineNode(id="n3", at=(200, 0), degree=1),
        LineNode(id="n4", at=(100, 100), degree=1),
        LineNode(id="n5", at=(0, 50), degree=1),
        LineNode(id="n6", at=(200, 50), degree=1),
    )
    edges = (
        edge("e1", "n1", "n2", "Supply", (0, 0), (100, 0), m=10.0),
        edge("e2", "n2", "n3", "Supply", (100, 0), (200, 0), m=10.0),
        edge("e3", "n2", "n4", "Supply", (100, 0), (100, 100), m=10.0),
        edge("e4", "n5", "n6", "Return", (0, 50), (200, 50), m=20.0),
    )  # fmt: skip
    return LineGraph(nodes=nodes, edges=edges, px_per_m=10.0, size_px=(300, 200))


def test_systems_are_one_styles_connected_edges_with_their_length() -> None:
    found = {s.style: s for s in systems(graph())}
    assert set(found["Supply"].edges) == {"e1", "e2", "e3"} and found["Supply"].length_m == 30.0
    assert found["Return"].edges == ("e4",) and found["Return"].length_m == 20.0


def test_two_styles_meeting_at_one_node_stay_two_systems() -> None:
    g = graph()
    joined = g.model_copy(
        update={"edges": (*g.edges, edge("e5", "n3", "n6", "Return", (200, 0), (200, 50)))}
    )
    styles = sorted(s.style for s in systems(joined))
    assert styles == ["Return", "Supply"]  # e5 joins the return line only
    assert {s.style: len(s.edges) for s in systems(joined)} == {"Supply": 3, "Return": 2}


def test_a_length_is_unknown_when_an_edge_has_none() -> None:
    g = graph()
    g = g.model_copy(
        update={"edges": (*g.edges, edge("e6", "n4", "n7", "Supply", (100, 100), (100, 120)))}
    )
    assert {s.style: s.length_m for s in systems(g)}["Supply"] is None


def test_a_terminal_attaches_to_the_nearest_line_within_the_bound_and_else_is_refused() -> None:
    near_end = Terminal(id="t1", label="radiator", at=(205, 3))  # by n3, 0.6 m off
    on_branch = Terminal(id="t2", label="radiator", at=(104, 90))  # beside e3
    on_return = Terminal(id="t3", label="radiator", at=(150, 55))  # nearer e4 than e2
    far = Terminal(id="t4", label="radiator", at=(280, 180))  # 13 m from anything
    got = {a.terminal: a for a in attach(graph(), [near_end, on_branch, on_return, far], 15.0)}
    assert got["t1"].edge == "e2" and got["t2"].edge == "e3" and got["t3"].edge == "e4"
    assert got["t1"].distance_px == 5.831
    assert got["t4"].edge is None and got["t4"].system is None
    assert got["t4"].why == "no line within 15 px"
    supply = next(s for s in systems(graph()) if s.style == "Supply")
    assert got["t1"].system == got["t2"].system == supply.id
    assert got["t3"].system != supply.id


def test_is_x_connected_to_y_reads_the_attached_systems() -> None:
    spots = {"t1": (205, 3), "t2": (104, 90), "t3": (150, 55), "t4": (280, 180)}
    terminals = [Terminal(id=k, label="radiator", at=at) for k, at in spots.items()]
    attached = attach(graph(), terminals, 15.0)
    assert connected(attached, "t1", "t2") is True
    # on different systems is not "no": a line read with a gap splits one system in two
    # (pics-graph.md: 5% of pieces lost -> pair recall 0.41, precision 1.0), so only "yes" is said
    assert connected(attached, "t1", "t3") is None
    assert connected(attached, "t1", "t4") is None  # t4 is not attached: unknown


def test_a_system_lists_its_terminals_and_its_source_equipment() -> None:
    terminals = [Terminal(id="t1", label="radiator", at=(205, 3)),
                 Terminal(id="b1", label="boiler", at=(-4, 2), equipment=True),
                 Terminal(id="t3", label="radiator", at=(150, 55))]  # fmt: skip
    attached = attach(graph(), terminals, 15.0)
    found = {s.style: s for s in systems(graph(), attached)}
    assert found["Supply"].terminals == ("t1",) and found["Supply"].sources == ("b1",)
    assert found["Return"].terminals == ("t3",) and found["Return"].sources == ()


def test_facts_give_each_system_its_terminals_and_length_and_each_terminal_its_system() -> None:
    terminals = [Terminal(id="t1", label="radiator", at=(205, 3)),
                 Terminal(id="t2", label="radiator", at=(104, 90)),
                 Terminal(id="t3", label="radiator", at=(150, 55))]  # fmt: skip
    g = graph()
    g = g.model_copy(
        update={"edges": (*g.edges, edge("e7", "n7", "n8", "Supply", (0, 190), (9, 190)))}
    )
    found = systems(g, attach(g, terminals, 15.0))
    spot = Spot(page=1, box=(0.6, 0.0, 0.7, 0.05), reader="template")
    facts = graph_facts(
        found, terminals, {"t1": spot}, discipline="heating", source="picture graph"
    )
    said = {(f.topic, f.subject): f for f in facts}
    assert said[("system.terminal_count", "Supply 1")].value == 2  # two supply pieces: numbered
    assert said[("system.terminal_count", "Supply 1")].spots == (spot,)
    assert said[("system.terminal_count", "Supply 2")].value == 0
    assert said[("system.length", "Supply 1")].value == 30.0
    assert ("system.length", "Supply 2") not in said  # e7 has no length
    assert said[("system.terminal_count", "Return")].value == 1
    assert said[("terminal.system", "radiator (t3)")].value == "Return"
    assert said[("terminal.system", "radiator (t1)")].spots == (spot,)
