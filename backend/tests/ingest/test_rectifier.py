"""RECTIFIER=r3 (app/adapters/rectifier): the paper border first, else UVDoc unless the plan
fills the photo. On synthetic photos only: the plan is drawn here and photographed by the
sample archive's phone_photo (on a table, at an angle, unevenly lit, slightly out of focus)."""

import io
import zipfile
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image, ImageDraw

import app.composition as composition
from app.adapters.rectifier import CLASSICAL, LEARNED, R3Rectifier, fills_frame
from app.adapters.rectifier.classical import Image as Pixels
from app.adapters.rectifier.uvdoc import OnnxUvdoc
from app.composition import UVDOC_MODEL, build_ingest
from app.core.errors import InvalidInputError
from app.settings import Settings
from scripts.make_sample_archive import PHOTO_CORNERS, PHOTO_SIZE, phone_photo

PLAN_SIZE = (1200, 850)
MARK = (500, 300, 640, 420)  # a dark square on the paper, seen straight on


def plan() -> Image.Image:
    image = Image.new("RGB", PLAN_SIZE, "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 1120, 770), outline="black", width=14)  # outer walls
    draw.line((600, 80, 600, 300), fill="black", width=8)
    draw.line((80, 450, 480, 450), fill="black", width=8)
    draw.rectangle(MARK, fill="black")
    return image


def jpeg(image: Image.Image, camera: bool = True) -> bytes:
    exif = Image.Exif()
    if camera:
        exif[0x010F] = "SyntheticPhone"
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=92, exif=exif)
    return buffer.getvalue()


def dark_centre(image: Image.Image) -> tuple[float, float]:
    """The centre of the dark square, as fractions of the image (the largest dark blob)."""
    grey = np.asarray(image.convert("L"))
    height, width = grey.shape
    ys, xs = np.nonzero(grey < 80)
    inside = (xs > 0.3 * width) & (xs < 0.7 * width) & (ys > 0.2 * height) & (ys < 0.65 * height)
    return float(xs[inside].mean() / width), float(ys[inside].mean() / height)


class Grid:
    """A dewarper whose page outline is the photo inset by `inset` on every side."""

    def __init__(self, inset: float) -> None:
        self.inset, self.calls = inset, 0

    def grid(self, photo: Pixels) -> NDArray[np.float64]:
        self.calls += 1
        height, width = photo.shape[:2]
        xs = np.linspace(self.inset * (width - 1), (1 - self.inset) * (width - 1), 31)
        ys = np.linspace(self.inset * (height - 1), (1 - self.inset) * (height - 1), 45)
        return np.stack(np.meshgrid(xs, ys), -1)


def test_the_paper_on_a_table_is_found_by_its_border_and_seen_straight_on() -> None:
    dewarper = Grid(0.1)
    found = R3Rectifier(dewarper).rectify(jpeg(phone_photo(plan())), "photo_plan")
    assert found is not None and found.method == CLASSICAL
    assert dewarper.calls == 0
    width, height = PHOTO_SIZE
    true = [(x / width, y / height) for x, y in PHOTO_CORNERS]
    for (x, y), (tx, ty) in zip(found.quad, true, strict=True):
        assert abs(x - tx) < 0.01 and abs(y - ty) < 0.01
    with Image.open(io.BytesIO(found.data)) as flat:
        assert flat.format == "JPEG" and flat.size == (found.width, found.height)
        assert found.width / found.height == pytest.approx(PLAN_SIZE[0] / PLAN_SIZE[1], rel=0.05)
        x, y = dark_centre(flat)
    mark_x, mark_y = (MARK[0] + MARK[2]) / 2 / PLAN_SIZE[0], (MARK[1] + MARK[3]) / 2 / PLAN_SIZE[1]
    assert abs(x - mark_x) < 0.01 and abs(y - mark_y) < 0.01


def test_only_a_camera_photo_of_a_drawing_is_rectified() -> None:
    photo = jpeg(phone_photo(plan()))
    for kind in ("png_plan", "jpeg_plan", "photo"):
        assert R3Rectifier(Grid(0.1)).rectify(photo, kind) is None


def test_without_a_paper_border_the_learned_dewarp_is_used() -> None:
    """The plan fills the photo, so no border is found; the dewarper's outline is inside it."""
    found = R3Rectifier(Grid(0.1)).rectify(jpeg(plan()), "photo_plan")
    assert found is not None and found.method == LEARNED
    assert found.quad[0] == pytest.approx((0.1, 0.1), abs=0.002)
    assert found.quad[2] == pytest.approx((0.9, 0.9), abs=0.002)
    assert (found.width, found.height) == pytest.approx((0.8 * 1199, 0.8 * 849), abs=2)


def test_a_plan_that_fills_the_photo_is_kept_when_the_dewarp_would_only_crop_it() -> None:
    assert R3Rectifier(Grid(0.01)).rectify(jpeg(plan()), "photo_plan") is None


def test_outline_at_six_percent_of_the_diagonal_fills_the_frame() -> None:
    """Demo photo 042: UVDoc's outline at 5.5% of the diagonal from the corners cut its caption
    (photo raised the guard to 6.5%; prototypes/photo/tests/test_phone.py, same case)."""
    photo: Pixels = np.zeros((1000, 750, 3), np.uint8)
    off = 0.06 * np.hypot(1000, 750) / np.sqrt(2)  # each corner 6% of the diagonal inward
    corners = np.array([[off, off], [749 - off, off], [749 - off, 999 - off], [off, 999 - off]])
    assert fills_frame(photo, corners)
    far = np.array([[90, 90], [660, 90], [660, 910], [90, 910]], float)  # ~10%: a sheet on a wall
    assert not fills_frame(photo, far)


@pytest.mark.skipif(not UVDOC_MODEL.is_file(), reason="data/models/photo/uvdoc.onnx is local only")
def test_the_onnx_uvdoc_outlines_the_paper_of_a_photo() -> None:
    """The real model (exported by scripts/export_uvdoc_onnx.py) on the synthetic photo: its
    outline lies near the paper's corners (UVDoc drifts 1-2% on synthetic photos)."""
    photo = np.asarray(phone_photo(plan()), np.uint8)
    grid = OnnxUvdoc(UVDOC_MODEL).grid(photo)
    assert grid.shape == (45, 31, 2)
    corners = np.array([grid[0, 0], grid[0, -1], grid[-1, -1], grid[-1, 0]])
    error = np.linalg.norm(corners - np.array(PHOTO_CORNERS), axis=1).mean()
    assert error < 0.05 * np.hypot(*PHOTO_SIZE)


def test_rectifier_r3_without_its_model_fails_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(composition, "UVDOC_MODEL", tmp_path / "missing.onnx")
    settings = Settings(_env_file=None, rectifier="r3")  # pyright: ignore[reportCallIssue]
    with pytest.raises(InvalidInputError, match=r"^RECTIFIER=r3: .*missing\.onnx is missing"):
        build_ingest(settings, tmp_path / "projects", background=False)


def test_a_photo_ingested_without_a_rectifier_is_read_again_with_r3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rectifier makes the frame every box is in, so it is part of the cache key."""
    monkeypatch.setattr(composition, "OnnxUvdoc", lambda model: Grid(0.1))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("photos/plan.jpg", jpeg(phone_photo(plan())))
    upload, root = buffer.getvalue(), tmp_path / "projects"
    states = []
    for name in ("none", "r3"):
        settings = Settings(_env_file=None, rectifier=name)  # pyright: ignore[reportCallIssue]
        ingest = build_ingest(settings, root, background=False)
        (file,) = ingest.status(ingest.start("upload.zip", upload)).files
        assert file.kind == "photo_plan" and file.normalised is not None
        states.append((file.reused, file.normalised.rectified, file.normalised.rectifier))
        ingest.close()
    assert states == [(False, False, None), (False, True, CLASSICAL)]
