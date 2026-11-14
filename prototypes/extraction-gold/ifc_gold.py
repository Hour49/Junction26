# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "ifcopenshell==0.8.5",
#     "pypdfium2==5.15.2",
#     "shapely==2.2.0",
#     "pillow",
# ]
# ///
"""Extraction gold (extraction_v1) for the floor-plan sheets of `ifc_models`.

NOTE: this script needs ifcopenshell (LGPL-3.0-or-later, imported as a library, not copied; allowed by
docs/decisions/0006-lgpl-dependencies.md); other imports: pypdfium2 (Apache-2.0/BSD-3), shapely (BSD-3),
Pillow (HPND). No PyMuPDF, no Ultralytics.

Truth: the IFC model (what each object is, its storey, wall parts, stair flights, quantities) plus
the plan SVG (where it is drawn). The SVG and the PDF sheet are the same frame
(page fraction = (x - viewBox.x) / viewBox.width, no flip, no rotation; checked on 11 sheets in
review-6), so the SVG boxes are written as fractions of the PDF page. One JSON per sheet PDF that has
questions. Sheets have a scale in the footer text ("Maßstab 1:100").

Elements carry a polygon (the drawn outline) when the object is one SVG shape, which matters on
rotated plans where the axis-aligned box of a diagonal wall is huge (Esplanades, Gymzaal, Gdynia).
Elements: one per IFC object of class door, window, wall, column, beam, slab, railing, stair (top-level
IfcStair, with its flights) that has drawn geometry on the sheet. Box = union of the object's own SVG
group and its decomposition (layer parts of a wall, flights of a stair). attrs: global_id, storey (IFC
containment), source_class (IFC type), parts (number of SVG groups merged), wall length/volume/side
area and slab volume from the file's Qto quantities in metres (length_m, net_volume_m3,
net_side_area_m2). Objects without a drawn shape are not listed; they are counted in `notes`.
Rooms: IfcSpace shapes; area_m2 = polygon area from the SVG (even-odd over sub-paths) x scale^2, the
quantity the dataset answers equal (review-5, within 1.2%). attrs: number (IfcSpace name), storey,
global_id, foreign (the space belongs to another storey than the sheet's).

Run: uv run prototypes/extraction-gold/ifc_gold.py --dataset data/stoa/full/junction-dataset \
         --split data/stoa/split --out data/stoa/extraction_gold/ifc_models \
         [--overlay-dir data/stoa/extraction_gold/_overlays/ifc_models] [--models substring]
Writes <out>/<sheet stem>.json and <out>/../_reports/<out name>_rulecheck.json (counts of the rule check, misses with ids).
"""

import argparse
import collections
import json
import math
import re
import sys
import time
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element as ue
import ifcopenshell.util.unit as uu
import pypdfium2 as pdfium
from PIL import ImageDraw
from shapely.geometry import Point, Polygon

CLASS_MAP = {
    "IfcDoor": "door",
    "IfcWindow": "window",
    "IfcWall": "wall",
    "IfcColumn": "column",
    "IfcBeam": "beam",
    "IfcSlab": "slab",
    "IfcRailing": "railing",
    "IfcStair": "stair",
}
# The same words as the reader's table (ROOM_WORDS in
# backend/app/adapters/vector_pdf/ifc_render.py), kept as a copy of its own: the gold
# must not import what it scores. The first row that matches types the room. Added on
# 2026-11-14 from the space names of the dev models, each checked by eye against the
# names it types: Estonian (tualett, vannituba, magamistuba, elutuba, köök, koridor,
# fuajee, esik, panipaik, saun), Spanish flat codes as in "2IZQ-HAB3" (-hab, -sal,
# -coc, -bañ, -dist; rellano, portal, salón), Dutch (douche, kast), German (Zimmer on
# its own, Vorraum, "Vorr.", Einstellraum) and English (communication).
ROOM_WORDS = [
    ("wc", r"\bwc\b|toilet|toilette|aseo|wc-|sanit|tualett"),
    (
        "bathroom",
        r"\bbad\b|bath|badkamer|badrum|bagno|baño|łazienk|kylpy|vonn|vannituba|douche|-bañ\b",
    ),
    (
        "bedroom",
        r"schlaf|bedroom|slaap|soverom|sypialn|dormitor|camera|habitaci|makuu|magamistuba"
        r"|-hab\d*\b|\bzimmer\b",
    ),
    # before the kitchens: "ELUTUBA+KÖÖK" is a living room with its kitchen
    ("living", r"elutuba"),
    (
        "kitchen",
        r"küche|kuche|kitchen|keuken|køkken|kokken|kuchn|cocina|cucina|keitti|köök|-coc\b",
    ),
    ("living", r"wohn|living|woon|stue|salon|salón|soggiorno|olohuone|-sal\b"),
    (
        "hall",
        r"flur|gang\b|hall|corridor|korytarz|pasillo|gang |trappe|vestibul|foyer|koridor|fuajee"
        r"|\besik\b|-dist\b|rellano|portal|vorraum|\bvorr\b|comm?unication",
    ),
    (
        "storage",
        r"abstell|storage|lager|bod\b|berging|depot|boiler|technik|kast\b|panipaik|einstellr",
    ),
    ("shaft", r"schacht|skakt|shaft|schaft"),
    ("balcony", r"balkon|balcon|terras|terrace|loggia"),
    ("sauna", r"sauna|\bsaun\b"),
]
COLORS = {
    "door": "#d00000",
    "window": "#0046dc",
    "wall": "#f08000",
    "column": "#c000c0",
    "beam": "#00a0a0",
    "slab": "#808000",
    "railing": "#704010",
    "stair": "#00a000",
}


# ---------------------------------------------------------------- SVG
def parse_svg(path: Path):
    t = path.read_text(encoding="utf8")
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', t).group(1).split()]
    groups = {}
    for m in re.finditer(r"<g ([^>]*class=\"([^\"]*)\"[^>]*)>(.*?)</g>", t, re.DOTALL):
        attrs, cls, body = m.groups()
        c = [x for x in cls.split() if x.startswith("Ifc")]
        g = re.search(r'data-guid="([^"]*)"', attrs)
        if not c or not g:
            continue
        rings = []
        for d in re.findall(r' d="([^"]*)"', body):
            for sub in re.split(r"(?=M)", d):
                pts = []
                for cmd, args in re.findall(r"([MLA])([^MLAZ]*)", sub):
                    n = [float(x) for x in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", args)]
                    if cmd == "A":
                        n = n[-2:]
                    pts += list(zip(n[0::2], n[1::2]))
                if len(pts) >= 2:
                    rings.append(pts)
        # columns are drawn as <circle r cx cy> (Institute EG, Smiley-West EG): a 16-gon ring
        for tag in re.findall(r"<circle\b[^>]*>", body):
            v = {k: float(x) for k, x in re.findall(r'\b(r|cx|cy)="([-\d.]+)"', tag)}
            rings.append(
                [
                    (
                        v["cx"] + v["r"] * math.cos(i * math.pi / 8),
                        v["cy"] + v["r"] * math.sin(i * math.pi / 8),
                    )
                    for i in range(16)
                ]
            )
        if not rings:
            continue
        nm = re.search(r'data-name="([^"]*)"', attrs)
        xs = [p[0] for r in rings for p in r]
        ys = [p[1] for r in rings for p in r]
        groups[g.group(1)] = {
            "cls": c[0],
            "name": nm.group(1) if nm else None,
            "rings": rings,
            "bbox": [min(xs), min(ys), max(xs), max(ys)],
        }
    texts = []
    for m in re.finditer(r'<text x="([-\d.]+)" y="([-\d.]+)"[^>]*>([^<]*)</text>', t):
        texts.append((float(m.group(1)), float(m.group(2)), m.group(3).strip()))
    return vb, groups, texts


def union_box(boxes):
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def frac_box(vb, b):
    f = [
        (b[0] - vb[0]) / vb[2],
        (b[1] - vb[1]) / vb[3],
        (b[2] - vb[0]) / vb[2],
        (b[3] - vb[1]) / vb[3],
    ]
    return [round(min(max(v, 0.0), 1.0), 5) for v in f]


def even_odd_polygon(rings):
    shape = None
    for r in sorted(rings, key=lambda r: -abs(Polygon(r).area) if len(r) >= 3 else 0):
        if len(r) < 3:
            continue
        p = Polygon(r).buffer(0)
        shape = p if shape is None else shape.symmetric_difference(p)
    return shape


# ---------------------------------------------------------------- IFC
def storey_of(e):
    c = e
    for _ in range(10):
        if c is None:
            return None
        if c.is_a("IfcBuildingStorey"):
            return c
        for r in getattr(c, "ContainedInStructure", None) or []:
            if r.RelatingStructure.is_a("IfcBuildingStorey"):
                return r.RelatingStructure
            c = r.RelatingStructure
            break
        else:
            a = getattr(c, "Decomposes", None)
            if not a:
                return None
            c = a[0].RelatingObject
    return None


def children(e):
    return [
        o for d in (getattr(e, "IsDecomposedBy", None) or []) for o in d.RelatedObjects
    ]


def load_ifc(path: Path):
    f = ifcopenshell.open(str(path))
    sl = uu.calculate_unit_scale(f)
    try:
        sa = uu.calculate_unit_scale(f, "AREAUNIT")
        sv = uu.calculate_unit_scale(f, "VOLUMEUNIT")
    except (RuntimeError, KeyError, ValueError, AttributeError):
        sa, sv = sl * sl, sl**3
    objs = {}
    for cls, cname in list(CLASS_MAP.items()) + [("IfcSpace", "space")]:
        for e in f.by_type(cls):
            if cname == "stair":
                par = (getattr(e, "Decomposes", None) or [None])[0]
                if par is not None and par.RelatingObject.is_a("IfcStair"):
                    continue  # child of another IfcStair (Molio): not a stair of its own
            s = storey_of(e)
            q = ue.get_psets(e, qtos_only=True) if cname in ("wall", "slab") else {}
            flat = {
                k: v
                for props in q.values()
                for k, v in props.items()
                if isinstance(v, (int, float))
            }
            attrs = {}
            if "Length" in flat and cname == "wall":
                attrs["length_m"] = round(flat["Length"] * sl, 4)
            if "NetVolume" in flat:
                attrs["net_volume_m3"] = round(flat["NetVolume"] * sv, 4)
            if "NetSideArea" in flat:
                attrs["net_side_area_m2"] = round(flat["NetSideArea"] * sa, 4)
            if cname == "space":
                a = ue.get_psets(e, qtos_only=True)
                for props in a.values():
                    for k in ("NetFloorArea", "GrossFloorArea"):
                        if (
                            isinstance(props.get(k), (int, float))
                            and "ifc_area_m2" not in attrs
                        ):
                            attrs["ifc_area_m2"] = props[k] * sa
            kids = []
            stack = children(e)
            while stack:
                k = stack.pop()
                kids.append(k.GlobalId)
                stack += children(k)
            objs[e.GlobalId] = {
                "guid": e.GlobalId,
                "cls": cname,
                "ifc_class": e.is_a(),
                "storey": s.Name if s else None,
                "storey_guid": s.GlobalId if s else None,
                "kids": kids,
                "attrs": attrs,
                "name": e.Name,
                "long_name": getattr(e, "LongName", None),
            }
    return objs


# ---------------------------------------------------------------- scale and text
def sheet_info(pdf_path: Path):
    pdf = pdfium.PdfDocument(str(pdf_path))
    pg = pdf[0]
    w, h = pg.get_size()
    rot = pg.get_rotation()
    txt = pg.get_textpage().get_text_range()
    m = re.search(r"1\s*:\s*(\d+)", txt)
    return w, h, rot, (int(m.group(1)) if m else None)


def scale_bar(pdf_path: Path):
    """Metres per page point from the drawn scale bar (equal-width black/white segments, label 'N m')."""
    from pypdfium2 import raw

    pg = pdfium.PdfDocument(str(pdf_path))[0]
    h = pg.get_size()[1]
    m = re.findall(r"(?<![\d.,])(\d+)\s*m\b", pg.get_textpage().get_text_range())
    rows = collections.defaultdict(list)
    for o in pg.get_objects():
        if o.type == raw.FPDF_PAGEOBJ_PATH:
            lft, b, r, t = o.get_bounds()
            if 2 < t - b < 8 and r - lft > 3 and b < h * 0.35:
                rows[(round(b, 1), round(t, 1))].append((lft, r))
    for v in rows.values():
        v.sort()
        ws = [r - lft for lft, r in v]
        if (
            3 <= len(v) <= 10
            and max(ws) - min(ws) < 0.02 * max(ws)
            and m
            and all(abs(v[i][1] - v[i + 1][0]) < 1.0 for i in range(len(v) - 1))
        ):
            return int(m[-1]) / (v[-1][1] - v[0][0])
    return None


def room_type(label: str) -> str:
    low = label.lower()
    for typ, pat in ROOM_WORDS:
        if re.search(pat, low):
            return typ
    return "other"


# ---------------------------------------------------------------- one sheet
def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build_sheet(dataset, pdf_rel, objs, split, idx):
    pdf_path = dataset / pdf_rel
    svg_path = pdf_path.with_suffix(".svg")
    w, h, rot, ratio = sheet_info(pdf_path)
    vb, groups, texts = parse_svg(svg_path)
    m_per_unit = ratio * 25.4 / 72 / 1000 if ratio else None
    used = set()
    elements, rooms, notes = [], [], []
    undrawn = collections.Counter()
    # sheet storey: the storey with most drawn doors, windows, walls and spaces
    vote = collections.Counter()
    for o in objs.values():
        if o["cls"] in ("door", "window", "wall", "space") and (
            o["guid"] in groups or any(k in groups for k in o["kids"])
        ):
            vote[o["storey"]] += 1
    sheet_storey = vote.most_common(1)[0][0] if vote else None
    # The sheet's title (file name: plan-NN-<storey>) wins when it names exactly one storey of the
    # model: Warmond's "basement" and "intermediate-level-1" sheets draw objects the IFC contains
    # in other storeys (cut plane above the storey), so the vote picks the wrong one there.
    stem = re.sub(r"^.*_plan-\d+-", "", pdf_path.stem)
    named = {
        o["storey"] for o in objs.values() if o["storey"] and slug(o["storey"]) == stem
    }
    if len(named) == 1:
        sheet_storey = named.pop()
    ne = 0
    for o in sorted(objs.values(), key=lambda o: o["guid"]):
        if o["cls"] == "space":
            continue
        gs = [o["guid"]] + o["kids"]
        drawn = [g for g in gs if g in groups]
        if not drawn:
            undrawn[o["cls"] + "@" + str(o["storey"])] += 1
            continue
        used.update(drawn)
        box = frac_box(vb, union_box([groups[g]["bbox"] for g in drawn]))
        ne += 1
        attrs = {
            "source_class": o["ifc_class"],
            "global_id": o["guid"],
            "storey": o["storey"],
            "parts": len(drawn),
            **o["attrs"],
        }
        poly = None
        if len(drawn) == 1:
            ring = max(groups[drawn[0]]["rings"], key=len)
            if 3 <= len(ring) <= 60:
                poly = [
                    [
                        round(min(max((x - vb[0]) / vb[2], 0), 1), 5),
                        round(min(max((y - vb[1]) / vb[3], 0), 1), 5),
                    ]
                    for x, y in ring
                ]
        elements.append(
            dict(
                id=f"e{ne}",
                **{"class": o["cls"]},
                page=1,
                plan="p1",
                box=box,
                polygon=poly,
                attrs=attrs,
            )
        )
    # rooms
    shapes = {}
    for o in objs.values():
        if o["cls"] != "space" or o["guid"] not in groups:
            continue
        g = groups[o["guid"]]
        shape = even_odd_polygon(g["rings"])
        if shape is None or shape.is_empty:
            continue
        shapes[o["guid"]] = shape
        used.add(o["guid"])
    # labels: SVG text inside the smallest polygon containing the text anchor
    lab = collections.defaultdict(list)
    for x, y, s in texts:
        best = None
        for gid, sh in shapes.items():
            if sh.contains(Point(x, y)) and (
                best is None or sh.area < shapes[best].area
            ):
                best = gid
        if best:
            lab[best].append((y, x, s))
    for nr, (gid, sh) in enumerate(sorted(shapes.items(), key=lambda kv: kv[0]), 1):
        o = objs[gid]
        g = groups[gid]
        label = " ".join(s for _, _, s in sorted(lab.get(gid, [])))
        poly = sh.geoms[0] if sh.geom_type == "MultiPolygon" else sh
        ring = [
            [(px - vb[0]) / vb[2], (py - vb[1]) / vb[3]]
            for px, py in list(poly.exterior.coords)[:-1]
        ]
        ring = [
            [round(min(max(a, 0), 1), 5), round(min(max(b, 0), 1), 5)] for a, b in ring
        ]
        area = None
        if m_per_unit:
            # SVG user unit = mm on the page; page unit = pt
            area = round(sh.area * (25.4 / 25.4) * (ratio / 1000) ** 2, 3)
        rooms.append(
            {
                "id": f"r{nr}",
                "type": room_type(label or (g["name"] or "")),
                "label": label or None,
                "page": 1,
                "plan": "p1",
                "polygon": ring,
                "box": frac_box(vb, g["bbox"]),
                "area_m2": area,
                "apartment": None,
                "outdoor": False,
                "attrs": {
                    "number": g["name"],
                    "storey": o["storey"],
                    "global_id": gid,
                    "foreign": o["storey"] != sheet_storey,
                    "source_class": o["ifc_class"],
                    "ifc_name": o["name"],
                    "ifc_long_name": o["long_name"],
                    "holes": len(getattr(sh, "interiors", []))
                    if sh.geom_type == "Polygon"
                    else None,
                },
            }
        )
    skipped = collections.Counter(
        g["cls"] for gid, g in groups.items() if gid not in used
    )
    totals = collections.defaultdict(lambda: collections.defaultdict(float))
    for o in objs.values():
        if o["storey"] is not None:
            t = totals[o["storey"]]
            t[o["cls"] + ".n"] += 1
            for k, v in o["attrs"].items():
                t[o["cls"] + "." + k] += v
    notes.append(
        "ifc_totals (all IFC objects of the storey, drawn or not, from the file's quantities; "
        "used by the rule check): "
        + json.dumps(
            {k: {a: round(b, 4) for a, b in v.items()} for k, v in totals.items()},
            ensure_ascii=False,
        )
    )
    if undrawn:
        notes.append(
            "IFC objects without a drawn shape on this sheet (class@storey: n): "
            + ", ".join(f"{k}: {v}" for k, v in sorted(undrawn.items()))
        )
    if skipped:
        notes.append(
            "drawn SVG groups not listed (no element class, or part of a listed object "
            "already merged): "
            + ", ".join(f"{k}: {v}" for k, v in sorted(skipped.items()))
        )
    # scale vs measured geometry: implied denominator from IfcSpace quantity area vs SVG polygon area (mm^2)
    import statistics

    imp = []
    for gid, sh in shapes.items():
        a = objs[gid]["attrs"].get("ifc_area_m2")
        if a and a > 1 and sh.area > 0:
            imp.append((a * 1e6 / sh.area) ** 0.5)
    wl = []
    for gid, o in objs.items():
        if (
            o["cls"] == "wall"
            and gid in groups
            and o["attrs"].get("length_m", 0) > 1
            and not o["kids"]
        ):
            b = groups[gid]["bbox"]
            lw, lh = b[2] - b[0], b[3] - b[1]
            if min(lw, lh) < 0.25 * max(lw, lh) and o["storey"] == sheet_storey:
                wl.append(o["attrs"]["length_m"] * 1000 / max(lw, lh))
    if len(wl) >= 3:
        wm = statistics.median(wl)
        wa = ratio is not None and abs(wm - ratio) / ratio <= 0.05
        notes.append(
            f"scale check (walls): implied 1:{wm:.0f} from {len(wl)} straight IfcWall Length vs SVG; "
            f"sheet text {'1:' + str(ratio) if ratio else 'none'}; {'agree' if wa else 'DISAGREE'}"
        )
    bar = scale_bar(pdf_path)
    if bar and ratio:
        implied = bar / 0.0003528
        notes.append(
            f"scale check (bar): drawn scale bar implies 1:{implied:.0f}; sheet text 1:{ratio}; "
            + ("agree" if abs(implied - ratio) / ratio <= 0.05 else "DISAGREE")
        )
    elif ratio:
        notes.append("scale check (bar): no scale bar found")
    evidence = ["scale_text"] if ratio else []
    bar_dev = abs(bar / m_per_unit - 1) if bar and m_per_unit else None
    if bar_dev is not None and bar_dev <= 0.01:
        evidence.append("scale_bar")
    if ratio is None:
        scale = {
            "status": "no_scale",
            "m_per_unit": None,
            "evidence": [],
            "text": None,
            "source": "no scale text on the sheet",
        }
    else:
        scale = {
            "status": "scaled",
            "m_per_unit": round(m_per_unit, 6),
            "evidence": evidence,
            "text": f"1:{ratio}",
            "source": f"sheet text 1:{ratio}"
            + (
                f"; scale bar agrees within {bar_dev:.1%}"
                if bar_dev is not None and bar_dev <= 0.01
                else "; scale bar not within 1%"
                if bar_dev is not None
                else "; no scale bar found"
            ),
        }
        if bar_dev is None or bar_dev > 0.01:
            notes.append(
                "scale case dropped: text and bar do not agree within 1% (or no bar found), "
                "so the 2-independent-checks rule is not met"
            )
    if imp:
        med = statistics.median(imp)
        agree = ratio is not None and abs(med - ratio) / ratio <= 0.05
        notes.append(
            f"scale check: implied 1:{med:.0f} from {len(imp)} IfcSpace quantity areas vs SVG polygons; "
            f"sheet text {'1:' + str(ratio) if ratio else 'none'}; {'agree' if agree else 'DISAGREE'}"
        )
    else:
        notes.append("scale check: no IfcSpace quantity areas to compare")
    if ratio is None:
        notes.append("scale: no scale text on the sheet")
    allb = [e["box"] for e in elements] + [r["box"] for r in rooms]
    pbox = (
        [
            min(b[0] for b in allb),
            min(b[1] for b in allb),
            max(b[2] for b in allb),
            max(b[3] for b in allb),
        ]
        if allb
        else [0, 0, 1, 1]
    )
    gold = {
        "schema": "extraction_v1",
        "file": pdf_rel,
        "split": split,
        "truth": "elements",
        "pages": [
            {"page": 1, "width": round(w, 3), "height": round(h, 3), "unit": "pt"}
        ],
        "scale": scale,
        "plans": [{"id": "p1", "page": 1, "box": pbox, "storey": sheet_storey}],
        "elements": elements,
        "rooms": rooms,
        "apartments": [],
        "counts": None,
        "notes": notes,
    }
    if rot:
        gold["notes"].append(
            f"PDF /Rotate {rot}: boxes are in the unrotated SVG frame, CHECK"
        )
    return gold


# ---------------------------------------------------------------- rule check
EN_COUNT = re.compile(r"^How many (.+?) are shown on the floor plan of '(.*)'\?$")
NOUN = {
    "doors": "door",
    "windows": "window",
    "walls": "wall",
    "columns": "column",
    "stairs": "stair",
}


def rule_check(gold, qs):
    """qs: list of (id, question, answer). English questions only (translations repeat the answer)."""
    tot = {}
    for n in gold["notes"]:
        if n.startswith("ifc_totals"):
            tot = json.loads(n.split(": ", 1)[1])
    rows = []
    E = gold["elements"]
    R = gold["rooms"]
    for qid, q, ans in qs:
        fam = None
        got = None
        m = EN_COUNT.match(q)
        if m:
            noun, st = m.groups()
            if noun.startswith("rooms"):
                fam = "count rooms"
                got = sum(1 for r in R if r["attrs"]["storey"] == st)
            else:
                fam = f"count {NOUN[noun]}"
                got = sum(
                    1
                    for e in E
                    if e["class"] == NOUN[noun] and e["attrs"]["storey"] == st
                )
        elif re.match(r"^How many .* are there in the model", q):
            rows.append((qid, "model-level (left out)", ans, None, None))
            continue
        else:
            m = re.match(
                r"^What is the net floor area of the room '(.*)' on '(.*)', in m²\?$", q
            )
            if m:
                fam = "room area"
                name, st = m.groups()
                mm = re.match(r"^(.*) \(([^()]*)\)$", name)
                num = mm.group(2) if mm else None
                cands = [r for r in R if r["attrs"]["storey"] == st]

                def names(r):
                    a = r["attrs"]
                    return {
                        a["ifc_name"],
                        a["ifc_long_name"],
                        f"{a['ifc_long_name']} ({a['ifc_name']})",
                        f"{a['ifc_name']} ({a['number']})",
                        f"{a['ifc_long_name']} ({a['number']})",
                    }

                hit = [r for r in cands if name in names(r)]
                if not hit and num is not None:
                    hit = [r for r in cands if r["attrs"]["number"] == num]
                if not hit:
                    hit = [r for r in cands if (r["label"] or "").startswith(name)]
                if len(hit) > 1:
                    hit = []  # ambiguous: same name or number on several spaces of the storey
                if len(hit) >= 1 and hit[0]["area_m2"] is not None:
                    got = hit[0]["area_m2"]
            m2 = re.match(
                r"^What is the total net floor area of all rooms \(spaces\) on '(.*)', in m²\?$",
                q,
            )
            if m2:
                fam = "total room area"
                got = round(
                    sum(
                        r["area_m2"] or 0
                        for r in R
                        if r["attrs"]["storey"] == m2.group(1)
                    ),
                    3,
                )
            m3 = re.match(
                r"^What is the total net side area of all walls on '(.*)', in m²\?$", q
            )
            if m3:
                fam = "wall side area"
                got = round(tot.get(m3.group(1), {}).get("wall.net_side_area_m2", 0), 3)
            m4 = re.match(
                r"^What is the total length of all walls on '(.*)', in metres\?$", q
            )
            if m4:
                fam = "wall length"
                got = round(tot.get(m4.group(1), {}).get("wall.length_m", 0), 3)
            m5 = re.match(
                r"^What is the total net volume of all (walls|slabs) on '(.*)', in m³\?$",
                q,
            )
            if m5:
                k = "wall" if m5.group(1) == "walls" else "slab"
                fam = f"{k} volume"
                st = m5.group(2)
                got = round(tot.get(st, {}).get(k + ".net_volume_m3", 0), 3)
        if fam is None:
            rows.append((qid, "other", ans, None, None))
            continue
        tol = 0 if fam.startswith("count") else 0.02
        ok = got is not None and abs(got - ans) <= tol * abs(ans) + 0
        rows.append((qid, fam, ans, got, ok))
    return rows


# ---------------------------------------------------------------- overlay
def overlay(dataset, gold, out_png):
    pg = pdfium.PdfDocument(str(dataset / gold["file"]))[0]
    W = 1800
    im = pg.render(scale=W / pg.get_size()[0]).to_pil().convert("RGB")
    d = ImageDraw.Draw(im, "RGBA")
    for r in gold["rooms"]:
        pts = [(x * im.width, y * im.height) for x, y in r["polygon"]]
        foreign = r["attrs"]["foreign"]
        d.polygon(
            pts,
            outline=(180, 0, 0, 255) if foreign else (0, 130, 0, 255),
            fill=(255, 0, 0, 40) if foreign else (0, 160, 0, 30),
        )
    for e in gold["elements"]:
        b = e["box"]
        d.rectangle(
            [
                b[0] * im.width - 2,
                b[1] * im.height - 2,
                b[2] * im.width + 2,
                b[3] * im.height + 2,
            ],
            outline=COLORS.get(e["class"], "black"),
            width=2,
        )
    d.rectangle([0, 0, im.width, 30], fill="white")
    cnt = collections.Counter(e["class"] for e in gold["elements"])
    d.text(
        (6, 8),
        f"{Path(gold['file']).name}  elements {dict(cnt)}  rooms {len(gold['rooms'])} "
        f"(green own storey, red foreign)  colours: "
        + " ".join(f"{k}" for k in COLORS),
        fill="black",
    )
    im.save(out_png)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--overlay-dir")
    ap.add_argument("--overlay-stems", nargs="*", default=[])
    ap.add_argument("--models", default="", help="only models whose name contains this")
    a = ap.parse_args()
    ds = Path(a.dataset)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    qid_split = {}
    for name in ("dev", "eval"):
        with (Path(a.split) / f"{name}.jsonl").open(encoding="utf8") as fh:
            for line in fh:
                if '"data/ifc_models/' in line:
                    r = json.loads(line)
                    qid_split[r["id"]] = name
    by_sheet = collections.defaultdict(list)
    with (ds / "questions.jsonl").open(encoding="utf8") as fh:
        for i, line in enumerate(fh, 1):
            if '"data/ifc_models/' not in line:
                continue
            r = json.loads(line)
            if r["path"].endswith(".pdf") and re.search(r"_plan-", r["path"]):
                by_sheet[r["path"]].append((i, r["question"], r["answer"]))
    by_model = collections.defaultdict(list)
    for p in by_sheet:
        by_model[re.sub(r"_plan-.*$", "", p[:-4])].append(p)
    summary = collections.defaultdict(lambda: collections.Counter())
    misses = []
    files = []
    t0 = time.time()
    for model, sheets in sorted(by_model.items()):
        if a.models not in model:
            continue
        objs = load_ifc(ds / (model + ".ifc"))
        for pdf_rel in sorted(sheets):
            ids = [i for i, _, _ in by_sheet[pdf_rel]]
            sp = {qid_split.get(i) for i in ids} - {None}
            split = "eval" if "eval" in sp else "dev"
            gold = build_sheet(ds, pdf_rel, objs, split, 0)
            stem = Path(pdf_rel).stem
            (out / f"{stem}.json").write_text(json.dumps(gold, ensure_ascii=False))
            files.append((split, stem, len(gold["elements"]), len(gold["rooms"])))
            for row in rule_check(
                gold,
                [
                    q
                    for q in by_sheet[pdf_rel]
                    if q[1].startswith(("How many", "What is"))
                ],
            ):
                qid, fam, ans, got, ok = row
                summary[fam]["n"] += 1
                if ok is None:
                    summary[fam]["skipped"] += 1
                elif ok:
                    summary[fam]["ok"] += 1
                else:
                    misses.append(
                        {
                            "id": qid,
                            "family": fam,
                            "file": pdf_rel,
                            "answer": ans,
                            "got": got,
                        }
                    )
            if a.overlay_dir and stem in a.overlay_stems:
                Path(a.overlay_dir).mkdir(parents=True, exist_ok=True)
                overlay(ds, gold, Path(a.overlay_dir) / f"{stem}.png")
        print(model, "done", round(time.time() - t0), "s", file=sys.stderr)
    res = {
        "files": files,
        "summary": {k: dict(v) for k, v in summary.items()},
        "misses": misses,
    }
    rep = out.parent / "_reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / f"{out.name}_rulecheck.json").write_text(json.dumps(res, ensure_ascii=False))
    print(json.dumps({k: dict(v) for k, v in summary.items()}, indent=1))
    print(
        "files",
        len(files),
        "dev",
        sum(1 for f in files if f[0] == "dev"),
        "eval",
        sum(1 for f in files if f[0] == "eval"),
        "misses",
        len(misses),
    )


if __name__ == "__main__":
    main()
