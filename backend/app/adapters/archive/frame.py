"""The frame of an image sheet (the `ImageFrame` port): the EXIF orientation is applied once,
here, and the upright image is what the pipeline reads and the API serves. Page sizes, boxes
and the served page are then in one frame, whatever a later reader does with EXIF (OpenCV
applies it on load, Pillow does not).

An image with no EXIF turn (orientation 1 or none) keeps its bytes. A turned one is written
again: a PNG as PNG, a JPEG as JPEG at quality 95, without the orientation tag. The photo
rectifier (prototypes/photo/) is the `Rectifier` port, applied to the upright image after this.
"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.ingest.model import ContentKind, Normalised, Rectified

ORIENTATION = 0x0112
JPEG_QUALITY = 95


class ExifFrame:
    def normalise(self, data: bytes) -> tuple[bytes, Normalised] | None:
        try:
            with Image.open(io.BytesIO(data)) as image:
                image_format = image.format
                exif = image.getexif().get(ORIENTATION)
                if exif in (None, 1) or image_format not in ("PNG", "JPEG"):
                    width, height = image.size
                    return data, Normalised(exif=exif, width=width, height=height)
                upright = ImageOps.exif_transpose(image)
        except (UnidentifiedImageError, OSError):
            return None
        buffer = io.BytesIO()
        if image_format == "PNG":
            upright.save(buffer, "PNG")
        else:
            upright.save(buffer, "JPEG", quality=JPEG_QUALITY, exif=upright.getexif())
        return buffer.getvalue(), Normalised(exif=exif, width=upright.width, height=upright.height)


class NoRectifier:
    """The `Rectifier` port's default (RECTIFIER=none): every image is kept as it is. The photo
    worker's rectifier replaces it with one adapter and a name in app/settings.py."""

    def rectify(self, image: bytes, kind: ContentKind) -> Rectified | None:
        return None
