"""Parity: the endpoint against local onnxruntime on the CPU, same model, same pages.

    cd backend && uv run python ../deploy/verda/parity.py --model <folder> [--pages 20]

Takes `--pages` images spread over the val part (data/stoa/exp/split.json), reads each with the
backend's `OnnxDetector` on the CPU and through the endpoint (`RemoteReader`), and compares per
page: element count per class, plan count, and each box against its nearest box of the same
class in the other reply, in page pixels. Parity holds when every count is equal and no box is
more than 1 px off. URL and key from the repo's .env (never printed).
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent))

from app.adapters.raster_detector import OnnxDetector
from app.adapters.raster_remote import HttpReaderClient, RemoteReader
from app.core.drawing.model import Page
from app.core.pipeline.model import DrawingFile, Extracted, Sheet

import verda_serve

DATASET = ROOT / "data/stoa/full/junction-dataset"


class Files:
    def read(self, path: str) -> bytes:
        return (DATASET / path).read_bytes()


def items(got: Extracted) -> list[tuple[str, tuple[float, ...]]]:
    return [(e.class_, e.box) for e in got.elements] + [("plan", p.box) for p in got.plans]


def worst_px(a: Extracted, b: Extracted, width: int, height: int) -> float:
    """The largest distance (px, any edge) from a box of `a` to the nearest box of its class in
    `b`, both ways."""
    scale = (width, height, width, height)

    def one_way(xs: list, ys: list) -> float:
        worst = 0.0
        for kind, box in xs:
            near = [
                max(abs(u - v) * s for u, v, s in zip(box, other, scale, strict=True))
                for k, other in ys
                if k == kind
            ]
            worst = max(worst, min(near, default=float("inf")))
        return worst

    return max(one_way(items(a), items(b)), one_way(items(b), items(a)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--pages", type=int, default=20)
    args = parser.parse_args()
    split = json.loads((ROOT / "data/stoa/exp/split.json").read_text())
    files_val = split["parts"]["val"]["files"]
    pages = files_val[:: max(1, len(files_val) // args.pages)][: args.pages]  # spread over val
    files = Files()
    env = verda_serve._env()
    local = OnnxDetector.from_folder(files, args.model)  # type: ignore[arg-type]
    remote = RemoteReader(files, HttpReaderClient(env["VERDA_READER_URL"],  # type: ignore[arg-type]
                                                  env["VERDA_INFERENCE_API_KEY"]))  # fmt: skip
    equal, worst_all = 0, 0.0
    for image in pages:
        path = image
        with Image.open(DATASET / path) as page:
            width, height = page.size
        source = DrawingFile(path=path, size=1, sha256="0" * 64, kind="png")
        sheet = Sheet(file=source, pages=(Page(page=1, width=width, height=height, unit="px"),))
        a, b = local.extract(source, sheet), remote.extract(source, sheet)
        counts_a = Counter(k for k, _ in items(a))
        counts_b = Counter(k for k, _ in items(b))
        worst = worst_px(a, b, width, height)
        same = counts_a == counts_b and worst <= 1.0
        equal += same
        worst_all = max(worst_all, worst if worst != float("inf") else 0.0)
        print(json.dumps({"page": Path(path).name, "same": same, "worst_px": round(worst, 2),
                          "cpu": dict(counts_a), "endpoint": dict(counts_b)}))  # fmt: skip
    print(json.dumps({"pages": len(pages), "parity": equal, "worst_px": round(worst_all, 2)}))


if __name__ == "__main__":
    main()
