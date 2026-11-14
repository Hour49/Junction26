"""Bench pictures of an IFC services model: one plan picture per storey and discipline, with its
truth next to it (docs/specs/backend/discipline-pictures.md, "Benchmark", slice P3).

What is drawn, and what the truth is:

- The elements are facts_mep's (`mep_elements`), with its storey, discipline, type name,
  systems, size and length, so the truth is the fact sheet restricted to the picture. The
  plan geometry is the geometry kernel's, in world coordinates (metres).
- Terminals, equipment, valves and the rest: one symbol per legend label (the type name) at
  the centre of the element's plan bounding box. Fittings are not drawn (they are part of
  the runs). Segments: a line along the plan axis of the segment's body, coloured and dashed
  per system, with the size printed by runs longer than 2 m.
- Background: the walls of the building's architectural model whose height spans the cut
  (1.2 m above the storey), in light grey, when the two models share coordinates: a storey at
  the same elevation and the plans' boxes overlapping.
- A legend (symbol + label, grouped by system, then the line of each system), a scale bar,
  the ratio, and a title naming the storey and the discipline.
- An element the kernel cannot build is not drawn and is left out of the truth (`undrawn`).

Variants (the spec's): `clean`; `scan`, greyscaled, rotated up to 1.5°, blurred, salted and
saved as JPEG quality 60; `photo`, a perspective warp of up to 5% of the side and uneven light,
JPEG quality 85; `no-legend` and `no-scale`, clean without the legend or the scale bar. The
truth's points move with the picture. A seed fixes every random choice, so the same
arguments give the same bytes. Structural plans draw columns, footings and piles as symbols.
"""

import json
import math
import re
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import ifcopenshell
import ifcopenshell.geom
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.adapters.ifc_model.facts_mep import MepElement, _element, mep_elements
from app.adapters.ifc_model.objects import _unit_scales

Variant = Literal["clean", "scan", "photo", "no-legend", "no-scale"]
VARIANTS: tuple[Variant, ...] = ("clean", "scan", "photo", "no-legend", "no-scale")
STRUCTURAL = ("IfcColumn", "IfcFooting", "IfcPile")  # drawn as symbols on a structural plan
RATIOS = (50, 100, 200, 500)  # the first whose plan fits PAPER_M on paper
PAPER_M = 0.8  # the plan's longer side on paper, at most: an A1 sheet less its margins
MARGIN_M = 2.0  # around the plan, in the building's metres
CUT_M = 1.2  # walls are cut this high above the storey
SIZE_PRINTED_M = 2.0  # runs longer than this print their size
SAME_ELEVATION_M = 0.05
OVERLAP = 0.5  # of the services plan's box that the walls' box must cover
SYMBOL_MM, TEXT_MM, LEGEND_MM = 4.0, 2.5, 110.0  # on paper
SHAPES = ("circle", "square", "triangle", "diamond", "cross", "hexagon", "x", "bar")
FILLS = ("outline", "solid", "dot")
COLOURS = ("#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b", "#e377c2", "#17becf")
DASHES: tuple[tuple[int, int] | None, ...] = (None, (14, 6), (4, 4))
NOT_SYMBOLS = ("flow_segment", "flow_fitting")  # groups drawn as lines, or not at all


@dataclass(frozen=True)
class _Placed:
    element: MepElement
    a: tuple[float, float]  # plan points in metres: a segment's two ends, else a == b
    b: tuple[float, float]


@dataclass(frozen=True)
class PlanSheet:
    """What one picture draws: a storey's elements of one discipline, and its background."""

    model: str
    storey: str
    discipline: str
    drawn: list[_Placed]
    walls: list[np.ndarray]  # plan triangles (m, 3, 2) of the walls cut at this storey
    background: dict[str, Any] | None  # what the truth says of the walls
    undrawn: int  # elements the geometry kernel could not build


def render_model(
    model_path: Path,
    out: Path,
    *,
    background: Path | None = None,
    dpi: int = 150,
    variant: Variant = "clean",
    seed: int = 0,
) -> list[Path]:
    """`read_plans` and `draw_plans` in one: the pictures of one model in one look."""
    return draw_plans(read_plans(model_path, background), out, dpi=dpi, variant=variant, seed=seed)


def read_plans(model_path: Path, background: Path | None = None) -> list[PlanSheet]:
    """The plan sheets of a model, one per storey and discipline that has something to draw:
    the slow part (the geometry kernel), done once for every look `draw_plans` draws."""
    model = _open(model_path)
    scale = _unit_scales(model)["LENGTHUNIT"]
    elements = [e for e in mep_elements(model) if e.discipline != "other"]
    elements += [
        replace(_element(entity, scale), discipline="structural")
        for class_ in STRUCTURAL
        for entity in model.by_type(class_)
    ]
    elements = [e for e in elements if e.storey]
    placed = _place(model, elements)
    elevation = _elevations(model)
    walls = _walls(background) if background is not None else None
    groups: dict[tuple[str, str], list[_Placed]] = defaultdict(list)
    for e in elements:
        if e.guid in placed:
            groups[(e.storey or "", e.discipline)].append(placed[e.guid])
    undrawn = Counter((e.storey, e.discipline) for e in elements if e.guid not in placed)
    sheets = []
    for (storey, discipline), drawn in sorted(groups.items()):
        if all(d.element.group == "flow_fitting" for d in drawn):
            continue  # nothing to draw
        cut, note = _background(walls, elevation.get(storey), drawn)
        sheets.append(
            PlanSheet(
                model_path.stem, storey, discipline, drawn, cut, note, undrawn[(storey, discipline)]
            )
        )
    return sheets


def draw_plans(
    sheets: list[PlanSheet], out: Path, *, dpi: int = 150, variant: Variant = "clean", seed: int = 0
) -> list[Path]:
    """Writes `<model>--<storey>--<discipline>.png` (`.jpg` for `scan` and `photo`) and its
    truth `.json` into `out` per sheet. Returns the pictures. Each picture's random choices
    come from `seed` and its name, so a rebuild gives the same bytes."""
    out.mkdir(parents=True, exist_ok=True)
    pictures = []
    for sheet in sheets:
        name = f"{sheet.model}--{_slug(sheet.storey)}--{sheet.discipline}"
        image, truth = _draw(
            sheet.drawn,
            sheet.walls,
            dpi,
            variant != "no-legend",
            variant != "no-scale",
            f"{sheet.storey} — {sheet.discipline}",
        )
        rng = np.random.default_rng([seed, zlib.crc32(name.encode())])
        if variant == "scan":
            image, truth = _scan(image, truth, rng)
        elif variant == "photo":
            image, truth = _photo(image, truth, rng)
        truth["size_px"] = list(image.size)
        jpeg = variant in ("scan", "photo")
        picture = out / f"{name}.{'jpg' if jpeg else 'png'}"
        image.save(picture, quality=60 if variant == "scan" else 85) if jpeg else image.save(
            picture
        )
        truth |= {
            "picture": picture.name,
            "model": sheet.model,
            "storey": sheet.storey,
            "discipline": sheet.discipline,
            "dpi": dpi,
            "variant": variant,
            "seed": seed,
            "background": sheet.background,
            "undrawn": sheet.undrawn,
        }
        picture.with_suffix(".json").write_text(json.dumps(truth, indent=1, ensure_ascii=False))
        pictures.append(picture)
    return pictures


def _open(path: Path) -> Any:
    opened: Any = ifcopenshell.open  # lazy: a fraction of the memory on a large model (objects.py)
    return opened(str(path), lazy=True)


def _place(model: Any, elements: list[MepElement]) -> dict[str, _Placed]:
    """The plan geometry of each element the kernel can build."""
    by_guid = {e.guid: e for e in elements}
    entities = [model.by_guid(e.guid) for e in elements]
    placed: dict[str, _Placed] = {}
    for guid, verts, _ in _shapes(model, entities):
        element = by_guid[guid]
        xy = verts[:, :2]
        if element.length_m is None:
            centre = tuple((xy.min(axis=0) + xy.max(axis=0)) / 2)
            placed[guid] = _Placed(element, centre, centre)
            continue
        mean = xy.mean(axis=0)
        spread = xy - mean
        if np.allclose(spread, 0):
            placed[guid] = _Placed(element, tuple(mean), tuple(mean))
            continue
        axis = np.linalg.eigh(spread.T @ spread)[1][:, -1]  # the direction of most spread
        along = spread @ axis
        a, b = mean + axis * along.min(), mean + axis * along.max()
        placed[guid] = _Placed(element, (float(a[0]), float(a[1])), (float(b[0]), float(b[1])))
    return placed


def _shapes(model: Any, entities: list[Any]) -> Any:
    """(GlobalId, world vertices in metres (n, 3), triangles as vertex indices (m, 3)) per
    entity the kernel builds."""
    if not entities:
        return
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("disable-opening-subtractions", True)
    iterator = ifcopenshell.geom.iterator(settings, model, 1, include=entities)
    if not iterator.initialize():
        return
    while True:
        shape: Any = iterator.get()
        verts = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
        if len(verts):
            yield shape.guid, verts, np.asarray(shape.geometry.faces, dtype=int).reshape(-1, 3)
        if not iterator.next():
            return


def _elevations(model: Any) -> dict[str, float]:
    scale = _unit_scales(model)["LENGTHUNIT"]
    return {
        s.Name: float(s.Elevation or 0.0) * scale
        for s in model.by_type("IfcBuildingStorey")
        if s.Name
    }


@dataclass(frozen=True)
class _Walls:
    model: str
    elevations: dict[str, float]
    pieces: list[tuple[float, float, np.ndarray]]  # z min, z max, plan triangles (m, 3, 2)


def _walls(path: Path) -> _Walls:
    model = _open(path)
    pieces = []
    for _, verts, faces in _shapes(model, list(model.by_type("IfcWall"))):
        z = verts[:, 2]
        pieces.append((float(z.min()), float(z.max()), verts[:, :2][faces]))
    return _Walls(path.stem, _elevations(model), pieces)


def _background(
    walls: _Walls | None, elevation: float | None, drawn: list[_Placed]
) -> tuple[list[np.ndarray], dict[str, Any] | None]:
    """The wall outlines cut at this storey, and what the truth says of them."""
    if walls is None or elevation is None:
        return [], None
    storey = next(
        (n for n, z in walls.elevations.items() if abs(z - elevation) <= SAME_ELEVATION_M), None
    )
    z = elevation + CUT_M
    cut = [xy for low, high, xy in walls.pieces if low <= z <= high]
    if storey is None or not cut:
        return [], {"model": walls.model, "storey": None, "why": "no storey at this elevation"}
    mine = _box(np.array([p for d in drawn for p in (d.a, d.b)]))
    theirs = _box(np.concatenate(cut).reshape(-1, 2))
    width = min(mine[2], theirs[2]) - max(mine[0], theirs[0])
    height = min(mine[3], theirs[3]) - max(mine[1], theirs[1])
    area = max(mine[2] - mine[0], 1e-6) * max(mine[3] - mine[1], 1e-6)
    if width <= 0 or height <= 0 or width * height < OVERLAP * area:
        return [], {"model": walls.model, "storey": storey, "why": "plans do not overlap"}
    return cut, {"model": walls.model, "storey": storey, "why": None}


def _box(points: np.ndarray) -> tuple[float, float, float, float]:
    return (*points.min(axis=0).tolist(), *points.max(axis=0).tolist())


def _draw(
    drawn: list[_Placed],
    walls: list[np.ndarray],
    dpi: int,
    legend: bool,
    scale_bar: bool,
    title: str,
) -> tuple[Image.Image, dict[str, Any]]:
    points = np.array([p for d in drawn for p in (d.a, d.b)])
    x_min, y_min, x_max, y_max = _box(points)
    if walls:  # the building, not only this storey's services
        wx_min, wy_min, wx_max, wy_max = _box(np.concatenate(walls).reshape(-1, 2))
        x_min, y_min = min(x_min, wx_min), min(y_min, wy_min)
        x_max, y_max = max(x_max, wx_max), max(y_max, wy_max)
    side = max(x_max - x_min, y_max - y_min)
    ratio = next((r for r in RATIOS if side / r <= PAPER_M), RATIOS[-1])
    dots_per_m = dpi / 0.0254  # on paper
    k = dots_per_m / ratio  # pixels per metre of building
    origin = (x_min - MARGIN_M, y_max + MARGIN_M)

    def px(p: tuple[float, float]) -> tuple[float, float]:
        return ((p[0] - origin[0]) * k, (origin[1] - p[1]) * k)

    mm = dots_per_m / 1000
    font = _font(max(8, round(TEXT_MM * mm)))
    line = round(TEXT_MM * mm * 1.8)
    symbols = [d for d in drawn if d.element.group not in NOT_SYMBOLS]
    labels = sorted({(d.element.kind, d.element.type_name) for d in symbols})
    glyph = {name: i for i, (_, name) in enumerate(labels)}
    systems = sorted({d.element.systems[0] if d.element.systems else "" for d in drawn})
    style = {s: i for i, s in enumerate(systems)}
    rows = len(glyph) + 2 * len(systems) + 2 if legend else 0
    plan_w = math.ceil((x_max - x_min + 2 * MARGIN_M) * k)
    plan_h = math.ceil((y_max - y_min + 2 * MARGIN_M) * k)
    texts = [*glyph, *systems]
    widest = max((font.getlength(t) for t in texts), default=0) + 6 * line
    legend_w = max(round(LEGEND_MM * mm), math.ceil(widest)) if legend else 0
    image = Image.new("RGB", (plan_w + legend_w, max(plan_h, rows * line + 2 * line)), "white")
    pen = ImageDraw.Draw(image)
    for triangles in walls:
        for tri in triangles.reshape(-1, 3, 2):
            pen.polygon([px(tuple(v)) for v in tri], fill="#d9d9d9")
    runs: dict[tuple[str | None, str | None], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for d in drawn:
        e = d.element
        if e.length_m is None:
            continue
        system = e.systems[0] if e.systems else ""
        _line(pen, px(d.a), px(d.b), style[system], max(2, round(0.35 * mm)))
        plan_m = math.dist(d.a, d.b)
        if plan_m > SIZE_PRINTED_M and e.size:
            mid = px(((d.a[0] + d.b[0]) / 2, (d.a[1] + d.b[1]) / 2))
            pen.text((mid[0] + 3, mid[1] + 3), e.size, fill="black", font=font)
        for s in e.systems or (None,):
            runs[(s, e.size)][0] += e.length_m
            runs[(s, e.size)][1] += plan_m
    size = SYMBOL_MM * mm
    spots = []
    for d in symbols:
        x, y = px(d.a)
        _glyph(pen, (x, y), glyph[d.element.type_name], size, font)
        spots.append(
            {
                "label": d.element.type_name,
                "kind": d.element.kind,
                "system": d.element.systems[0] if d.element.systems else None,
                "x": round(x, 2),
                "y": round(y, 2),
            }
        )
    entries = []
    if legend:
        x0, y = plan_w + line // 2, line
        found: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
        for d in symbols:
            e = d.element
            found[(e.kind, e.type_name)][e.systems[0] if e.systems else ""] += 1
        by_system: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for label, among in found.items():  # one entry per label, under its usual system
            by_system[among.most_common(1)[0][0]].append(label)
        for system in systems:
            if system and by_system[system]:  # a heading for its symbols
                pen.text((x0, y), system, fill="black", font=font)
                y += line
            if any(r[0] == system or (r[0] is None and not system) for r in runs):
                _line(pen, (x0, y + line / 2), (x0 + 4 * line, y + line / 2), style[system], 3)
                pen.text((x0 + 5 * line, y), system or "pipes, ducts", fill="black", font=font)
                y += line
            for kind, name in sorted(by_system[system]):
                _glyph(pen, (x0 + line, y + line / 2), glyph[name], size, font)
                pen.text((x0 + 3 * line, y), name, fill="black", font=font)
                entries.append({"label": name, "kind": kind, "system": system or None})
                y += line
    pen.text((line, line / 2), title, fill="black", font=font)
    if scale_bar:
        bar = 5.0 if ratio <= 100 else 10.0
        x, y = line, plan_h - line * 1.5
        pen.rectangle((x, y, x + bar * k, y + line / 3), fill="black")
        pen.text(
            (x + bar * k + line / 2, y - line / 3),
            f"{bar:g} m   1:{ratio}",
            fill="black",
            font=font,
        )
    counts = Counter(s["label"] for s in spots)
    truth = {
        "ratio": ratio if scale_bar else None,
        "px_per_m": round(k, 6),
        "origin_m": [round(origin[0], 6), round(origin[1], 6)],
        "size_px": list(image.size),
        "legend": entries,
        "symbols": spots,
        "counts": dict(sorted(counts.items())),
        "runs": [
            {"system": s, "size": z, "length_m": round(m, 3), "plan_m": round(p, 3)}
            for (s, z), (m, p) in sorted(runs.items(), key=lambda r: (str(r[0][0]), str(r[0][1])))
        ],
        "system_lengths_m": {
            s: round(sum(m for (t, _), (m, _) in runs.items() if t == s), 3)
            for s in sorted({s for s, _ in runs if s})
        },
    }
    return image, truth


def _font(size: int) -> Any:
    try:  # a font with "ø" and "²", which sizes print; Pillow's own lacks them
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def _line(
    pen: ImageDraw.ImageDraw, a: tuple[float, float], b: tuple[float, float], i: int, w: int
) -> None:
    colour, dash = COLOURS[i % len(COLOURS)], DASHES[i // len(COLOURS) % len(DASHES)]
    if dash is None:
        pen.line([a, b], fill=colour, width=w)
        return
    length = math.dist(a, b)
    on, off = dash
    for start in np.arange(0, length, on + off):
        t0, t1 = start / length, min(start + on, length) / length
        pen.line([_at(a, b, t0), _at(a, b, t1)], fill=colour, width=w)


def _at(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _glyph(
    pen: ImageDraw.ImageDraw, at: tuple[float, float], i: int, size: float, font: Any
) -> None:
    """Symbol `i`: a shape, a fill, and past len(SHAPES) * len(FILLS) a number beside it."""
    shape, fill = SHAPES[i % len(SHAPES)], FILLS[i // len(SHAPES) % len(FILLS)]
    x, y, r = at[0], at[1], size / 2
    solid = "black" if fill == "solid" else None
    w = max(2, round(size / 10))
    corners = {
        "square": [(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r)],
        "triangle": [(x, y - r), (x + r, y + r), (x - r, y + r)],
        "diamond": [(x, y - r), (x + r, y), (x, y + r), (x - r, y)],
        "hexagon": [(x + r * math.cos(a), y + r * math.sin(a)) for a in np.arange(6) * math.pi / 3],
    }
    if shape == "circle":
        pen.ellipse((x - r, y - r, x + r, y + r), outline="black", fill=solid, width=w)
    elif shape in corners:
        pen.polygon(corners[shape], outline="black", fill=solid, width=w)
    elif shape == "cross":
        pen.line([(x - r, y), (x + r, y)], fill="black", width=w * (2 if solid else 1))
        pen.line([(x, y - r), (x, y + r)], fill="black", width=w * (2 if solid else 1))
    elif shape == "x":
        pen.line([(x - r, y - r), (x + r, y + r)], fill="black", width=w * (2 if solid else 1))
        pen.line([(x - r, y + r), (x + r, y - r)], fill="black", width=w * (2 if solid else 1))
    else:  # bar
        pen.rectangle((x - r, y - r / 3, x + r, y + r / 3), outline="black", fill=solid, width=w)
    if fill == "dot":
        pen.ellipse((x - r / 4, y - r / 4, x + r / 4, y + r / 4), fill="black")
    if i >= len(SHAPES) * len(FILLS):
        pen.text(
            (x + r + 2, y - r), str(i // (len(SHAPES) * len(FILLS)) + 1), fill="black", font=font
        )


def _scan(
    image: Image.Image, truth: dict[str, Any], rng: np.random.Generator
) -> tuple[Image.Image, dict]:
    angle = float(rng.uniform(-1.5, 1.5))
    grey = image.convert("L").rotate(
        angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255
    )  # expanded: the corners (title, legend) stay on the page
    pixels = np.array(grey.filter(ImageFilter.GaussianBlur(1)))
    salt = rng.random(pixels.shape) < 0.002
    pixels[salt] = rng.choice(np.array([0, 255], dtype=np.uint8), size=int(salt.sum()))
    cx, cy = image.width / 2, image.height / 2
    nx, ny = grey.width / 2, grey.height / 2  # the centre stays the centre
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    rotation = np.array(
        [[cos, sin, nx - cx * cos - cy * sin], [-sin, cos, ny + cx * sin - cy * cos]]
    )
    moved = _moved(truth, np.vstack([rotation, [0, 0, 1]]))
    return Image.fromarray(pixels), moved | {"rotation_deg": round(angle, 4)}


def _photo(
    image: Image.Image, truth: dict[str, Any], rng: np.random.Generator
) -> tuple[Image.Image, dict]:
    """The page photographed: its corners moved in by up to 5% of the side, the light falling
    off by up to 30% across it."""
    w, h = image.size
    page = np.array([(0, 0), (w, 0), (w, h), (0, h)], dtype=float)
    inward = np.array([(1, 1), (-1, 1), (-1, -1), (1, -1)])  # nothing leaves the frame
    photo = page + inward * rng.uniform(0, 0.05, (4, 2)) * (w, h)
    back = _homography(photo, page)  # PIL asks, per pixel of the photo, where on the page
    warped = image.transform(
        (w, h),
        Image.Transform.PERSPECTIVE,
        tuple((back / back[2, 2]).flatten()[:8]),
        Image.Resampling.BICUBIC,
        fillcolor=(90, 90, 90),
    )
    turn = float(rng.uniform(0, 2 * math.pi))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    ramp = xs * math.cos(turn) + ys * math.sin(turn)
    ramp = (ramp - ramp.min()) / max(float(np.ptp(ramp)), 1.0)
    lit = np.asarray(warped, dtype=np.float32) * (1 - 0.3 * ramp)[..., None]
    moved = _moved(truth, _homography(page, photo))
    lit_image = Image.fromarray(lit.round().astype(np.uint8))
    return lit_image, moved | {"corners_px": photo.round(2).tolist()}


def _homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """The 3x3 projective map taking the four points `src` to `dst`."""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(src, dst, strict=True):
        rows += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        rhs += [u, v]
    return np.append(np.linalg.solve(np.array(rows), np.array(rhs)), 1.0).reshape(3, 3)


def _moved(truth: dict[str, Any], to: np.ndarray) -> dict[str, Any]:
    """The truth with its symbols' points mapped through the 3x3 matrix `to`."""
    symbols = []
    for s in truth["symbols"]:
        x, y, z = to @ (s["x"], s["y"], 1.0)
        symbols.append(s | {"x": round(float(x / z), 2), "y": round(float(y / z), 2)})
    return truth | {"symbols": symbols}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "storey"
