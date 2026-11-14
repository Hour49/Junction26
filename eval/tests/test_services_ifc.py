"""`services_backend.py graph` run for real in backend/'s environment on a synthetic IFC, then the
truth on its graph. Skipped where backend/ has no environment (as in eval's CI job)."""

import os
import subprocess
from pathlib import Path

import pytest

from stoa_eval import backend
from stoa_eval.services import Net, ServicesGraph

pytestmark = pytest.mark.skipif(
    not (backend.BACKEND / ".venv").is_dir(), reason="backend/ has no environment"
)
MAKER = Path(__file__).with_name("make_services_ifc.py")


def test_a_synthetic_ifc_becomes_a_graph_the_truth_reads(tmp_path: Path) -> None:
    ifc = tmp_path / "tower_ventilation.ifc"
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    subprocess.run(
        ["uv", "run", "--locked", "--project", str(backend.BACKEND), "python", MAKER, ifc],
        cwd=backend.BACKEND, env=env, check=True,
    )  # fmt: skip
    out = tmp_path / "graph.json"
    backend.run("graph", "--ifc", str(ifc), "--out", str(out), script=backend.SERVICES_SCRIPT)
    graph = ServicesGraph.model_validate_json(out.read_text("utf-8"))
    net = Net(graph)
    by_rid = {net.rid(g): g for g in net.nodes}
    assert graph.model == "tower_ventilation"
    assert sorted(by_rid) == [101, 102, 103, 104, 105, 106, 107]
    assert len(graph.edges) == 4
    assert len(graph.flow) == 4
    assert {s.name: s.elevation for s in graph.storeys} == {"L1": 0.0, "L2": 3.0}
    assert graph.system_types["SA1"] == "Supply Air"
    fan, lamp, ahu, grille = by_rid[106], by_rid[107], by_rid[101], by_rid[105]
    assert (net.nodes[fan].ports, net.nodes[fan].connected) == (1, 0)
    assert net.circuit_of(lamp) == "P1/3"
    assert net.src(ahu) and net.src(fan)
    assert net.terminals_served(ahu) == 1
    assert net.run_length(ahu) == 5.0
    assert net.run_length(system="SA1") == 5.0
    assert net.feeds(grille) == [101]
    assert net.cut_off(by_rid[103]) == (2, None)  # the damper: the duct and the grille after it
    assert net.controllers_between(grille, ahu) == ([103], 4, True)
    assert net.system_storeys("SA1") == 2
    assert net.unconnected("fan", "L1") == 1
    assert net.describe(ahu) == ("AHU on the top floor", {"family": "AHU", "top": True})
