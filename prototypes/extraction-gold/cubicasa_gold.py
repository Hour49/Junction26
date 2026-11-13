# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""CubiCasa extraction gold (extraction_v1) for the Stoa dataset.

Dev files: elements and rooms from the public CubiCasa5K `model.svg` (read straight from the zip).
Eval files: `truth: counts` built from the question answers only (decision 0003: eval SVGs are never read).

Imports: standard library only (zipfile, xml.etree, json, re, struct). Reads the CubiCasa5K zip from Zenodo
record 2613548 (CC BY-NC-SA 4.0, research use). No PyMuPDF, no Ultralytics, no ifcopenshell.

    uv run prototypes/extraction-gold/cubicasa_gold.py --dataset data/stoa/full/junction-dataset \
        --split data/stoa/split --out data/stoa/extraction_gold/cubicasa5k [--zip data/external/cubicasa5k/cubicasa5k.zip]
    ... --check     also print the rule check (dataset answers vs counts from the gold files)
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = "{http://www.w3.org/2000/svg}"
TEMPLATES = {  # EN question prefix -> template key
    "How many windows": "windows",
    "How many floors": "floors",
    "How many toilet bowls": "wc_seats",
    "How many sinks": "sinks",
    "How many showers and bathtubs": "showers_baths",
    "How many doors": "doors",
    "How many saunas": "saunas",
    "How many kitchens": "kitchens",
    "How many bedrooms": "bedrooms",
    "How many bathrooms": "bathrooms",
    "How many separate WC": "wc_rooms",
    "How many balconies": "balconies",
}
# eval files (truth: counts): template -> count key. Showers and baths are one combined question.
COUNT_KEY = {
    "windows": "window",
    "floors": "plan",
    "wc_seats": "toilet",
    "sinks": "sink",
    "showers_baths": "shower",
    "doors": "door",
    "saunas": "room:sauna",
    "kitchens": "room:kitchen",
    "bedrooms": "room:bedroom",
    "bathrooms": "room:bathroom",
    "wc_rooms": "room:wc",
    "balconies": "room:balcony",
}


# Scale evidence seen by eye on 74 dev images (review-1): stem -> kinds of evidence (extraction_v1 scale.evidence names; "unclear" = unreadable).
SCALE_LOOKED = {
    "high_quality_architectural-12501": [],
    "colorful-12214": [],
    "high_quality-11271": [],
    "colorful-1953": [],
    "high_quality_architectural-2580": ["printed_areas", "dimension_lines"],
    "high_quality-20059": ["not_to_scale_note"],
    "colorful-11565": [],
    "high_quality_architectural-11461": ["printed_areas"],
    "high_quality-7522": [],
    "high_quality_architectural-9352": [],
    "high_quality-8530": [],
    "high_quality_architectural-7578": ["dimension_lines"],
    "colorful-11774": [],
    "colorful-7513": ["not_to_scale_note"],
    "high_quality-14424": [],
    "high_quality_architectural-11862": [],
    "high_quality_architectural-13802": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-14874": ["printed_areas", "dimension_lines"],
    "high_quality-17": ["not_to_scale_note"],
    "high_quality-9835": [],
    "high_quality_architectural-6074": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-1364": ["printed_areas"],
    "high_quality_architectural-1576": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-14052": ["dimension_lines"],
    "high_quality_architectural-7798": ["dimension_lines"],
    "high_quality-10669": ["not_to_scale_note"],
    "high_quality_architectural-14587": ["printed_areas"],
    "high_quality_architectural-12598": ["not_to_scale_note"],
    "high_quality-6256": [],
    "high_quality_architectural-769": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-12544": ["printed_areas"],
    "high_quality_architectural-9976": ["printed_areas"],
    "colorful-13019": [],
    "high_quality_architectural-8218": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-10217": ["not_to_scale_note"],
    "high_quality-3920": ["not_to_scale_note"],
    "high_quality_architectural-9837": [],
    "high_quality_architectural-13717": ["dimension_lines"],
    "high_quality_architectural-9104": ["dimension_lines"],
    "high_quality_architectural-7084": ["dimension_lines"],
    "high_quality-9336": [],
    "high_quality_architectural-6322": ["dimension_lines"],
    "high_quality-12896": [],
    "high_quality_architectural-14561": [
        "printed_areas",
        "dimension_lines",
        "scale_text",
    ],
    "colorful-10706": [],
    "high_quality_architectural-10719": ["printed_areas"],
    "high_quality-10666": ["unclear"],
    "colorful-444": ["not_to_scale_note"],
    "high_quality_architectural-3778": ["printed_areas"],
    "high_quality-13742": [],
    "high_quality-3106": [],
    "high_quality_architectural-10267": [],
    "colorful-11397": [],
    "high_quality_architectural-486": [],
    "high_quality_architectural-5901": ["printed_areas"],
    "colorful-9392": ["not_to_scale_note"],
    "high_quality-5972": [],
    "high_quality-12137": [],
    "high_quality-7539": [],
    "high_quality_architectural-13791": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-10149": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-13113": [],
    "high_quality_architectural-10203": ["printed_areas"],
    "colorful-10312": [],
    "high_quality-215": [],
    "high_quality-1651": ["not_to_scale_note"],
    "high_quality_architectural-3864": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-11404": ["printed_areas", "dimension_lines"],
    "high_quality-3954": [],
    "colorful-13577": [],
    "high_quality-13094": [],
    "high_quality_architectural-4697": [],
    "high_quality_architectural-11153": ["printed_areas"],
    "high_quality_architectural-8502": ["printed_areas"],
}

# Hand scales (status scaled): stem -> (metres per svg unit, evidence, printed scale text, source). Gold rule: at least two printed room areas
# agree within 1% (largest subset within +-1% of its median; the median of that subset is the value). arch-1576 failed (2 rooms, 2.3% apart) and is dropped.
HAND_SCALES = {
    "high_quality_architectural-14874": (
        0.00966,
        ["printed_areas", "dimension_lines"],
        None,
        "hand: 6 of 9 printed room areas agree within 1% (K 12,2 OH 17,9 ET 6,8 PH 3,6 WC 2,0 MH 10,6/12,5/10,7 m2); outer dimension 10930 mm vs 10,73 m interior + walls",
    ),
    "high_quality_architectural-11461": (
        0.00995,
        ["printed_areas"],
        None,
        "hand: 4 of 5 printed room areas agree within 1% (KEITTIO 13 ET 5,5 OH 23 MH 12,5 m2)",
    ),
    "high_quality_architectural-13802": (
        0.00971,
        ["printed_areas"],
        None,
        "hand: 3 of 3 printed room areas agree within 1% (WC 1,6 KPH 3,3 KHH 9 m2)",
    ),
    "high_quality_architectural-9976": (
        0.00977,
        ["printed_areas"],
        None,
        "hand: 9 of 11 printed room areas agree within 1% (mh 12,4 11,4 8,6 vh 3,8 wc 3,6 khh 7,8 pukut 7,4 pesut 8,1 tk 7,0 m2)",
    ),
    "high_quality_architectural-769": (
        0.00999,
        ["printed_areas", "dimension_lines"],
        None,
        "hand: 4 of 7 printed room areas agree within 1% (VIERASH 11,7 OLOH 24,0 TK 3,0 VH 2,5 m2); total width 14915 mm printed",
    ),
    "high_quality_architectural-32": (
        0.00952,
        ["printed_areas"],
        None,
        "hand: 4 of 5 printed room areas agree within 1% (MH 13,9 TEKN.TILA 8,4 AT 20,3 MH 10,9 m2), skewed scan",
    ),
    "high_quality_architectural-11250": (
        0.01035,
        ["printed_areas", "dimension_lines"],
        None,
        "hand: 4 of 7 printed room areas agree within 1% (PH 4,2 PKH 5,3 MH 8,1 TK 6,1 m2)",
    ),
    "high_quality_architectural-14087": (
        0.01031,
        ["printed_areas", "dimension_lines", "scale_text"],
        "1:50",
        "hand: 4 of 7 printed room areas agree within 1% (MH 16 KH 6,6 PH 6,9 TYOH 11,5 m2); sheet text 1:50, not usable alone for pixels",
    ),
    "high_quality_architectural-13666": (
        0.01011,
        ["printed_areas", "dimension_lines", "scale_text"],
        "1:50",
        "hand: 4 of 6 printed room areas agree within 1% (MH 13,3 MH 14,0 OH 26,4 TEKN 3,8 VAR 28,6 m2); sheet text 1:50, not usable alone for pixels",
    ),
    "high_quality_architectural-14561": (
        0.00965,
        ["printed_areas", "dimension_lines", "scale_text"],
        "1:50",
        "hand: 4 of 9 printed room areas agree within 1% (K 9,5 OH 22,0 PH 4,0 WC 2,5 KHH 9,5 VAR 10,0 m2); sheet text 1:50, not usable alone for pixels",
    ),
}
DROPPED_SCALES = {
    "high_quality_architectural-1576": "printed room areas TUPA/KEITTIO 25,9 and ET 9,2 m2 disagree by 2.3% (> 1%); dropped from the scale cases"
}
# model.svg units are about 1 cm: 0.0095-0.0104 m/unit on the 10 hand-scaled plans (mean abs error 2.5%, max 4.8%). Reference only, never a 2% truth.
SVG_M_PER_UNIT = 0.01

DIM_LINES: dict = {}  # stem -> review-2 case, filled in main()


def make_scale(stem: str, ws: int, W: int):
    """scale object (status scaled / no_scale / not_to_scale) and notes for a dev file. m per Stoa PNG pixel."""
    ref = round(SVG_M_PER_UNIT * ws / W, 7)
    if stem in HAND_SCALES:
        mu, ev, text, src = HAND_SCALES[stem]
        return {
            "status": "scaled",
            "m_per_unit": round(mu * ws / W, 7),
            "evidence": ev,
            "text": text,
            "source": src,
        }, []
    if stem in DIM_LINES:
        c = DIM_LINES[stem]
        if c.get("m_per_unit") is None:  # review-2 dropped it (anisotropic scan)
            ref = round(SVG_M_PER_UNIT * ws / W, 7)
            return {
                "status": "no_scale",
                "m_per_unit": None,
                "evidence": [],
                "text": None,
                "source": "dropped from the scale cases",
                "reference_m_per_unit": ref,
            }, [
                "scale dropped: anisotropic scan 2%: " + c.get("note", ""),
                "scale not reviewed",
            ]
        notes = (
            ["trap: printed 1:50 belongs to a detail, not the plan"]
            if c.get("trap")
            else []
        )
        return {
            "status": "scaled",
            "m_per_unit": c["m_per_unit"],
            "evidence": ["dimension_lines"],
            "text": None,
            "source": "dimension lines, "
            + "; ".join(str(x) for x in c.get("checks", []))
            + (" | " + c["note"] if c.get("note") else ""),
        }, notes
    kinds = SCALE_LOOKED.get(stem)
    if stem in DROPPED_SCALES:
        return {
            "status": "no_scale",
            "m_per_unit": None,
            "evidence": [],
            "text": None,
            "source": "dropped from the scale cases",
            "reference_m_per_unit": ref,
        }, [DROPPED_SCALES[stem], "scale not reviewed"]
    if kinds == ["not_to_scale_note"]:
        return {
            "status": "not_to_scale",
            "m_per_unit": None,
            "evidence": ["not_to_scale_note"],
            "text": None,
            "source": "the sheet says it is not to scale (e.g. suuntaa-antava, ei mittakaavassa)",
        }, []
    if kinds == []:
        return {
            "status": "no_scale",
            "m_per_unit": None,
            "evidence": [],
            "text": None,
            "source": "looked at the image: no scale evidence",
            "reference_m_per_unit": ref,
        }, []
    if kinds:  # evidence seen but no verified value
        what = "unreadable text" if kinds == ["unclear"] else ", ".join(kinds)
        return {
            "status": "no_scale",
            "m_per_unit": None,
            "evidence": [],
            "text": None,
            "source": "scale not verified",
            "reference_m_per_unit": ref,
        }, [
            "scale not reviewed",
            f"image shows ({what}) but no value was verified; excluded from scale cases",
        ]
    return {
        "status": "no_scale",
        "m_per_unit": None,
        "evidence": [],
        "text": None,
        "source": "not reviewed",
        "reference_m_per_unit": ref,
    }, ["scale not reviewed"]


# ---------- geometry ----------
def mat_mul(a, b):  # a applied after b: a*b, matrices (a,b,c,d,e,f)
    return (
        a[0] * b[0] + a[2] * b[1],
        a[1] * b[0] + a[3] * b[1],
        a[0] * b[2] + a[2] * b[3],
        a[1] * b[2] + a[3] * b[3],
        a[0] * b[4] + a[2] * b[5] + a[4],
        a[1] * b[4] + a[3] * b[5] + a[5],
    )


def parse_transform(t: str | None):
    m = (1, 0, 0, 1, 0, 0)
    if not t:
        return m
    for name, args in re.findall(r"(\w+)\(([^)]*)\)", t):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if name == "matrix":
            n = tuple(v)
        elif name == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        else:
            continue
        m = mat_mul(m, n)
    return m


def apply(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def pts(s: str):
    v = [float(x) for x in re.split(r"[\s,]+", s.strip()) if x]
    return list(zip(v[0::2], v[1::2]))


def dedupe(poly):
    out = []
    for p in poly:
        if not out or p != out[-1]:
            out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


# ---------- svg ----------
def svg_size(root):
    return float(root.get("width")), float(root.get("height"))


def own_polygon(g, prefer=("BoundaryPolygon",)):
    """Points (local coordinates) of the group's own outline polygon."""
    for child in g:
        if child.tag == NS + "polygon":
            return pts(child.get("points"))
    for child in g:
        if (
            child.tag == NS + "g"
            and (child.get("class") or "").split()[:1]
            and child.get("class").split()[0] in prefer
        ):
            for pg in child.iter(NS + "polygon"):
                return pts(pg.get("points"))
    return None


def local_points(
    g,
    m=(1, 0, 0, 1, 0, 0),
    skip=("Direction", "Name", "Dimension", "SelectionControls", "Visual"),
):
    """All outline points below g in g's local frame (polygons, rects, circles, lines, paths with absolute M/L coordinates)."""
    out = []
    for ch in g:
        cl = (ch.get("class") or "").split()[:1]
        if cl and cl[0] in skip:
            continue
        cm = mat_mul(m, parse_transform(ch.get("transform")))
        tag = ch.tag.replace(NS, "")
        if tag == "polygon" or tag == "polyline":
            out += [apply(cm, p) for p in pts(ch.get("points") or "")]
        elif tag == "rect":
            x, y, w, h = (float(ch.get(k) or 0) for k in ("x", "y", "width", "height"))
            out += [
                apply(cm, p) for p in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
            ]
        elif tag == "circle":
            cx, cy, r = (float(ch.get(k) or 0) for k in ("cx", "cy", "r"))
            out += [apply(cm, p) for p in ((cx - r, cy - r), (cx + r, cy + r))]
        elif tag == "line":
            out += [
                apply(cm, (float(ch.get("x1")), float(ch.get("y1")))),
                apply(cm, (float(ch.get("x2")), float(ch.get("y2")))),
            ]
        elif tag == "g":
            out += local_points(ch, cm, skip)
    return out


def hull_box(points):
    x0, y0, x1, y1 = bbox(points)
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def walk(g, m, ctx, out):
    """Collect (class, matrix, element, floor) for every group below g."""
    for ch in g:
        if ch.tag != NS + "g":
            continue
        cm = mat_mul(m, parse_transform(ch.get("transform")))
        cl = ch.get("class") or ""
        floor = ctx
        if cl.startswith("Floorplan"):
            floor = ch.get("id") or cl.split()[-1]
        out.append((cl, cm, ch, floor))
        walk(ch, cm, floor, out)


def label_of(space):
    for e in space.iter(NS + "g"):
        if (e.get("class") or "") == "TextLabel NameLabel":
            t = next(e.iter(NS + "text"), None)
            return (t.text or "").strip() if t is not None else ""
    return ""


def room_type(cl: str, label: str):
    w = cl.split()[1:]
    k = w[0] if w else ""
    if k == "Bedroom":
        return "bedroom", False
    if k == "Kitchen":
        return "kitchen", False
    if k == "Bath":
        return ("wc" if re.match(r"\s*WC", label.upper()) else "bathroom"), False
    if k == "Sauna":
        return "sauna", False
    if k == "Outdoor":
        return ("balcony" if len(w) > 1 and w[1] == "Balcony" else "outdoor"), True
    if k in ("LivingRoom", "Dining", "Den", "RecreationRoom"):
        return "living", False
    if k in ("Entry", "Lobby", "DraughtLobby", "Hall", "Alcove"):
        return "hall", False
    if k in (
        "Storage",
        "Closet",
        "Utility",
        "DressingRoom",
        "Garage",
        "CarPort",
        "Attic",
        "Basement",
    ):
        return "storage", False
    return "other", False


def element_class(cl: str):
    if cl.startswith("Door ") or cl == "Door":
        return "door"
    if cl.startswith("Window"):
        return "window"
    if not cl.startswith("FixedFurniture "):
        return None
    k = cl[len("FixedFurniture ") :]
    if k == "Toilet":
        return "toilet"
    if "Sink" in k:
        return "sink"
    if k == "Shower":
        return "shower"
    if k.startswith("Bathtub"):
        return "bathtub"
    if "SaunaStove" in k:
        return "sauna_stove"
    return None


def storey_of(fid: str):
    """The SVG's own Floorplan id ("Floor-1", "Floor-2", "Basement-1"); a string, as extraction_v1 wants."""
    return fid or None


def build_dev(svg_bytes: bytes, file: str, W: int, H: int, ws: int, hs: int):
    """W,H = size of the Stoa PNG (F1_original); ws,hs = size of F1_scaled, the pixel frame of model.svg."""
    root = ET.fromstring(svg_bytes)

    def fr(p):
        return (
            min(1.0, max(0.0, p[0] / ws)),
            min(1.0, max(0.0, p[1] / hs)),
        )  # clamp: a few shapes poke out of the page

    items = []
    walk(root, (1, 0, 0, 1, 0, 0), None, items)
    floors = [(cl, m, e, f) for cl, m, e, f in items if cl.startswith("Floorplan")]
    plan_ids = {}
    plans = []
    for cl, m, e, f in floors:
        plan_ids[f] = f"p{len(plans) + 1}"
        plans.append(
            {
                "id": plan_ids[f],
                "page": 1,
                "box": None,
                "storey": storey_of(f),
                "_pts": [],
            }
        )
    elements, rooms = [], []
    merged = 0
    seen = {}
    for cl, m, e, f in items:
        if f is None:
            continue
        pid = plan_ids[f]
        pl = next(p for p in plans if p["id"] == pid)
        if cl.startswith("Space "):
            local = own_polygon(e)
            if not local:
                continue
            poly = [fr(apply(m, p)) for p in dedupe(local)]
            label = label_of(e)
            t, outdoor = room_type(cl, label)
            x0, y0, x1, y1 = bbox(poly)
            rooms.append(
                {
                    "id": f"r{len(rooms) + 1}",
                    "type": t,
                    "label": label,
                    "page": 1,
                    "plan": pid,
                    "polygon": [[round(a, 5), round(b, 5)] for a, b in poly]
                    if len(poly) >= 3
                    else None,
                    "box": [round(x0, 5), round(y0, 5), round(x1, 5), round(y1, 5)],
                    "area_m2": None,
                    "apartment": None,
                    "outdoor": outdoor,
                    "attrs": {"source_class": cl},
                }
            )
            pl["_pts"] += poly
            continue
        if cl.startswith("Wall"):
            local = own_polygon(e)
            if local:
                pl["_pts"] += [fr(apply(m, p)) for p in local]
        ec = element_class(cl)
        if ec is None:
            continue
        local = own_polygon(e)
        if not local:
            lp = local_points(e)
            if not lp:
                continue
            local = hull_box(lp)
        raw = [apply(m, p) for p in dedupe(local)]
        poly = [fr(p) for p in raw]
        key = (
            ec,
            tuple((round(a, 2), round(b, 2)) for a, b in raw),
        )  # identical in the SVG, not after clamping
        if key in seen:
            merged += 1
            seen[key]["attrs"]["multiplicity"] = (
                seen[key]["attrs"].get("multiplicity", 1) + 1
            )
            continue
        x0, y0, x1, y1 = bbox(poly)
        seen[key] = el = {
            "id": f"e{len(elements) + 1}",
            "class": ec,
            "page": 1,
            "plan": pid,
            "box": [round(x0, 5), round(y0, 5), round(x1, 5), round(y1, 5)],
            "polygon": [[round(a, 5), round(b, 5)] for a, b in poly]
            if len(poly) >= 3
            else None,
            "attrs": {"source_class": cl},
        }
        elements.append(el)
    for pl in plans:
        p = pl.pop("_pts")
        if p:
            x0, y0, x1, y1 = bbox(p)
            pl["box"] = [
                round(max(0, x0), 5),
                round(max(0, y0), 5),
                round(min(1, x1), 5),
                round(min(1, y1), 5),
            ]
        else:
            pl["box"] = [0.0, 0.0, 1.0, 1.0]
    notes = (
        [f"{merged} element(s) drawn twice at identical geometry merged"]
        if merged
        else []
    )
    stem = Path(file).stem
    scale, snotes = make_scale(stem, ws, W)
    notes += snotes
    return {
        "schema": "extraction_v1",
        "file": file,
        "split": "dev",
        "truth": "elements",
        "pages": [{"page": 1, "width": W, "height": H, "unit": "px"}],
        "scale": scale,
        "plans": plans,
        "elements": elements,
        "rooms": rooms,
        "apartments": [],
        "counts": None,
        "notes": notes,
    }


# Frame (checked on 60 dev plans, see review-1.md section 8): model.svg user units are pixels of F1_scaled.png
# (origin top left, uniform), so fraction = svg coordinate / F1_scaled size; F1_original (= the Stoa PNG) has the same aspect.
def png_size(path: Path):
    with open(path, "rb") as f:
        b = f.read(24)
    return struct.unpack(">II", b[16:24])


def template_of(q: str):
    for pre, k in TEMPLATES.items():
        if q.startswith(pre):
            return k
    return None


def counts_from_gold(g: dict):
    """The dataset's counting rules, applied to a dev gold file (rule check)."""
    c = collections.Counter()
    for e in g["elements"]:
        c[e["class"]] += e["attrs"].get(
            "multiplicity", 1
        )  # duplicates count as drawn objects (the dataset counts them)
    r = collections.Counter(x["type"] for x in g["rooms"])
    sauna = r["sauna"] or c["sauna_stove"]
    return {
        "windows": c["window"],
        "floors": len(g["plans"]),
        "wc_seats": c["toilet"],
        "sinks": c["sink"],
        "showers_baths": c["shower"] + c["bathtub"],
        "doors": c["door"],
        "saunas": sauna,
        "kitchens": r["kitchen"],
        "bedrooms": r["bedroom"],
        "bathrooms": r["bathroom"],
        "wc_rooms": r["wc"],
        "balconies": r["balcony"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--zip", default="data/external/cubicasa5k/cubicasa5k.zip")
    ap.add_argument("--check", action="store_true")
    ap.add_argument(
        "--dim-lines",
        default="data/stoa/extraction_gold/_scale/cubicasa_dimension_lines.json",
        help="review-2 dimension-line scale cases ([{file, m_per_unit, checks, note}]); read if present",
    )
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    ds, out = Path(a.dataset), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    split_of = {}
    for sp in ("dev", "eval"):
        for line in (Path(a.split) / f"{sp}.jsonl").read_text("utf8").splitlines():
            d = json.loads(line)
            if "cubicasa5k" in d["path"]:
                split_of.setdefault(d["path"], sp)
    qs = collections.defaultdict(dict)  # path -> template -> (id, answer)
    for i, line in enumerate(
        (ds / "questions.jsonl").read_text("utf8").splitlines(), 1
    ):
        d = json.loads(line)
        if "cubicasa5k" not in d["path"]:
            continue
        t = template_of(d["question"])
        if t:
            qs[d["path"]][t] = (i, d["answer"])
    z = zipfile.ZipFile(a.zip)
    dl = Path(a.dim_lines)
    if dl.exists():
        for c in json.loads(dl.read_text("utf8")):
            DIM_LINES[Path(c["file"]).stem] = c
    n = collections.Counter()
    avg = collections.Counter()
    results = collections.defaultdict(lambda: [0, 0, []])
    for path in sorted(qs):
        sp = split_of.get(path)
        if sp is None:
            continue
        if a.limit and sum(n.values()) >= a.limit:
            break
        stem = Path(path).stem
        W, H = png_size(ds / path)
        if sp == "dev":
            cat, num = stem.rsplit("-", 1)
            ws, hs = struct.unpack(
                ">II", z.read(f"cubicasa5k/{cat}/{num}/F1_scaled.png")[16:24]
            )
            g = build_dev(
                z.read(f"cubicasa5k/{cat}/{num}/model.svg"), path, W, H, ws, hs
            )
            avg["elements"] += len(g["elements"])
            avg["rooms"] += len(g["rooms"])
            if a.check:
                got = counts_from_gold(g)
                for t, (qid, ans) in qs[path].items():
                    r = results[t]
                    r[1] += 1
                    if got[t] == ans:
                        r[0] += 1
                    else:
                        r[2].append((qid, path, ans, got[t]))
        else:
            counts = {}
            for t, (qid, ans) in qs[path].items():
                counts[COUNT_KEY[t]] = ans
            g = {
                "schema": "extraction_v1",
                "file": path,
                "split": "eval",
                "truth": "counts",
                "pages": [{"page": 1, "width": W, "height": H, "unit": "px"}],
                "scale": {
                    "status": "no_scale",
                    "m_per_unit": None,
                    "evidence": [],
                    "text": None,
                    "source": "eval split: not labelled",
                },
                "plans": [],
                "elements": [],
                "rooms": [],
                "apartments": [],
                "counts": counts,
                "notes": [
                    "scale not reviewed",
                    (
                        "counts from question answers; showers_baths is one combined count under"
                        " 'shower'; room:sauna is the sauna count (room else stove)"
                    ),
                ],
            }
        (out / f"{stem}.json").write_text(
            json.dumps(g, ensure_ascii=False), encoding="utf8"
        )
        n[sp] += 1
    print(f"written: dev {n['dev']}, eval {n['eval']} -> {out}")
    if n["dev"]:
        print(
            f"dev mean per file: elements {avg['elements'] / n['dev']:.1f}, rooms {avg['rooms'] / n['dev']:.1f}"
        )
    if a.check:
        print("rule check (dev):")
        for t in TEMPLATES.values():
            ok, tot, miss = results[t]
            print(f"  {t}: {ok}/{tot}")
            for m in miss[:20]:
                print(f"     miss id {m[0]} {m[1]} answer {m[2]} gold {m[3]}")
            if len(miss) > 20:
                print(f"     ... {len(miss) - 20} more")


if __name__ == "__main__":
    sys.exit(main())
