"""Parity of the backend's local gate scores with local-dec's offline fit on val.

    cd backend && uv run python scripts/check_local_gate.py --arm C1 [--fixture N]

For each model data/models/arbiter/T1/<name>-<arm>.json (lgate2-rt and lgate-rt-noL1 for the
element families and plan, lgate-rt-rooms and lgate-rt-rooms-noL1 for the room families), the
core's score() over every val unit's readings (data/stoa/exp/local-dec/rt/readings-<arm>.json,
written by prototypes/localdec/lgate_rt.py with the inputs the backend has at runtime) against
the offline signal of the same fit (rt/signal-<name>-<arm>-val-allfit.json). Prints the largest
difference (1e-6 expected) and the time per page. --fixture N writes
tests/fixtures/local_gate/parity.json: the lgate2-rt and lgate-rt-rooms models and N units per
family (pages renamed val-<n>), which tests/test_local_gate.py replays.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.local_gate import load_local_gate
from app.core.answering.local_gate import GateReading, RoomCounts, score

ROOT = Path(__file__).resolve().parents[2]
RT = ROOT / "data/stoa/exp/local-dec/rt"
MODELS = ROOT / "data/models/arbiter/T1"
FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/local_gate/parity.json"
NAMES = ("lgate2-rt", "lgate-rt-noL1", "lgate-rt-rooms", "lgate-rt-rooms-noL1")
FIXTURE_MODELS = ("lgate2-rt", "lgate-rt-rooms")


def reading(unit: dict) -> GateReading:
    return GateReading(
        answer=unit["answer"],
        probs=unit["probs"],
        readers=unit["readers"],
        scores=tuple(unit["scores"]),
        plans=unit["plans"],
        arbiter_p=unit["arbiter_p"],
        rooms=RoomCounts(**unit["rooms"]) if unit["rooms"] else None,
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
        got = {
            (u["file"], u["family"]): score(model, u["family"], reading(u))
            for u in units
            if u["family"] in model.families
        }
        ms = 1000 * (time.perf_counter() - t0) / pages
        assert set(got) == set(want), name
        diff = max(abs(float(got[k] or 0.0) - v) for k, v in want.items())
        print(f"{name} {a.arm}: units {len(want)}, max |diff| {diff:.2e}, {ms:.3f} ms per page")
    if a.fixture:
        keep = ("schema", "name", "families", "readers", "blocks", "prior", "mu", "sd", "coef")
        models, want = {}, {}
        for name in FIXTURE_MODELS:
            doc = json.loads((MODELS / f"{name}-{a.arm}.json").read_text())
            models[name] = {k: doc[k] for k in (*keep, "intercept")}
            sig = json.loads((RT / f"signal-{name}-{a.arm}-val-allfit.json").read_text())["values"]
            want |= {(v["file"], v["family"]): (name, v["value"]) for v in sig}
        by_family, names = defaultdict(list), {}
        for u in units:
            by_family[u["family"]].append(u)
        rows = []
        for family, mine in by_family.items():
            for u in mine[: a.fixture]:
                page = names.setdefault(u["file"], f"val-{len(names) + 1}")
                name, value = want[(u["file"], family)]
                rows.append(
                    {**{k: v for k, v in u.items() if k != "file"}, "page": page,
                     "model": name, "expected": value}
                )  # fmt: skip
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps({"models": models, "units": rows}, indent=1))
        print("fixture ->", FIXTURE, len(rows), "units")


if __name__ == "__main__":
    main()
