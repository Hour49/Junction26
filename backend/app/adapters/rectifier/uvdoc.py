"""UVDoc (Verhoeven et al. 2023, MIT, github.com/tanguymagne/UVDoc @4c9b82b): a learned document
dewarper that predicts a coarse 2-D grid of where each point of the flat page is in the photo.
Run here as ONNX on onnxruntime (exported once from the published weights by
scripts/export_uvdoc_onnx.py; the file lives only in data/models/photo/, like the detector's).
"""

from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np
from numpy.typing import NDArray

from app.adapters.rectifier.classical import Corners, Image, quad_size
from app.core.errors import NotFoundError

INPUT_SIZE = (488, 712)  # width, height the network was trained at
THREADS = 4


class Dewarper(Protocol):
    def grid(self, photo: Image) -> NDArray[np.float64]:
        """Where the flat page's grid nodes are in the photo, in pixels: (rows, cols, 2) x, y."""
        ...


class OnnxUvdoc:
    def __init__(self, model: Path) -> None:
        if not model.is_file():
            raise NotFoundError(
                f"{model} is missing: export it once with backend/scripts/export_uvdoc_onnx.py"
            )
        import onnxruntime

        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = THREADS
        options.inter_op_num_threads = 1
        self._session: Any = onnxruntime.InferenceSession(
            str(model), options, providers=["CPUExecutionProvider"]
        )

    def grid(self, photo: Image) -> NDArray[np.float64]:
        image = cv2.resize(photo, INPUT_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)
        batch = (image / 255).transpose(2, 0, 1)[None]
        (grid,) = self._session.run(["grid2d"], {"image": batch})
        nodes = np.asarray(grid[0], np.float64).transpose(1, 2, 0)  # in [-1, 1], x then y
        height, width = photo.shape[:2]
        return np.stack(
            [(nodes[..., 0] + 1) / 2 * (width - 1), (nodes[..., 1] + 1) / 2 * (height - 1)], -1
        )


def dewarp(photo: Image, grid: NDArray[np.float64]) -> tuple[Image, Corners]:
    """The flat page the grid describes, and its outline's corners in the photo. The grid is
    upsampled bilinearly with its corner nodes on the output's corner pixels (as UVDoc does)."""
    rows, cols = grid.shape[:2]
    corners = np.array([grid[0, 0], grid[0, -1], grid[-1, -1], grid[-1, 0]])
    width, height = quad_size(corners)
    at_x = np.tile(np.arange(width, dtype=np.float32) * (cols - 1) / max(1, width - 1), (height, 1))
    at_y = np.tile(
        (np.arange(height, dtype=np.float32) * (rows - 1) / max(1, height - 1))[:, None], (1, width)
    )
    nodes = grid.astype(np.float32)
    map_x = cv2.remap(nodes[..., 0], at_x, at_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    map_y = cv2.remap(nodes[..., 1], at_x, at_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    flat = cv2.remap(photo, map_x, map_y, cv2.INTER_CUBIC, borderValue=(255, 255, 255))
    return np.asarray(flat, np.uint8), corners
