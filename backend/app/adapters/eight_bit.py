"""A 16-bit greyscale image (a PNG Pillow opens as mode I;16, such as a scanner writes) scaled to
8-bit, for the readers of an upload's own bytes and for the frame every later reader sees.

Pillow's `convert` clips I;16 values above 255 to 255 instead of scaling them, so every pixel
brighter than 0.4% grey turns white and a plan with grey lines reads as a blank page (QA r7,
review-202 finding 4). 16-bit RGB, grey-with-alpha and RGBA PNGs are scaled by Pillow itself
when they are opened.
"""

import numpy as np
from PIL import Image


def eight_bit(image: Image.Image) -> Image.Image:
    """An I;16 image as 8-bit greyscale (the high byte of each value); any other as it is."""
    if not image.mode.startswith("I;16"):
        return image
    return Image.fromarray((np.asarray(image, np.uint16) >> 8).astype(np.uint8), "L")
