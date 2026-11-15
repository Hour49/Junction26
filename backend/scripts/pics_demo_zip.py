"""A demo upload for the plan edit followed on services pictures, from the DigitalHub models
(partner data: the ZIP goes under data/, never into git).

    uv run python scripts/pics_demo_zip.py <ifc_models dir> <out.zip> [--storey E00_OKRD]

One floor's heating and plumbing pictures drawn by the bench renderer (plan_picture) from the
hzg and san models, over the architecture model's walls, plus the other floor's heating picture
as a distractor; and the floor plan as a vector PDF (the only plan the no-keys backend edits)
drawn from the architecture model on the pictures' frame: the same origin and size in metres,
as the sheets of one drawing set share their sheet frame. The pictures are padded white to one
size so all the sheets are the same page in metres (pairing's "laid over page to page").
Names follow a sheet set: A-1xx plan, H-1xx heating, P-1xx plumbing, the floor in each name.
"""

import argparse
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import ifcopenshell
import numpy as np
from ifcopenshell.util.element import get_aggregate, get_container
from PIL import Image
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

sys.path[:0] = [str(Path(__file__).parents[1]), str(Path(__file__).parents[1] / "tests")]
from pdf_sheets import BLACK, SheetPdf  # noqa: E402
from swiss_walls import WALL  # noqa: E402
from test_vector_pdf import GREY  # noqa: E402

from app.adapters.ifc_model.plan_picture import (  # noqa: E402
    _shapes,  # pyright: ignore[reportPrivateUsage]
    draw_plans,
    read_plans,
)

PT_PER_M = 72 / 25.4 * 1000 / 100  # the plan PDF is at 1:100
ARC, HZG, SAN = (
    "rwth-digitalhub_digitalhub-fm-arc-v2.ifc",
    "rwth-digitalhub_digitalhub-fm-hzg-v2.ifc",
    "rwth-digitalhub_digitalhub-fm-san-v2.ifc",
)
NUMBERS = {"B01_OKRD": "100", "E00_OKRD": "101", "E01_OKRD": "102"}


def _polygons(geometry: Any) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    return [g for g in getattr(geometry, "geoms", []) if isinstance(g, Polygon)]


def _footprint(verts: np.ndarray, faces: np.ndarray) -> Any:
    tris = [Polygon(t) for t in verts[:, :2][faces] if Polygon(t).area > 1e-9]
    return unary_union(tris).buffer(0.002).buffer(-0.002)


def plan_pdf(arc: Path, storey: str, truth: dict[str, Any], size_px: tuple[int, int]) -> bytes:
    """The storey's rooms (IfcSpace footprints with name, number, area) and its cut walls, on
    the pictures' frame, swiss style (the style the no-keys vector reader edits)."""
    k = truth["px_per_m"]
    ox, oy = truth["origin_m"]
    sheet = SheetPdf(size_px[0] / k * PT_PER_M, size_px[1] / k * PT_PER_M)

    def at(p: tuple[float, float]) -> tuple[float, float]:
        return ((p[0] - ox) * PT_PER_M, (oy - p[1]) * PT_PER_M)

    model = ifcopenshell.open(str(arc))
    level = next(s for s in model.by_type("IfcBuildingStorey") if s.Name == storey)
    z0 = float(level.Elevation or 0.0)
    spaces = [
        s
        for s in model.by_type("IfcSpace")
        if (c := get_aggregate(s) or get_container(s)) and c.id() == level.id()
    ]
    rooms = 0
    for guid, verts, faces in _shapes(model, spaces):
        entity = model.by_guid(guid)
        shape = max(_polygons(_footprint(verts, faces)), key=lambda p: p.area, default=None)
        if shape is None or shape.area < 1.0:
            continue
        ring = [at(p) for p in shape.exterior.coords]
        sheet.path(ring, stroke=GREY, width=0.37, fill=(255, 255, 255))
        name = (entity.LongName or entity.Name or "").strip()
        # the swiss reader takes rooms numbered like 1.19 (swiss.NUMBER): 1-19 -> 1.19, 301 -> 3.01
        raw = (entity.Name or "").strip() if entity.LongName else ""
        number = raw.replace("-", ".") if "-" in raw else (f"{raw[0]}.{raw[1:]}" if raw else "")
        x, y = at(shape.representative_point().coords[0])
        lines = [t for t in (name, number, f"{shape.area:.2f} m²") if t]
        for n, line in enumerate(lines):
            sheet.text(line, x - 12, y - 6 + 8 * n)
        rooms += 1
    cut = z0 + 1.2
    walls = []
    for _, verts, faces in _shapes(model, list(model.by_type("IfcWall"))):
        z = verts[:, 2]
        if z.min() <= cut <= z.max():
            walls += _polygons(_footprint(verts, faces))
    for wall in walls:  # piece by piece: their union is a ring with holes
        sheet.path([at(p) for p in wall.exterior.coords], stroke=BLACK, width=0.99, fill=WALL)
    sheet.text("Massstab 1:100", sheet.width - 150, sheet.height - 20)
    print(f"plan: {rooms} rooms, {len(walls)} wall pieces", file=sys.stderr)
    return sheet.pdf()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("models", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--storey", default="E00_OKRD")
    parser.add_argument("--other", default="E01_OKRD")
    parser.add_argument("--dpi", type=int, default=100)
    args = parser.parse_args()
    arc = args.models / ARC
    wanted = {
        (args.storey, "heating"): "H",
        (args.storey, "plumbing"): "P",
        (args.other, "heating"): "H",
    }
    model_of = {"heating": HZG, "plumbing": SAN}  # each lane from its own model only
    sheets = [
        s
        for path in (args.models / HZG, args.models / SAN)
        for s in read_plans(path, arc)
        if (s.storey, s.discipline) in wanted and model_of[s.discipline] == path.name
    ]
    found = {(s.storey, s.discipline) for s in sheets}
    assert found == set(wanted), sorted(found)
    with tempfile.TemporaryDirectory() as tmp:
        pictures = draw_plans(sheets, Path(tmp), dpi=args.dpi)
        truths = {p: json.loads(p.with_suffix(".json").read_text()) for p in pictures}
        frames = {(t["storey"], tuple(t["origin_m"]), t["px_per_m"]) for t in truths.values()}
        print("frames:", sorted(frames), file=sys.stderr)
        here = [t for t in truths.values() if t["storey"] == args.storey]
        assert len({(tuple(t["origin_m"]), t["px_per_m"]) for t in here}) == 1, here
        size = (
            max(t["size_px"][0] for t in truths.values()),
            max(t["size_px"][1] for t in truths.values()),
        )
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            floor = args.storey.split("_")[0]
            archive.writestr(
                f"set/A-{NUMBERS[args.storey]} {floor} plan.pdf",
                plan_pdf(arc, args.storey, here[0], size),
            )
            for picture, truth in truths.items():
                image = Image.open(picture).convert("RGB")
                padded = Image.new("RGB", size, "white")
                padded.paste(image, (0, 0))
                letter = wanted[(truth["storey"], truth["discipline"])]
                name = (
                    f"set/{letter}-{NUMBERS[truth['storey']]} {truth['storey'].split('_')[0]} "
                    f"{truth['discipline']}.png"
                )
                data = io.BytesIO()
                padded.save(data, "PNG")
                archive.writestr(name, data.getvalue())
                print(name, image.size, "->", size, file=sys.stderr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(out.getvalue())
    print(args.out, len(out.getvalue()), file=sys.stderr)


if __name__ == "__main__":
    main()
