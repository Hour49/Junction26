"""A plan drawn on a transparent background (a PNG whose paper is alpha 0 over black, as a CAD
export or an image editor writes it). Pillow's convert("RGB") drops the alpha and shows the
black under it: the probe saw an all-black image and set the plan aside as "no sharp line ...
100% ink" (QA r12 upload sweep), and the viewer served a black page. Both now put it on white,
as the raster detector's `open_rgb` already did."""

import io
from collections.abc import Callable

import numpy as np
import pytest
from PIL import Image

from app.adapters.archive import FileProbe
from app.adapters.eight_bit import on_white
from app.adapters.page_render import render_png, render_upload
from app.core.ingest.model import SheetFile
from scripts.make_sample_archive import png_bytes, raster_plan


def clear_paper(mode: str) -> Image.Image:
    """The sample plan as black ink whose paper is fully transparent (black under it)."""
    grey = np.asarray(raster_plan().convert("L"), np.uint8)
    alpha = 255 - grey
    if mode == "LA":
        return Image.fromarray(np.dstack([np.zeros_like(grey), alpha]), "LA")
    black = np.zeros_like(grey)
    return Image.fromarray(np.dstack([black, black, black, alpha]), "RGBA")


def keyed() -> Image.Image:
    """A palette PNG whose paper colour (index 0, black) is marked transparent (tRNS)."""
    dark = np.asarray(raster_plan().convert("L"), np.uint8) < 128
    keyed = Image.fromarray(dark.astype(np.uint8), "P")  # 0 paper, 1 ink
    keyed.putpalette([0, 0, 0, 0, 0, 0])  # both black: only the key tells them apart
    keyed.info["transparency"] = 0
    return keyed


@pytest.mark.parametrize("make", [lambda: clear_paper("RGBA"), lambda: clear_paper("LA"), keyed])
def test_a_plan_on_a_transparent_background_is_a_plan(make: Callable[[], Image.Image]) -> None:
    found = FileProbe().probe(png_bytes(make()))
    assert found.kind == "png_plan", found.did


def test_the_probe_reads_a_transparent_plan_as_the_same_plan_on_white() -> None:
    plan = clear_paper("RGBA")
    assert (
        FileProbe().probe(png_bytes(plan)).kind == FileProbe().probe(png_bytes(on_white(plan))).kind
    )


def mean_grey(png: bytes) -> float:
    with Image.open(io.BytesIO(png)) as image:
        return float(np.asarray(image.convert("L")).mean())


def test_the_viewer_shows_a_transparent_plan_on_white() -> None:
    data = png_bytes(clear_paper("RGBA"))
    sheet = SheetFile(drawing_id="d", path="plan.png", kind="png", data=data)
    assert mean_grey(render_png(sheet, 1, 400)) > 200  # paper white, not black
    assert mean_grey(render_upload(data, "png_plan", 400)) > 200


def test_on_white_keeps_an_opaque_image_as_it_is() -> None:
    plan = raster_plan().convert("RGB")
    assert on_white(plan) is plan
    grey = plan.convert("L")
    assert on_white(grey) is grey
