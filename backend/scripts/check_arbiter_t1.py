"""Parity of the backend's count arbiter with local-dec's T1 arm on val, from the per-source
counts T1 was scored with (data/stoa/exp/local-dec/, gitignored).

    cd backend && uv run python scripts/check_arbiter_t1.py [--fixture N] [--l1 DATASET]
        [--e2e N --images DATASET]

Every (page, family) with a val answer: reading_of() over the eight-view extraction
(valsrc/Lv8), the one-view one (valsrc/L1v) and L1's val probabilities, then the core's pick()
against T1's targets and confidences (the base where it is above L1's last class, which T1
offline let L1 pull down: 1 val unit). Prints the mismatches (0 expected). --fixture N writes
tests/fixtures/count_arbiter/parity.json: the model and N units per family (pages renamed val-<n>,
the changed picks first), which tests/test_count_arbiter.py replays. --l1 also runs the ONNX L1
on each val page (one view) against L1-v1's probabilities and times it on the CPU. --e2e N runs
the component itself (arbiter-t1:C-yolo26l:C-yolo26l-onnx-val: both detector reads and L1, on the
CPU) on the first N val pages and compares each family's element count with the arm built from
T1's picks with one-view L1 (local-dec/T1-v1), timing each page.
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.count_arbiter import (
    ArbiterCountExtractor,
    L1PageCounts,
    load_model,
    reading_of,
)
from app.adapters.raster_detector import OnnxDetector
from app.core.pipeline.count_arbiter import FAMILY_CLASSES, pick
from app.core.pipeline.model import DrawingFile, Extracted, Sheet

ROOT = Path(__file__).resolve().parents[2]
LD = ROOT / "data/stoa/exp/local-dec"
FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/count_arbiter/parity.json"


def extracted(path: Path) -> tuple[str, Extracted]:
    d = json.loads(path.read_text())
    elements = [
        {"id": e["id"], "class": e["class"], "page": 1, "box": e["box"],
         "attrs": {"score": e.get("attrs", {}).get("score", 0)}}
        for e in d["elements"]
    ]  # fmt: skip
    plans = [{"id": p["id"], "page": 1, "box": p["box"]} for p in d["plans"]]
    found = Extracted.model_validate(
        {"method": "detector", "scale": {"status": "no_scale"}, "plans": plans,
         "elements": elements}
    )  # fmt: skip
    return d["file"], found


def folder(name: str) -> dict[str, Extracted]:
    return dict(extracted(p) for p in sorted((LD / name).glob("*.json")))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", type=Path, default=ROOT / "data/models/arbiter/T1")
    ap.add_argument("--fixture", type=int, default=0)
    ap.add_argument("--l1", type=Path)
    ap.add_argument("--e2e", type=int, default=0)
    ap.add_argument("--images", type=Path)
    a = ap.parse_args()
    if a.e2e:
        end_to_end(a.e2e, a.images, a.model_dir)
        return
    model = load_model(a.model_dir)
    base, second = folder("valsrc/Lv8"), folder("valsrc/L1v")
    probs = {
        r["file"]: r["probs"]
        for r in json.loads((LD / "L1-cnxt-t-1024/val-probs.json").read_text())
    }
    targets = json.loads((LD / "T1.targets.json").read_text())
    confs = json.loads((LD / "T1.conf.json").read_text())
    units, bad, worst, changed, above = [], 0, 0.0, Counter(), []
    for file in sorted(targets):
        for family in model.families:
            if family not in targets[file] or file not in base:
                continue
            reading = reading_of(family, base[file], second[file], probs[file])
            got = pick(model, family, reading)
            want = targets[file][family]
            if reading.base >= len(reading.probs):  # the base is kept above L1's last class
                above.append(f"{file} {family}: base {reading.base}, T1 {want}, kept {got.count}")
                bad += got.count != reading.base
            else:
                bad += got.count != want
                worst = max(worst, abs(got.p - confs[file][family]))
            changed[family] += got.count != reading.base
            units.append((family, file, reading, want, confs[file][family]))
    print(
        f"units {len(units)}, pick mismatches {bad}, max |P diff| {worst:.2e}, "
        f"changed vs base {dict(changed)}; base above L1's last class {len(above)}"
    )
    for line in above:
        print("  " + line)
    if a.fixture:
        rows, names = [], {}
        for family in model.families:
            mine = [u for u in units if u[0] == family]
            mine.sort(key=lambda u: (u[3] == u[2].base, u[1]))  # changed picks first
            for fam, file, r, want, p in mine[: a.fixture]:
                rows.append(
                    {
                        "page": names.setdefault(file, f"val-{len(names) + 1}"),
                        "family": fam,
                        "base": r.base,
                        "scores": list(r.scores),
                        "plans": r.plans,
                        "second": r.second,
                        "probs": [round(v, 8) for v in r.probs],
                        "expected": want,
                        "expected_p": round(p, 8),
                    }
                )
        shipped = json.loads((a.model_dir / "arbiter.json").read_text())
        prior = json.loads((a.model_dir / "prior.json").read_text())
        FIXTURE.write_text(
            json.dumps(
                {
                    "arbiter": {
                        "families": {
                            f: {k: v[k] for k in ("mu", "sd", "coef", "intercept")}
                            for f, v in shipped["families"].items()
                        }
                    },
                    "prior": prior,
                    "units": rows,
                },
                indent=1,
            )
        )
        print("fixture ->", FIXTURE, len(rows), "units")
    if a.l1:
        l1 = L1PageCounts.from_folder(a.model_dir)
        ref = {r["file"]: r["probs"] for r in json.loads((LD / "L1-v1/val-probs.json").read_text())}
        diffs, tops, ms = [], 0, []
        for file in sorted(ref):
            data = (a.l1 / file).read_bytes()
            t0 = time.perf_counter()
            got = l1.probs(data)
            ms.append(1000 * (time.perf_counter() - t0))
            for head, p in got.items():
                q = ref[file][head]
                diffs.append(max(abs(x - y) for x, y in zip(p, q, strict=True)))
                tops += max(range(len(p)), key=p.__getitem__) != max(
                    range(len(q)), key=q.__getitem__
                )
        ms.sort()
        print(
            f"L1 one view vs L1-v1: pages {len(ref)}, max |P diff| {max(diffs):.2e}, "
            f"top differs {tops} of {len(diffs)}; CPU ms/page median {ms[len(ms) // 2]:.0f}, "
            f"p90 {ms[int(0.9 * len(ms))]:.0f}"
        )


class Images:
    def __init__(self, root: Path) -> None:
        self.root = root

    def read(self, path: str) -> bytes:
        return (self.root / path).read_bytes()


def end_to_end(n: int, images: Path, model_dir: Path) -> None:
    files = Images(images)
    arm = ROOT / "data/models/detector/C-yolo26l"
    one = ROOT / "data/stoa/exp/detector/raw/C-yolo26l-onnx-val.thresholds.json"
    arbiter = ArbiterCountExtractor.from_folder(
        OnnxDetector.from_folder(files, arm, views=8),
        OnnxDetector.from_folder(files, arm, one),
        files,
        model_dir,
    )
    want = folder("T1-v1/cubicasa5k")
    bad, ms = 0, []
    for file in sorted(want)[:n]:
        source = DrawingFile(path=file, size=1, sha256="0" * 64, kind="png")
        t0 = time.perf_counter()
        found = arbiter.extract(source, Sheet(file=source, pages=()))
        ms.append(1000 * (time.perf_counter() - t0))
        for family, classes in FAMILY_CLASSES.items():
            got = sum(e.class_ in classes for e in found.elements)
            ref = sum(e.class_ in classes for e in want[file].elements)
            if got != ref:
                bad += 1
                print(f"  {file} {family}: backend {got}, T1-v1 {ref}")
    ms.sort()
    print(
        f"end to end: pages {len(ms)}, family counts differing {bad} of {6 * len(ms)}; "
        f"CPU ms/page median {ms[len(ms) // 2]:.0f}, max {ms[-1]:.0f}"
    )


if __name__ == "__main__":
    main()
