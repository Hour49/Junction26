"""The part of a CubiCasa sheet the dev gold annotates, and whether the drawing goes on beyond it
(golden-13 task 1).

A sheet often shows more than the annotated flat: the flats around it, a stairwell, a carport. On
those, a detector trained on the whole sheet learns that unlabelled walls and fixtures are
background, and at answer time it counts them. `stoa_eval annotated-region` writes, for every
experiment train and val image:

- `rings`: the region, the union of the gold rooms (polygons), elements (boxes) and plans that have
  neither (boxes), each grown by MARGIN_M, as outer rings in pixels clipped to the image. Outside
  it nothing is labelled, so it works as a training ignore mask;
- `ink_outside`: the dark ink farther than GAP_M beyond the region over the dark ink inside it,
  measured on the image alone (a model never sees the gold, so nothing else may decide it). A
  border band, solid fills at least SOLID_M thick (scan shadows, dark terraces) and rows or
  columns dark across the image (scanner bars, frame lines) are left out;
- `extends`: ink_outside >= EXTENDS_AT, the drawing visibly goes on beyond the region.

The cut was chosen on hand-labelled images (.agents/exp/golden.md): it flags flats drawn around the
annotated one and misses thin-line extents such as a carport or a stairwell. Use `ink_outside` for
another cut.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
import shapely
from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from .exp_split import ExpPart
from .extraction import Extraction

MARGIN_M = 0.5  # around each gold room and element: covers exterior walls and their windows
GAP_M = 0.25  # ink this close beyond the region belongs to it (wall ends, dimension ticks)
SOLID_M = 0.5  # ink at least this thick in both directions is a fill or a scanner bar, not lines
DARK = 0.6  # a pixel is ink when darker than DARK x the sheet's 95th-percentile grey
BORDER = 0.01  # the band along the image edge left out, as a share of the longer side
BAR = 0.9  # a row or column at least this dark across the image is a scanner bar or a frame line
EXTENDS_AT = 0.2  # ink_outside from which the drawing visibly extends beyond the region
REGION_PARTS: tuple[ExpPart, ...] = ("train", "val")  # test stays unseen until its one run

Ring = list[tuple[float, float]]
Mask = npt.NDArray[np.bool_]


class ImageRegion(BaseModel):
    """One image: its region and the ink beyond it."""

    model_config = ConfigDict(extra="forbid")

    part: ExpPart
    style: str = Field(description="the CubiCasa style, from the file name")
    width: int
    height: int
    box: tuple[float, float, float, float] = Field(description="[x0, y0, x1, y1] of the rings")
    rings: list[Ring] = Field(description="outer rings of the region, pixels, origin top left")
    ink_outside: float = Field(ge=0, description="ink beyond the region over ink inside it")
    extends: bool = Field(description=f"ink_outside >= {EXTENDS_AT}")


class StyleCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    images: int
    extends: int


class AnnotatedRegions(BaseModel):
    """data/stoa/exp/labels/annotated_region.json."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    made_by: str = "cd eval && uv run python -m stoa_eval annotated-region"
    split_sha256: str = Field(description="the data/stoa/exp/split.json it was made from")
    coordinates: str = "pixels of the image, origin top left (gold is in page fractions)"
    margin_m: float = MARGIN_M
    gap_m: float = GAP_M
    solid_m: float = SOLID_M
    dark: float = DARK
    border: float = BORDER
    extends_at: float = EXTENDS_AT
    styles: dict[str, dict[ExpPart, StyleCount]]
    images: dict[str, ImageRegion]


def style_of(file: str) -> str:
    """data/cubicasa5k/high_quality-12.png -> high_quality."""
    return file.rsplit("/", 1)[-1].rsplit("-", 1)[0]


def region(gold: Extraction) -> BaseGeometry:
    """The gold rooms, elements and plans with neither, each grown by MARGIN_M, merged, in pixels,
    clipped to the page. Fails on a gold with no scale, more than one page, or nothing annotated."""
    if len(gold.pages) != 1:
        raise ValueError(f"{gold.file}: {len(gold.pages)} pages, a CubiCasa sheet has one")
    if gold.scale.m_per_unit is None:
        raise ValueError(f"{gold.file}: no m_per_unit, so no margin in pixels")
    width, height = gold.pages[0].width, gold.pages[0].height
    shapes: list[BaseGeometry] = []
    for room in gold.rooms:
        if room.polygon:
            shapes.append(Polygon([(x * width, y * height) for x, y in room.polygon]).buffer(0))
        else:
            x0, y0, x1, y1 = room.box
            shapes.append(shapely.box(x0 * width, y0 * height, x1 * width, y1 * height))
    for element in gold.elements:
        x0, y0, x1, y1 = element.box
        shapes.append(shapely.box(x0 * width, y0 * height, x1 * width, y1 * height))
    used = {room.plan for room in gold.rooms} | {element.plan for element in gold.elements}
    for plan in gold.plans:  # a plan box is its content's bbox: only an empty plan adds it
        if plan.id not in used:
            x0, y0, x1, y1 = plan.box
            shapes.append(shapely.box(x0 * width, y0 * height, x1 * width, y1 * height))
    grow = MARGIN_M / gold.scale.m_per_unit
    grown = [shape.buffer(grow, join_style="mitre") for shape in shapes if not shape.is_empty]
    if not grown:
        raise ValueError(f"{gold.file}: no gold room, element or plan")
    return shapely.union_all(grown).intersection(shapely.box(0, 0, width, height))


def outer_rings(shape: BaseGeometry) -> list[Ring]:
    """The outer ring of each polygon of `shape`, simplified to half a pixel, at 0.1 px."""
    if isinstance(shape, Polygon):
        polygons = [shape]
    elif isinstance(shape, MultiPolygon):
        polygons = list(shape.geoms)
    else:  # a collection left by the clip: keep its polygons
        polygons = [g for g in getattr(shape, "geoms", []) if isinstance(g, Polygon)]
    rings: list[Ring] = []
    for polygon in polygons:
        simple = polygon.simplify(0.5)
        if isinstance(simple, Polygon) and not simple.is_empty:
            rings.append([(round(xy[0], 1), round(xy[1], 1)) for xy in simple.exterior.coords])
    return rings


def fill(rings: Sequence[Ring], width: int, height: int) -> Mask:
    """The pixels inside any of the rings."""
    image = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(image)
    for ring in rings:
        draw.polygon(ring, fill=1)
    return np.asarray(image, dtype=np.bool_)


def grey(image: Image.Image) -> npt.NDArray[np.uint8]:
    """The image in grey levels, transparent parts on white."""
    if image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info):
        white = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(white, image.convert("RGBA"))
    return np.asarray(image.convert("L"), dtype=np.uint8)


def _window_sum(mask: Mask, before: int, after: int) -> npt.NDArray[np.int64]:
    """For each pixel (y, x), the set pixels in rows y - before .. y + after - 1 and the same
    columns (an integral image)."""
    height, width = int(mask.shape[0]), int(mask.shape[1])
    table = np.pad(mask.astype(np.int64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    y0 = np.clip(np.arange(-before, height - before), 0, height)
    y1 = np.clip(np.arange(after, height + after), 0, height)
    x0 = np.clip(np.arange(-before, width - before), 0, width)
    x1 = np.clip(np.arange(after, width + after), 0, width)
    return table[y1][:, x1] - table[y0][:, x1] - table[y1][:, x0] + table[y0][:, x0]


def solid(mask: Mask, k: int) -> Mask:
    """The parts of `mask` a k x k square fits in (a morphological opening): the squares that
    fit (erosion), then every pixel of those squares (dilation by the mirrored window)."""
    if k <= 1:
        return mask.copy()
    before, after = k // 2, k - k // 2
    fits = _window_sum(mask, before, after) == k * k
    return _window_sum(fits, after - 1, before + 1) > 0


def ink(pixels: npt.NDArray[np.uint8], m_per_px: float) -> Mask:
    """Dark pixels, without solid fills SOLID_M thick or more and without rows or columns dark
    across BAR of the image."""
    background = float(np.percentile(pixels, 95))
    dark = pixels < DARK * background
    lines = dark & ~solid(dark, max(1, round(SOLID_M / m_per_px)))
    lines[dark.mean(axis=1) >= BAR, :] = False
    lines[:, dark.mean(axis=0) >= BAR] = False
    return lines


def ink_outside(dark: Mask, inside: Mask, beyond: Mask) -> float:
    """Ink in `beyond`, away from the image border, over ink in `inside`."""
    height, width = dark.shape
    band = max(1, round(BORDER * max(height, width)))
    away = beyond.copy()
    away[:band] = False
    away[-band:] = False
    away[:, :band] = False
    away[:, -band:] = False
    return int(dark[away].sum()) / max(int(dark[inside].sum()), 1)


def annotate(part: ExpPart, gold: Extraction, image: Image.Image) -> ImageRegion:
    """The region of one image and the ink beyond it."""
    width, height = image.size
    page = gold.pages[0]
    if (page.width, page.height) != (width, height):
        raise ValueError(
            f"{gold.file}: image {width}x{height}, gold {page.width:g}x{page.height:g}"
        )
    shape = region(gold)
    m_per_px = gold.scale.m_per_unit
    assert m_per_px is not None  # region() checked
    rings = outer_rings(shape)
    beyond = ~fill(outer_rings(shape.buffer(GAP_M / m_per_px)), width, height)
    ratio = round(ink_outside(ink(grey(image), m_per_px), fill(rings, width, height), beyond), 4)
    x0, y0, x1, y1 = shape.bounds
    return ImageRegion(
        part=part,
        style=style_of(gold.file),
        width=width,
        height=height,
        box=(round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)),
        rings=rings,
        ink_outside=ratio,
        extends=ratio >= EXTENDS_AT,
    )


def annotate_file(job: tuple[ExpPart, Extraction, Path]) -> ImageRegion:
    """annotate() on (part, gold, image path): top level, so a process pool can run it."""
    part, gold, path = job
    with Image.open(path) as image:
        return annotate(part, gold, image)


def style_counts(images: dict[str, ImageRegion]) -> dict[str, dict[ExpPart, StyleCount]]:
    """Per style and part: images, and how many extend beyond their region."""
    counts: dict[str, dict[ExpPart, StyleCount]] = {}
    for record in images.values():
        parts = counts.setdefault(record.style, {})
        count = parts.setdefault(record.part, StyleCount(images=0, extends=0))
        count.images += 1
        count.extends += int(record.extends)
    return {style: dict(sorted(parts.items())) for style, parts in sorted(counts.items())}
