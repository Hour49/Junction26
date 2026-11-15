"""model.pt -> model.onnx (dynamic height/width, input (x/255 - 0.5)/0.25, output class logits).

python export.py <model.pt> <model.onnx>"""

import sys

import torch
from train import model


def main() -> None:
    weights = __import__("pathlib").Path(sys.argv[1])
    net = model((weights.parent / "encoder.txt").read_text().strip(), None)
    net.load_state_dict(torch.load(sys.argv[1], map_location="cpu"))
    net.eval()
    torch.onnx.export(
        net,
        torch.zeros(1, 3, 512, 512),
        sys.argv[2],
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={"image": {0: "n", 2: "h", 3: "w"}, "logits": {0: "n", 2: "h", 3: "w"}},
        opset_version=17,
        dynamo=False,
    )


if __name__ == "__main__":
    main()
