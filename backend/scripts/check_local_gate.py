"""Parity of the backend's local gate scores with local-dec's offline fit on val.

    cd backend && uv run python scripts/check_local_gate.py --arm C1 [--fixture N]

For each model data/models/arbiter/T1/<name>-<arm>.json (lgate-rt, lgate-rt-noL1, lgate2-rt), the
core's score() over every val unit's readings (data/stoa/exp/local-dec/rt/readings-<arm>.json,
written by prototypes/localdec/lgate_rt.py with the inputs the backend has at runtime) against
the offline signal of the same fit (rt/signal-<name>-<arm>-val-allfit.json). Prints the largest
difference (1e-6 expected) and the time per page. --fixture N writes
tests/fixtures/local_gate/parity.json: the lgate2-rt model and N units per family (pages renamed
val-<n>), which tests/test_local_gate.py replays.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.local_gate import load_local_gate
from app.core.answering.local_gate import GateReading, score

ROOT = Path(__file__).resolve().parents[2]
RT = ROOT / "data/stoa/exp/local-dec/rt"
MODELS = ROOT / "data/models/arbiter/T1"
FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/local_gate/parity.json"
NAMES = ("lgate-rt", "lgate-rt-noL1", "lgate2-rt")


def reading(unit: dict) -> GateReading:
    return GateReading(
        answer=unit["answer"],
        probs=unit["probs"],
        readers=unit["readers"],
        scores=tuple(unit["scores"]),
        plans=unit["plans"],
        arbiter_p=unit["arbiter_p"],
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--fixture", type=int, default=0)
    a = ap.parse_args()
    units = json.loads((RT / f"readings-{a.arm}.json").read_text())
    pages = len({u["file"] for u in units})
    for name in NAMES:
        model = load_local_gate(MODELS / f"{name}-{a.arm}.json")
        sig = json.loads((RT / f"signal-{name}-{a.arm}-val-allfit.json").read_text())["values"]
        want = {(v["file"], v["family"]): v["value"] for v in sig}
        t0 = time.perf_counter()
        got = {(u["file"], u["family"]): score(model, u["family"], reading(u)) for u in units}
        ms = 1000 * (time.perf_counter() - t0) / pages
        diff = max(abs(float(got[k] or 0.0) - v) for k, v in want.items())
        print(f"{name} {a.arm}: units {len(want)}, max |diff| {diff:.2e}, {ms:.3f} ms per page")
    if a.fixture:
        model_doc = json.loads((MODELS / f"lgate2-rt-{a.arm}.json").read_text())
        sig = json.loads((RT / f"signal-lgate2-rt-{a.arm}-val-allfit.json").read_text())["values"]
        want = {(v["file"], v["family"]): v["value"] for v in sig}
        by_family, names = defaultdict(list), {}
        for u in units:
            by_family[u["family"]].append(u)
        rows = []
        for family, mine in by_family.items():
            for u in mine[: a.fixture]:
                page = names.setdefault(u["file"], f"val-{len(names) + 1}")
                rows.append(
                    {**{k: v for k, v in u.items() if k != "file"}, "page": page,
                     "expected": want[(u["file"], family)]}
                )  # fmt: skip
        keep = ("schema", "name", "families", "readers", "blocks", "prior", "mu", "sd", "coef")
        model = {k: model_doc[k] for k in (*keep, "intercept")}
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps({"model": model, "units": rows}, indent=1))
        print("fixture ->", FIXTURE, len(rows), "units")


if __name__ == "__main__":
    main()
