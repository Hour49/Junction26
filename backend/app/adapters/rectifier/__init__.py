"""`RECTIFIER=r3`: the photo experiment's winning rectifier (.agents/exp/photo.md, R3 with R4's
guard), as the `Rectifier` port of ingest's normalise stage.

Only a `photo_plan` (a camera photo of a drawing) is rectified; every other image is kept.
1. R1c (classical.py): the paper as a quad with a sheet-like border, one homography. Right on
   7 of 7 real photos it fired on; it fires when the paper is lighter than what is around it.
2. Else UVDoc (uvdoc.py): a learned dewarp, which always finds something. When the outline it
   finds sits at the photo's own corners (FILLS_FRAME), the plan already fills the photo and a
   dewarp would only crop into it (R4), so the photo is kept.
On 30 real Commons photos R3 flattened the plan in 16 and partly in 14 (cropping or bending);
on synthetic photos the corners are within 2% of the sheet's diagonal in 91-99%.
"""

import io
import math

import numpy as np
from PIL import Image as PILImage

from app.adapters.rectifier.classical import Corners, Image, find_quad, warp_quad
from app.adapters.rectifier.uvdoc import Dewarper, dewarp
from app.core.ingest.model import ContentKind, Quad, Rectified

# Mean corner distance to the photo's corners, as a share of its diagonal, below which the plan
# fills the photo. 0.065 (photo, prototypes/photo/rectify.py): on 30 real photos UVDoc crops the
# caption or legend at 5.5-6.1% (037, 040, 041, 042) and does well from 6.8% (033) up.
FILLS_FRAME = 0.065
JPEG_QUALITY = 95
# How each method is named to a person (`Normalised.rectifier`, shown in reasons and traces):
# R1c's paper border and UVDoc's dewarp in plain words (QA R4, 2026-11-14).
CLASSICAL = "paper edges"
LEARNED = "page flattening"


class R3Rectifier:
    def __init__(self, dewarper: Dewarper) -> None:
        self._dewarper = dewarper

    def rectify(self, image: bytes, kind: ContentKind) -> Rectified | None:
        if kind != "photo_plan":
            return None
        with PILImage.open(io.BytesIO(image)) as opened:
            image_format = opened.format
            photo: Image = np.asarray(opened.convert("RGB"), np.uint8)
        quad = find_quad(photo)
        if quad is not None:
            return _rectified(warp_quad(photo, quad), quad, photo, image_format, CLASSICAL)
        flat, corners = dewarp(photo, self._dewarper.grid(photo))
        if fills_frame(photo, corners):
            return None
        return _rectified(flat, corners, photo, image_format, LEARNED)


def fills_frame(photo: Image, corners: Corners) -> bool:
    height, width = photo.shape[:2]
    frame = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], float)
    distance = float(np.linalg.norm(corners - frame, axis=1).mean())
    return distance < FILLS_FRAME * math.hypot(width, height)


def _rectified(
    flat: Image, corners: Corners, photo: Image, image_format: str | None, method: str
) -> Rectified:
    """The flat image in the photo's own format, and the corners as fractions of the photo."""
    height, width = photo.shape[:2]
    quad: Quad = tuple(  # type: ignore[assignment]
        (min(1.0, max(0.0, float(x) / width)), min(1.0, max(0.0, float(y) / height)))
        for x, y in corners
    )
    buffer = io.BytesIO()
    if image_format == "PNG":
        PILImage.fromarray(flat).save(buffer, "PNG")
    else:
        PILImage.fromarray(flat).save(buffer, "JPEG", quality=JPEG_QUALITY)
    return Rectified(
        data=buffer.getvalue(),
        quad=quad,
        width=flat.shape[1],
        height=flat.shape[0],
        method=method,
    )
