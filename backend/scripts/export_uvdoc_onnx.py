"""Export UVDoc (MIT, github.com/tanguymagne/UVDoc @4c9b82b) to ONNX for RECTIFIER=r3, once.

The backend runs the model on onnxruntime; torch is needed only here, in a throwaway environment:

    cd backend && uv run --no-project --python 3.12 --with torch==2.9.1 --with onnx \\
        --with onnxruntime --with numpy --index https://download.pytorch.org/whl/cpu \\
        --index-strategy unsafe-best-match python scripts/export_uvdoc_onnx.py \\
        <UVDoc checkout> <uvdoc_best_model.pkl> [--out ../data/models/photo/uvdoc.onnx]

The photo experiment keeps both inputs locally: the checkout in prototypes/photo/third_party/UVDoc
and the weights in data/models/photo/uvdoc_best_model.pkl. The export is checked against torch on
a random image before it is written.
"""

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
import onnxruntime
import torch

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "data" / "models" / "photo" / "uvdoc.onnx"
INPUT = (1, 3, 712, 488)  # batch, RGB, height, width the network was trained at


def main() -> None:
    parser = argparse.ArgumentParser(description="Exports UVDoc to ONNX.")
    parser.add_argument("checkout", type=Path)
    parser.add_argument("weights", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    sys.path.insert(0, str(args.checkout))
    from model import UVDocnet  # type: ignore[import-not-found]

    net = UVDocnet(num_filter=32, kernel_size=5)
    state = torch.load(args.weights, map_location="cpu", weights_only=False)["model_state"]
    net.load_state_dict(state)
    net.eval()
    image = torch.rand(*INPUT, generator=torch.Generator().manual_seed(0))
    with torch.no_grad():
        expected = net(image)[0].numpy()
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "uvdoc.onnx"
        torch.onnx.export(
            net,
            (image,),
            str(path),
            input_names=["image"],
            output_names=["grid2d", "grid3d"],
            opset_version=17,
            dynamo=False,
        )
        session = onnxruntime.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        got = session.run(["grid2d"], {"image": image.numpy()})[0]
        difference = float(np.abs(got - expected).max())
        if difference > 1e-4:
            raise SystemExit(f"the ONNX grid differs from torch by {difference}")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(path.read_bytes())
    print(f"wrote {args.out} (max difference to torch {difference:.1e})")


if __name__ == "__main__":
    main()
