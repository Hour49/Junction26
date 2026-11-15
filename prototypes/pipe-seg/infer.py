"""Class maps for every page under a render root: python infer.py <model.pt> <root> <out> <set>...

Writes <out>/<set>/<variant>-150/<stem>.cls.png (uint8 argmax class, 0 = no line)."""

import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from train import model, predict


def main() -> None:
    weights, root, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    torch.set_num_threads(int(__import__("os").environ.get("THREADS", "160")))
    net = model((weights.parent / "encoder.txt").read_text().strip(), None)
    net.load_state_dict(torch.load(weights, map_location="cpu"))
    net.eval()
    for name in sys.argv[4:]:
        for page in sorted((root / name).glob("*-150/*")):
            if page.suffix not in (".png", ".jpg"):
                continue
            t = time.time()
            cls = predict(net, np.array(Image.open(page).convert("RGB")))
            dest = out / name / page.parent.name
            dest.mkdir(parents=True, exist_ok=True)
            Image.fromarray(cls).save(dest / f"{page.stem}.cls.png")
            print(name, page.parent.name, page.stem[-30:], f"{time.time() - t:.1f}s", flush=True)


if __name__ == "__main__":
    main()
