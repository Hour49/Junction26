# /// script
# requires-python = ">=3.13"
# dependencies = ["ezdxf==1.4.5", "pypdfium2==5.15.2", "shapely==2.2.0", "pillow==13.0.0"]
# ///
"""Extraction gold (extraction_v1) for swiss_dwellings, built from the DXF of each floor plan.

For every swiss PDF that has questions it writes `<out>/<stem>.json` (frame: the PDF page, points)
and `<out>/<stem>.png.json` (frame: the PNG, pixels; the PNG is the same page, so fractions are
identical). Truth is the DXF drawn into the page frame: the DXF (metres) is fitted to the PDF page
by matching room outlines by room number (scale from the title block, translation by least
squares, residual reported in notes). The PDF is read only for that fit and for the room fill
(grey 228 = outdoor, 243 = lifts/stairs/shafts), which the DXF does not carry.
Elements (from DXF layers): door = 5-point DOOR polyline (one per opening, swing leaves/arcs are not
counted); window = closed 4-point WINDOW rectangle; bathtub = 69-point FIXTURE polyline; shower =
5-point FIXTURE polyline; toilet = 48-point FIXTURE polyline with a 2-point FIXTURE line (tank) within 8 cm; sink = the other 48-point FIXTURE polylines. Kitchen blocks, burners etc. are not listed.
Rooms: ROOM_OUTLINE polygons that carry a number text; `area_m2` = outline minus nested outlines;
type from the label (de/fr/it vocabulary), `outdoor` for outdoor names or fill 228, `shaft` for
lift/stair names or unnamed fill 243 (`attrs.fill` keeps 243 for the apartment rule). Apartments =
the "Whg./App. X" labels; a room belongs to the unit outline that holds the label's room.
Scale: `scale.m_per_unit` = metres per pt (PDF) or per pixel (PNG = pt scale x page width / PNG
width) from the title-block text 1:100 / 1:200 on an A3 page.
The rule check (printed at the end of every run): the dataset's counting rules applied to the written JSON only must
reproduce every swiss answer (counts, label counts, room, label, floor and apartment areas).
Split (dev/eval) comes from `<split>/manifest.json` eval_groups. Eval gold is for milestone scoring,
never for tuning. Licence: swiss_dwellings is CC BY 4.0 (Archilyse AG); credit goes in pictures.
Run: uv run prototypes/extraction-gold/swiss_gold.py --dataset <root> --split <dir> --out <dir>
     [--overlays <dir>] (draws 6 pages)
"""

import argparse
import ctypes
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from pypdfium2 import raw
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

OUTDOOR_NAMES = {
    "Balkon", "Balcon", "Balcone", "Loggia", "Terrasse", "Terrazza", "Sitzplatz", "Garten",
    "Patio", "Arkade", "Jardin d'hiver", "Wintergarten", "Giardino d'inverno",
}  # fmt: skip
SHAFT_NAMES = {
    "Lift",
    "Ascenseur",
    "Ascensore",
    "Treppenhaus",
    "Cage d'escalier",
    "Vano scala",
}
BALCONY_NAMES = {"Balkon", "Balcon", "Balcone"}
ROOM_TYPES = {
    "kitchen": {"Küche", "Cuisine", "Cucina", "Küche/Essen"},
    "bathroom": {"Bad", "Bain", "Bagno"},
    "bedroom": {
        "Schlafzimmer", "Chambre à coucher", "Camera da letto", "Zimmer", "Pièce", "Stanza",
    },
    "living": {
        "Wohnen", "Wohnen/Essen", "Séjour", "Séjour/repas", "Soggiorno", "Soggiorno/pranzo",
        "Essen", "Repas", "Pranzo",
    },
    "hall": {"Korridor", "Couloir", "Corridoio", "Halle", "Hall", "Eingangshalle"},
    "storage": {
        "Reduit", "Réduit", "Ripostiglio", "Kellerabteil", "Vano cantina", "Compartiment cave",
    },
}  # fmt: skip
ROOM_STROKE, ROOM_WIDTH = (138, 138, 138), 0.37
AREA_TEXT = re.compile(r"(\d+[.,]\d+)\s*m²")
NUMBER = re.compile(r"[A-Z]*\d+\.\d+")
UNIT_LABEL = re.compile(r"^(?:Whg|Wohnung|App|Appt|Appartement|Alloggio)\.?\s+([A-Z])$")
APT_Q = re.compile(r"(?:apartment|Wohnung|appartement|appartamento) ([A-Z])\b")
ROOM_Q = re.compile(r"(?:room|Raum|salle|pièce|locale|local) ([A-Z]*\d+\.\d+)")
LABEL_Q = re.compile(
    r"[«'] *(.+?) *[»'](?!.*[»'])"
)  # last quote closes: names may hold '
COUNT_Q = [  # first match wins; keys are element classes or special names
    ("apartment", r"apartments|Wohnungen|appartements|appartamenti"),
    ("door", r"doors|Türen|portes|porte "),
    ("window", r"windows|Fenster|fenêtres|finestre"),
    ("toilet", r"toilets|WCs|\bWC\b"),
    ("sink", r"washbasins|Lavabos|lavabos|lavabi"),
    ("bathtub", r"bathtubs|Badewannen|baignoires|vasche"),
    ("shower", r"showers|Duschen|douches|docce"),
]
TANK_GAP = 0.08  # metres: a 2-point tank line this close to a 48-point outline makes it a toilet


def _color(obj, getter) -> tuple[int, int, int]:
    r, g, b, a = (ctypes.c_uint() for _ in range(4))
    getter(obj.raw, r, g, b, a)
    return r.value, g.value, b.value


def pdf_rooms(path: Path) -> dict:
    """Page size, nominal scale and, per room number, the fill and outline centroid (page pt)."""
    page = pdfium.PdfDocument(str(path))[0]
    outlines, texts, bar_rects = [], [], []
    textpage = page.get_textpage()
    width_pt, height_pt = page.get_size()
    for obj in page.get_objects():
        if obj.type == raw.FPDF_PAGEOBJ_PATH:
            bounds = obj.get_bounds()
            if (  # scale-bar blocks: 5-point rectangles 4-8 pt high at the bottom left
                raw.FPDFPath_CountSegments(obj.raw) == 5
                and 4 <= bounds[3] - bounds[1] <= 8
                and bounds[1] < 0.12 * height_pt
                and bounds[0] < 0.4 * width_pt
                and _color(obj, raw.FPDFPageObj_GetFillColor)
                in ((0, 0, 0), (255, 255, 255))
                and _color(obj, raw.FPDFPageObj_GetStrokeColor) == (0, 0, 0)
            ):
                bar_rects.append((bounds, _color(obj, raw.FPDFPageObj_GetFillColor)[0]))
            width = ctypes.c_float()
            raw.FPDFPageObj_GetStrokeWidth(obj.raw, width)
            mode, _ = ctypes.c_int(), ctypes.c_int()
            raw.FPDFPath_GetDrawMode(obj.raw, mode, _)
            if (
                _color(obj, raw.FPDFPageObj_GetStrokeColor) == ROOM_STROKE
                and round(width.value, 2) == ROOM_WIDTH
                and mode.value == 2
            ):
                matrix = raw.FS_MATRIX()
                raw.FPDFPageObj_GetMatrix(obj.raw, matrix)
                rings: list[list[tuple[float, float]]] = []
                for i in range(raw.FPDFPath_CountSegments(obj.raw)):
                    seg = raw.FPDFPath_GetPathSegment(obj.raw, i)
                    x, y = ctypes.c_float(), ctypes.c_float()
                    raw.FPDFPathSegment_GetPoint(seg, x, y)
                    if (
                        raw.FPDFPathSegment_GetType(seg) == raw.FPDF_SEGMENT_MOVETO
                        or not rings
                    ):
                        rings.append([])
                    rings[-1].append((
                        matrix.a * x.value + matrix.c * y.value + matrix.e,
                        matrix.b * x.value + matrix.d * y.value + matrix.f,
                    ))  # fmt: skip
                polys = [
                    p
                    for r in rings
                    if len(r) >= 3 and not (p := Polygon(r).buffer(0)).is_empty
                ]
                if polys:
                    outlines.append(
                        (
                            max(polys, key=lambda p: p.area),
                            _color(obj, raw.FPDFPageObj_GetFillColor)[0],
                            len(polys) > 1,
                        )
                    )
        elif obj.type == raw.FPDF_PAGEOBJ_TEXT:
            n = raw.FPDFTextObj_GetText(obj.raw, textpage.raw, None, 0)
            if n > 2:
                buf = (ctypes.c_ushort * n)()
                raw.FPDFTextObj_GetText(
                    obj.raw,
                    textpage.raw,
                    ctypes.cast(buf, ctypes.POINTER(ctypes.c_ushort)),
                    n,
                )
                left, bottom, right, top = obj.get_bounds()
                text = (
                    bytes(memoryview(buf).cast("B"))
                    .decode("utf-16-le")
                    .rstrip("\x00")
                    .strip()
                )
                texts.append(((left + right) / 2, (bottom + top) / 2, text))
    scale = (
        int(m.group(1))
        if (m := re.search(r"1\s*:\s*(\d+)", textpage.get_text_range()))
        else 100
    )
    printed: dict[int, float] = {}
    by_number: dict[str, tuple] = {}
    for x, y, text in texts:
        inside = [
            (o[0].area, i) for i, o in enumerate(outlines) if o[0].contains(Point(x, y))
        ]
        if not inside:
            continue
        i = min(inside)[1]
        if m := AREA_TEXT.fullmatch(text):
            printed[i] = float(m.group(1).replace(",", "."))
        if NUMBER.fullmatch(text):
            poly, fill, holes = outlines[i]
            nested = holes or any(
                j != i and o[0].area < poly.area and poly.buffer(0.3).contains(o[0])
                for j, o in enumerate(outlines)
            )
            by_number[text] = (
                fill,
                (poly.centroid.x, poly.centroid.y),
                i,
                poly.area,
                nested,
            )
    rooms = {
        n: (v[0], v[1], v[3], v[4], printed.get(v[2])) for n, v in by_number.items()
    }  # fill, centroid, area pt2, has cut-outs, printed m2
    bar_rects = _bar_blocks(bar_rects)
    return {
        "w": width_pt,
        "h": height_pt,
        "scale": scale,
        "rooms": rooms,
        "rotation": page.get_rotation(),
        "bar_pt": _bar_length(bar_rects),
        "bar_label_m": _bar_label(texts, bar_rects),
        "has_printed_areas": bool(printed),
    }


def _bar_blocks(rects):
    """The scale bar = the blocks sharing one bottom/top edge (legend squares are alone)."""
    rows: dict[tuple[int, int], list] = defaultdict(list)
    for item in rects:
        rows[(round(item[0][1]), round(item[0][3]))].append(item)
    best = max(rows.values(), key=len, default=[])
    return best if len(best) >= 2 else []


def _bar_length(rects) -> float | None:
    black = [b for b, fill in rects if fill == 0]
    return (
        max(b[2] for b, _ in rects) - min(b[0] for b, _ in rects) - 0.5
        if black
        else None
    )


def _bar_label(texts, rects) -> int | None:
    """The largest metre label above the scale bar (e.g. 5 in '0 1 2 5 m')."""
    if not rects:
        return None
    left, right = min(b[0] for b, _ in rects) - 5, max(b[2] for b, _ in rects) + 5
    top = max(b[3] for b, _ in rects)
    labels = [
        int(t)
        for x, y, t in texts
        if t.isdigit() and left <= x <= right and 0 < y - top < 25
    ]
    return max(labels) if labels else None


def dxf_floor(path: Path) -> dict:
    """Rooms (with number text), unit outlines and elements of one DXF, in metres."""
    msp = ezdxf.readfile(str(path)).modelspace()
    outlines, units, texts, elements = [], [], [], defaultdict(list)
    lines2, unit_labels = [], []
    for e in msp:
        kind, layer = e.dxftype(), e.dxf.layer
        if kind == "LWPOLYLINE":
            pts = [(x, y) for x, y, *_ in e.get_points()]
            if layer in ("ROOM_OUTLINE", "UNIT_OUTLINE") and len(pts) >= 3:
                poly = Polygon(pts)
                poly = poly if poly.is_valid else poly.buffer(0)
                (outlines if layer == "ROOM_OUTLINE" else units).append(poly)
            elif layer == "DOOR" and len(pts) == 5:
                elements["door"].append(Polygon(pts))
            elif layer == "WINDOW" and len(pts) == 4 and e.closed:
                elements["window"].append(Polygon(pts))
            elif layer == "FIXTURE":
                if len(pts) == 69:
                    elements["bathtub"].append(Polygon(pts))
                elif len(pts) == 5:
                    elements["shower"].append(Polygon(pts))
                elif len(pts) == 48:
                    elements["wc_or_sink"].append(Polygon(pts))
                elif len(pts) == 2:
                    lines2.append(pts)
        elif kind == "TEXT" and layer == "ROOM_TEXT":
            if m := UNIT_LABEL.match(e.dxf.text.strip()):
                unit_labels.append(
                    (m.group(1), Point(e.dxf.insert[0], e.dxf.insert[1]))
                )
            texts.append((e.dxf.insert[0], e.dxf.insert[1], e.dxf.text.strip()))
    for shape in elements.pop("wc_or_sink", []):
        tank = any(LineString(line).distance(shape) < TANK_GAP for line in lines2)
        elements["toilet" if tank else "sink"].append(shape)
    owner: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for x, y, text in texts:
        inside = [
            (outlines[i].area, i)
            for i in range(len(outlines))
            if outlines[i].contains(Point(x, y))
        ]
        if inside:
            owner[min(inside)[1]].append((y, text))
    rooms = []
    for i, lines in owner.items():
        words = [t for _, t in sorted(lines, reverse=True)]
        number = next((t for t in words if NUMBER.fullmatch(t)), None)
        if number is None:
            continue
        unit = next((m.group(1) for t in words if (m := UNIT_LABEL.match(t))), None)
        names = [
            t
            for t in words
            if t != number and not UNIT_LABEL.match(t) and "m²" not in t
        ]
        outline = outlines[i]
        nested = [
            o for j, o in enumerate(outlines)
            if j != i and o.area < outline.area and outline.buffer(0.01).contains(o)
        ]  # fmt: skip
        net = outline.difference(unary_union(nested)).area if nested else outline.area
        rooms.append({
            "outline": outline, "number": number, "unit_label": unit, "name": names[0] if names else None,
            "area": net, "cutouts": len(nested),
        })  # fmt: skip
    return {
        "rooms": rooms,
        "units": units,
        "elements": elements,
        "unit_labels": unit_labels,
    }


def room_type(name: str | None, fill: int | None) -> tuple[str, bool]:
    """(extraction type, outdoor flag)."""
    outdoor = name in OUTDOOR_NAMES or fill == 228
    if name in BALCONY_NAMES:
        return "balcony", True
    if outdoor:
        return "outdoor", True
    if name in SHAFT_NAMES or (name is None and fill == 243):
        return "shaft", False
    for kind, words in ROOM_TYPES.items():
        if name in words:
            return kind, False
    return "other", False


class Frame:
    """DXF metres -> page fractions (origin top left), fitted per file from room outlines."""

    def __init__(self, floor: dict, pdf: dict):
        a = 1.0 / (25.4 / 72 * pdf["scale"] / 1000)  # pt per metre, nominal
        pairs = [
            (r["outline"].centroid, pdf["rooms"][r["number"]][1])
            for r in floor["rooms"]
            if r["number"] in pdf["rooms"]
        ]
        self.a, self.w, self.h = a, pdf["w"], pdf["h"]
        self.tx = statistics.fmean(p[1][0] - a * p[0].x for p in pairs)
        self.ty = statistics.fmean(
            p[1][1] - a * p[0].y for p in pairs
        )  # PDF y points up
        res = [
            max(abs(self.tx + a * c.x - q[0]), abs(self.ty + a * c.y - q[1]))
            for c, q in pairs
        ]
        self.residual_max, self.residual_mean = max(res), statistics.fmean(res)
        self.pairs = len(pairs)

    def point(self, x: float, y: float) -> list[float]:
        u, v = (self.tx + self.a * x) / self.w, 1 - (self.ty + self.a * y) / self.h
        return [round(min(max(u, 0.0), 1.0), 5), round(min(max(v, 0.0), 1.0), 5)]

    def poly(self, shape: Polygon) -> list[list[float]]:
        return [self.point(x, y) for x, y in list(shape.exterior.coords)[:-1]]

    def box(self, shape: Polygon) -> list[float]:
        pts = self.poly(shape)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return [min(xs), min(ys), max(xs), max(ys)]


def scale_object(
    pdf: dict, png_width: int | None = None
) -> tuple[dict, str | None, dict]:
    """The extraction_v1 `scale` object: status scaled, every evidence kind, the checks used."""
    m_per_pt = 25.4 / 72 * pdf["scale"] / 1000
    checks: dict[str, float] = {}
    evidence = ["scale_text"]
    if pdf["bar_pt"] and pdf["bar_label_m"]:
        evidence.append("scale_bar")
        checks["bar"] = pdf["bar_pt"] * m_per_pt / pdf["bar_label_m"] - 1
    if pdf["has_printed_areas"]:
        evidence.append("printed_areas")
    plain = sorted(
        (v for v in pdf["rooms"].values() if v[4] and v[4] >= 4 and not v[3]),
        key=lambda v: -v[4],
    )[:2]  # printed area >= 4 m2 and no cut-outs: outline area equals the printed area
    for i, v in enumerate(plain):
        checks[f"area{i + 1}"] = (v[2] * m_per_pt**2 / v[4]) ** 0.5 - 1
    ok = (
        abs(checks.get("bar", 1)) < 0.01
        or sum(abs(c) < 0.01 for c in checks.values()) >= 2
    )
    per_unit = m_per_pt if png_width is None else m_per_pt * pdf["w"] / png_width
    words = ", ".join(f"{k} {abs(c) * 100:.2f}%" for k, c in checks.items())
    obj = {
        "status": "scaled", "m_per_unit": round(per_unit, 6), "evidence": evidence,
        "text": f"1:{pdf['scale']}",
        "source": f"title block 1:{pdf['scale']}; checked: {words or 'none'}"
        + ("" if png_width is None else "; per pixel = per pt x PDF width / PNG width"),
    }  # fmt: skip
    note = (
        None
        if ok
        else f"scale case dropped: checks {words or 'none'} do not agree within 1%"
    )
    return obj, note, checks


def build(
    file: str, split: str, floor: dict, pdf: dict, frame: Frame, page: dict
) -> dict:
    scale_obj, scale_note, _ = scale_object(pdf)
    letters = sorted({letter for letter, _ in floor["unit_labels"]})
    holding: dict[str, Polygon] = {}
    for letter, point in floor[
        "unit_labels"
    ]:  # the label may sit in a room without a number
        cands = [u for u in floor["units"] if u.contains(point)]
        if cands:
            holding[letter] = min(cands, key=lambda u: u.area)
    rooms = []
    for i, r in enumerate(sorted(floor["rooms"], key=lambda r: r["number"]), 1):
        fill = pdf["rooms"].get(r["number"], (None, None))[0]
        kind, outdoor = room_type(r["name"], fill)
        point = r["outline"].representative_point()
        apt = next((a for a, u in holding.items() if u.contains(point)), None)
        rooms.append({
            "id": f"r{i}", "type": kind, "label": r["name"], "page": 1, "plan": "p1",
            "polygon": frame.poly(r["outline"]), "box": frame.box(r["outline"]),
            "area_m2": round(r["area"], 3), "apartment": f"a{apt}" if apt else None,
            "outdoor": outdoor, "attrs": {"number": r["number"], "fill": fill, "cutouts": r["cutouts"]},
        })  # fmt: skip
    elements = []
    for cls, shapes in floor["elements"].items():
        for shape in shapes:
            elements.append({
                "id": f"e{len(elements) + 1}", "class": cls, "page": 1, "plan": "p1",
                "box": frame.box(shape), "polygon": None,
                "attrs": {"source_class": {"door": "DOOR 5-pt", "window": "WINDOW 4-pt",
                          "bathtub": "FIXTURE 69-pt", "shower": "FIXTURE 5-pt",
                          "toilet": "FIXTURE 48-pt + tank", "sink": "FIXTURE 48-pt"}[cls]},
            })  # fmt: skip
    allx = [c for r in rooms for c in (r["box"][0], r["box"][2])]
    ally = [c for r in rooms for c in (r["box"][1], r["box"][3])]
    apartments = []
    for letter in letters:
        total = sum(
            r["area_m2"] for r in rooms
            if r["apartment"] == f"a{letter}" and not r["outdoor"] and r["attrs"]["fill"] != 243
        )  # fmt: skip
        apartments.append(
            {"id": f"a{letter}", "label": letter, "area_m2": round(total, 3)}
        )
    return {
        "schema": "extraction_v1", "file": file, "split": split, "truth": "elements",
        "pages": [{"page": 1, **page}],
        "scale": scale_obj,
        "plans": [{"id": "p1", "page": 1, "box": [min(allx), min(ally), max(allx), max(ally)], "storey": None}],
        "elements": elements, "rooms": rooms, "apartments": apartments, "counts": None,
        "notes": [
            *([scale_note] if scale_note else []),
            (
                f"DXF->page fit on {frame.pairs} rooms: residual max {frame.residual_max:.2f} pt, "
                f"mean {frame.residual_mean:.2f} pt"
            ),
            "apartment ids a<letter>; unit outlines without a label are not apartments",
        ],
    }  # fmt: skip


def rule_check(doc: dict, question: dict) -> float | int | None:
    """The dataset's counting rule applied to a gold dict only; None = not one of our templates."""
    text = question["question"]
    rooms, elements = doc["rooms"], doc["elements"]
    if question["type"] == "count":
        if re.search(r"labelled|Bezeichnung|désignation|denominazione", text):
            m = LABEL_Q.search(text)
            return sum(1 for r in rooms if m and r["label"] == m.group(1))
        for cls, pattern in COUNT_Q:
            if re.search(pattern, text):
                if cls == "apartment":
                    return len(doc["apartments"])
                return sum(1 for e in elements if e["class"] == cls)
        return None
    if question["type"] != "area":
        return None
    numbered = [r for r in rooms]
    if re.search(r"all numbered indoor|nummerierten|numérotées|numerati", text):
        return sum(r["area_m2"] for r in numbered if not r["outdoor"])
    if m := APT_Q.search(text):
        return sum(
            r["area_m2"] for r in numbered
            if r["apartment"] == f"a{m.group(1)}" and not r["outdoor"] and r["attrs"]["fill"] != 243
        )  # fmt: skip
    if m := ROOM_Q.search(text):
        return sum(r["area_m2"] for r in numbered if r["attrs"]["number"] == m.group(1))
    if m := LABEL_Q.search(text):
        return sum(r["area_m2"] for r in numbered if r["label"] == m.group(1))
    return None


def overlay(doc: dict, pdf_path: Path, out: Path) -> None:
    page = pdfium.PdfDocument(str(pdf_path))[0]
    img = page.render(scale=2.0).to_pil().convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    colors = {
        "outdoor": (120, 120, 120, 120),
        "balcony": (120, 120, 120, 120),
        "shaft": (230, 150, 0, 110),
    }
    for r in doc["rooms"]:
        draw.polygon(
            [(x * w, y * h) for x, y in r["polygon"]],
            fill=colors.get(r["type"], (40, 150, 70, 60)),
            outline=(0, 90, 30, 255),
        )
    palette = {
        "door": (220, 0, 0),
        "window": (0, 80, 255),
        "toilet": (200, 0, 200),
        "sink": (0, 170, 170),
        "shower": (255, 120, 0),
        "bathtub": (120, 60, 0),
    }
    for e in doc["elements"]:
        x0, y0, x1, y1 = e["box"]
        draw.rectangle(
            [x0 * w - 2, y0 * h - 2, x1 * w + 2, y1 * h + 2],
            outline=palette[e["class"]] + (255,),
            width=3,
        )
    img.save(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--overlays", type=Path, default=None)
    parser.add_argument(
        "--overlay-stems", default="", help="comma list of file stems to draw"
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    eval_groups = set(
        json.loads((args.split / "manifest.json").read_text())["eval_groups"]
    )
    questions: dict[str, list[dict]] = defaultdict(list)
    with open(args.dataset / "questions.jsonl", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            q = json.loads(line)
            if q["path"].startswith("data/swiss_dwellings/"):
                questions[q["path"]].append({**q, "id": line_no})
    args.out.mkdir(parents=True, exist_ok=True)
    hits, misses, residuals = Counter(), [], []
    combos, scale_errors, dropped = Counter(), [], 0
    docs: dict[str, dict] = {}
    for n, (path, qs) in enumerate(sorted(questions.items())):
        if args.limit is not None and n >= args.limit:
            break
        stem = Path(path).stem
        split = "eval" if f"swiss_dwellings/{stem}" in eval_groups else "dev"
        pdf = pdf_rooms(args.dataset / path)
        floor = dxf_floor(args.dataset / path.replace(".pdf", ".dxf"))
        frame = Frame(floor, pdf)
        residuals.append(frame.residual_max)
        doc = build(
            path,
            split,
            floor,
            pdf,
            frame,
            {"width": pdf["w"], "height": pdf["h"], "unit": "pt"},
        )
        (args.out / f"{stem}.json").write_text(json.dumps(doc, ensure_ascii=False))
        png_path = path.replace(".pdf", ".png")
        with Image.open(args.dataset / png_path) as im:
            png_w, png_h = im.size
        if abs(png_w / png_h - pdf["w"] / pdf["h"]) > 0.005:
            print(f"WARNING {stem}: PNG aspect differs from the PDF page")
        png_doc = {
            **doc,
            "file": png_path,
            "pages": [{"page": 1, "width": png_w, "height": png_h, "unit": "px"}],
        }
        png_doc["scale"], _, _ = scale_object(pdf, png_w)
        combos["+".join(doc["scale"]["evidence"])] += 1
        _, _, checks = scale_object(pdf)
        scale_errors.extend(abs(c) for c in checks.values())
        dropped += any("scale case dropped" in n for n in doc["notes"])
        (args.out / f"{stem}.png.json").write_text(
            json.dumps(png_doc, ensure_ascii=False)
        )
        docs[stem] = doc
        for q in qs:
            got = rule_check(doc, q)
            if got is None:
                hits["unhandled"] += 1
                continue
            tolerance = 0 if q["type"] == "count" else 0.02 * abs(q["answer"])
            ok = abs(got - q["answer"]) <= tolerance + 1e-9
            key = (q["type"], "ok" if ok else "miss")
            hits[key] += 1
            if not ok:
                misses.append((q["id"], q["answer"], round(got, 2), stem))
    print(
        "files",
        len(docs),
        "dev",
        sum(d["split"] == "dev" for d in docs.values()),
        "eval",
        sum(d["split"] == "eval" for d in docs.values()),
    )
    print("rule check", dict(hits))
    print(
        "fit residual max pt: mean",
        round(statistics.fmean(residuals), 3),
        "worst",
        round(max(residuals), 3),
    )
    print("misses", len(misses), misses[:40])
    print("scale evidence per file", dict(combos), "dropped", dropped)
    print(
        "scale check errors: n",
        len(scale_errors),
        "max",
        round(max(scale_errors), 4),
        "mean",
        round(statistics.fmean(scale_errors), 4),
    )
    if args.overlays:
        args.overlays.mkdir(parents=True, exist_ok=True)
        for stem in filter(None, args.overlay_stems.split(",")):
            overlay(
                docs[stem],
                args.dataset / docs[stem]["file"],
                args.overlays / f"{stem}.png",
            )


if __name__ == "__main__":
    main()
