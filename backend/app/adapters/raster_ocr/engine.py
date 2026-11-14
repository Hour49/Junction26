"""The real `TextEngine`: rapidocr 3.10 (Apache-2.0) with the PP-OCRv6 small detection and
multilingual recognition models (PaddleOCR, Apache-2.0) on onnxruntime, CPU. rapidocr downloads
the two models on first use (about 20 MB) into its package folder; loading them takes a second,
so one engine is made per process and kept."""

from collections.abc import Sequence
from functools import cached_property
from typing import Any

import numpy as np
from rapidocr import ModelType, RapidOCR
from rapidocr.ch_ppocr_rec import TextRecInput
from rapidocr.utils.process_img import get_rotate_crop_image

from app.adapters.raster_ocr.reader import Quad

THREADS = 4


class RapidOcrEngine:
    @cached_property
    def _ocr(self) -> Any:
        return RapidOCR(
            params={
                "Global.log_level": "warning",
                "Det.model_type": ModelType.SMALL,
                "Rec.model_type": ModelType.SMALL,
                "Det.lang_type": "fi",
                "Rec.lang_type": "fi",
                "EngineConfig.onnxruntime.intra_op_num_threads": THREADS,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            }
        )

    def detect(self, image: np.ndarray) -> list[Quad]:
        # rapidocr's models take BGR, as OpenCV reads images
        found = self._ocr._load_det_model()(np.ascontiguousarray(image[:, :, ::-1]))
        if found.boxes is None:
            return []
        return [[(float(x), float(y)) for x, y in box] for box in found.boxes]

    def recognise(self, crops: Sequence[np.ndarray]) -> list[tuple[str, float]]:
        if not crops:
            return []
        bgr = [np.ascontiguousarray(c[:, :, ::-1]) for c in crops]
        out = self._ocr._load_rec_model()(TextRecInput(img=bgr))
        return [(str(t), float(s)) for t, s in zip(out.txts, out.scores, strict=True)]

    def cut(self, image: np.ndarray, quad: Quad) -> np.ndarray:
        """rapidocr's own cutter: the quad warped to a rectangle, a tall one turned flat."""
        corners = np.array([[float(x), float(y)] for x, y in quad], dtype=np.float32)
        return np.ascontiguousarray(get_rotate_crop_image(image, corners))
