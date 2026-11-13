# /// script
# requires-python = ">=3.13"
# dependencies = ["pypdfium2==5.15.2", "shapely==2.2.0", "pillow==13.0.0"]
# ///
"""Conflict gold (extraction_v1 `conflicts`, ingestion stage 8) for the golden set, dev split only.

Writes `<out>/conflicts.jsonl` (one line per file: {"file", "split", "conflicts": [...]}),
`<out>/extras.jsonl` (Part 2 lines, kind "conflict") and one overlay PNG per `conflict` entry.
The two values of every entry are computed here from the gold JSON files and the dataset;
what is judged by hand (which disagreements are real, the resolution rule, what the picture
showed) is the data in CONFLICTS below. Nothing is invented: a candidate that is not listed
here was rejected (see review-10.md section 9).

Sources of the values:
- ifc_models: `plan_drawing` = elements/rooms of the gold JSON for the sheet's storey;
  `ifc_model` = the `ifc_totals` note of the same JSON (counts of the IFC objects of that storey).
- cubicasa5k scale: `scale_text` = the printed ratio, `dimension_lines` = the gold m/px turned
  into a ratio with the page width as A4 (297 mm) at the PNG width.
- swiss_dwellings agree entries: `printed_label` = the "x,xx m²" text object inside the room
  outline on the PDF, `polygon_x_scale` = the gold room area (outline x scale^2).
Run (repo root): uv run prototypes/extraction-gold/conflicts_gold.py
"""

import argparse
import collections
import ctypes
import json
import re
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from pypdfium2 import raw
from shapely.geometry import Point, Polygon

GOLD = "data/stoa/extraction_gold"
IFC = "ifc_models"
A4_MM = 297.0  # CubiCasa high_quality scans are A4 landscape (aspect 1.414)

# Hand-judged IFC-vs-drawing disagreements, each looked at on the rendered sheet (see `seen`).
# (stem, class | "space", quantity, rule for the resolution, what the picture showed)
IFC_CONFLICTS = [
    (
        "bimspeed-gdynia_ruchu-oporu-18_plan-03-0",
        "space",
        "room_count",
        "keep spaces whose IFC storey is the sheet's storey (foreign spaces are greyed)",
        "foreign_rooms",
        "9 tinted spaces; 4 carry -1.x numbers and overlap the 0.x rooms",
    ),
    (
        "rwth-digitalhub_digitalhub-fm-arc-v2_plan-01-b01-okrd",
        "space",
        "room_count",
        "keep spaces whose IFC storey is the sheet's storey",
        "foreign_rooms",
        "14 tinted spaces; the two lift shafts Aufzug West/Ost (300, 400) belong to another storey",
    ),
    (
        "rwth-digitalhub_digitalhub-fm-arc-v2_plan-03-e01-okrd",
        "space",
        "room_count",
        "keep spaces whose IFC storey is the sheet's storey",
        "foreign_rooms",
        "32 tinted spaces; the six lift/shaft cells 300-302, 400-402 belong to another storey",
    ),
    (
        "bimspeed-vitoria_ald26-before_plan-01-p0",
        "column",
        "element_count",
        "count what the sheet draws (1.20 m cut)",
        "ifc_undrawn",
        "19 solid column squares drawn and all boxed; the IFC has 33 columns on storey P0",
    ),
    (
        "bimspeed-vitoria_ald26-project_plan-01-p0",
        "column",
        "element_count",
        "count what the sheet draws (1.20 m cut)",
        "ifc_undrawn",
        "19 solid column squares drawn and all boxed; the IFC has 33 columns on storey P0",
    ),
    (
        "bimspeed-gdynia_ruchu-oporu-18_plan-03-0",
        "window",
        "element_count",
        "count what the sheet draws (our rule, not Stoa's: no dataset question asks the window count here)",
        "ifc_undrawn",
        "the IFC windows not drawn have sills 1.24-1.94 m, above the 1.20 m cut",
    ),
    (
        "bimspeed-gdynia_ruchu-oporu-18_plan-02-1",
        "window",
        "element_count",
        "count what the sheet draws (our rule, not Stoa's: no dataset question asks the window count here)",
        "ifc_undrawn",
        "the 4 undrawn IFC windows have sills at 1.63 m, above the 1.20 m cut",
    ),
    (
        "bsc-esplanades_1807-ep-ar-v18_plan-01-1-korrus",
        "window",
        "element_count",
        "count what the sheet draws (our rule, not Stoa's: no dataset question asks the window count here)",
        "ifc_undrawn",
        "the undrawn IFC windows sit at 1.68 m, above the 1.20 m cut",
    ),
    (
        "bsc-esplanades_1807-ep-ar-v18_plan-02-2-korrus",
        "window",
        "element_count",
        "count what the sheet draws (our rule, not Stoa's: no dataset question asks the window count here)",
        "ifc_undrawn",
        "the undrawn IFC windows sit at 1.68 m, above the 1.20 m cut",
    ),
    (
        "bsc-esplanades_1807-ep-ar-v18_plan-03-3-korrus",
        "window",
        "element_count",
        "count what the sheet draws (our rule, not Stoa's: no dataset question asks the window count here)",
        "ifc_undrawn",
        "the undrawn IFC windows sit at 1.68 m, above the 1.20 m cut",
    ),
    (
        "bsc-esplanades_1807-ep-ar-v18_plan-04-4-korrus",
        "window",
        "element_count",
        "count what the sheet draws (our rule, not Stoa's: no dataset question asks the window count here)",
        "ifc_undrawn",
        "the undrawn IFC windows sit at 1.68 m, above the 1.20 m cut",
    ),
    (
        "bsc-esplanades_1807-ep-ar-v18_plan-05-5-korrus",
        "window",
        "element_count",
        "count what the sheet draws (our rule, not Stoa's: no dataset question asks the window count here)",
        "ifc_undrawn",
        "the undrawn IFC windows sit at 1.68 m, above the 1.20 m cut",
    ),
    (
        "tuwien-escape-route_real-world-escape-route-test-model-zdb_plan-05-dg1",
        "window",
        "element_count",
        "count what the sheet draws (our rule, not Stoa's: no dataset question asks the window count here)",
        "ifc_undrawn",
        "the 2 undrawn IFC windows are roof windows hosted by an IfcRoof",
    ),
    (
        "tuwien-escape-route_real-world-escape-route-test-model-zdb_plan-07-da",
        "space",
        "room_count",
        "no rule decides it: show both and lower confidence",
        "ifc_undrawn",
        "roof sheet with no tinted space; the IFC has 2 spaces on storey DA",
    ),
]
# CubiCasa mixed files (gold scale evidence has printed_areas and dimension_lines): the printed-area
# scale is the gold m_per_unit; the dimension-line scale was measured by hand on the PNG from the
# tick positions at 4-8x zoom: (stem, printed length mm, pixels between its ticks, box, how)
CUBICASA_DIMS = [
    ("high_quality_architectural-769", 14815, 621.5, [0.06, 0.95, 0.472, 0.99],
     "bottom chain 6100+4715+4000, ticks x=91, 347, 543.8, 712.5 (single parts 23.74-23.90 mm/px)"),
    ("high_quality_architectural-14874", 10930, 400.0, [0.185, 0.92, 0.78, 0.97],
     "bottom dimension 10930 between ticks x=125.8 and 525.8"),
    ("high_quality_architectural-14561", 8654, 532.5, [0.066, 0.04, 0.534, 0.062],
     "top chain 1800 / 8654 / 3405 / 2000: ticks x=104.3, 215, 636.8, 760, 846.3 (all 16.23-16.26 mm/px)"),
    ("high_quality_architectural-14087", 14200, 831.0, [0.035, 0.8, 0.49, 0.84],
     "bottom dimension 14200 between ticks x=65 and 896"),
]  # fmt: skip
AREA_TEXT = re.compile(r"(\d+[.,]\d+)\s*m²")


def load(path):
    return json.loads(Path(path).read_text())


def frac(box, w, h):
    return [
        round(box[0] / w, 5),
        round(1 - box[3] / h, 5),
        round(box[2] / w, 5),
        round(1 - box[1] / h, 5),
    ]


def ifc_values(gold, cls):
    """(drawn_value, ifc_value, all_rooms_drawn) for the sheet's storey."""
    note = next(n for n in gold["notes"] if n.startswith("ifc_totals"))
    totals = json.loads(note[note.index("{") :])
    storey = gold["plans"][0]["storey"]
    t = totals.get(storey, {})
    if cls == "space":
        return len(gold["rooms"]), int(t.get("space.n", 0)), storey
    drawn = sum(
        1
        for e in gold["elements"]
        if e["class"] == cls and e["attrs"].get("storey") == storey
    )
    return drawn, int(t.get(cls + ".n", 0)), storey


def ifc_entry(gold, idx, cls, quantity, rule, kind, seen):
    drawn, ifcv, storey = ifc_values(gold, cls)
    box = gold["plans"][0]["box"]
    unit = "rooms" if cls == "space" else "count"
    return {
        "id": f"c{idx}",
        "quantity": quantity,
        "subject": {
            "kind": "sheet" if cls == "space" else "class",
            "ref": None if cls == "space" else cls,
        },
        "status": "conflict" if drawn != ifcv else "agree",
        "tolerance": 0,
        "values": [
            {
                "value": drawn,
                "unit": unit,
                "method": "plan_drawing",
                "page": 1,
                "box": box,
            },
            {"value": ifcv, "unit": unit, "method": "ifc_model", "page": 1, "box": box},
        ],
        "resolution": {
            "rule": rule,
            "value": ifcv if kind == "foreign_rooms" else drawn,
        }
        if "no rule" not in rule
        else None,
        "note": f"storey {storey}: {seen}",
    }


def ifc_agree(gold, start, limit):
    """Counts that agree (drawn == IFC, > 0) for doors, windows, stairs, spaces on one sheet."""
    out = []
    for cls in ("door", "window", "stair", "space"):
        drawn, ifcv, storey = ifc_values(gold, cls)
        if cls == "space":
            drawn = sum(1 for r in gold["rooms"] if not r["attrs"].get("foreign"))
        if drawn == ifcv and drawn > 0:
            box = gold["plans"][0]["box"]
            unit = "rooms" if cls == "space" else "count"
            out.append(
                {
                    "id": f"c{start + len(out)}",
                    "quantity": "room_count" if cls == "space" else "element_count",
                    "subject": {
                        "kind": "sheet" if cls == "space" else "class",
                        "ref": None if cls == "space" else cls,
                    },
                    "status": "agree",
                    "tolerance": 0,
                    "values": [
                        {
                            "value": drawn,
                            "unit": unit,
                            "method": "plan_drawing",
                            "page": 1,
                            "box": box,
                        },
                        {
                            "value": ifcv,
                            "unit": unit,
                            "method": "ifc_model",
                            "page": 1,
                            "box": box,
                        },
                    ],
                    "resolution": {"rule": "both methods agree", "value": drawn},
                    "note": f"storey {storey}",
                }
            )
    return out[:limit]


def printed_areas(dataset, gold):
    """[(room, printed m2, text box fractions)] for the printed 'x,xx m2' texts of a swiss PDF."""
    pdf = pdfium.PdfDocument(Path(dataset) / gold["file"])
    page = pdf[0]
    tp = page.get_textpage()
    w, h = page.get_size()
    polys = [
        (Polygon([(x * w, (1 - y) * h) for x, y in r["polygon"]]).buffer(0), r)
        for r in gold["rooms"]
        if r["polygon"]
    ]
    found = []
    for obj in page.get_objects():
        if obj.type != raw.FPDF_PAGEOBJ_TEXT:
            continue
        n = raw.FPDFTextObj_GetText(obj.raw, tp.raw, None, 0)
        if n <= 2:
            continue
        buf = (ctypes.c_ushort * n)()
        raw.FPDFTextObj_GetText(
            obj.raw, tp.raw, ctypes.cast(buf, ctypes.POINTER(ctypes.c_ushort)), n
        )
        text = (
            bytes(memoryview(buf).cast("B")).decode("utf-16-le").rstrip("\x00").strip()
        )
        m = AREA_TEXT.fullmatch(text)
        if not m:
            continue
        left, bottom, right, top = obj.get_bounds()
        centre = Point((left + right) / 2, (bottom + top) / 2)
        inside = [(p.area, r) for p, r in polys if p.contains(centre)]
        if inside:
            room = min(inside, key=lambda x: x[0])[1]
            found.append(
                (
                    room,
                    float(m.group(1).replace(",", ".")),
                    frac((left, bottom, right, top), w, h),
                )
            )
    return found


def swiss_agree(dataset, gold, limit):
    out = []
    for room, printed, tbox in printed_areas(dataset, gold):
        if room["attrs"]["cutouts"] or room["area_m2"] < 2:
            continue  # nested outlines and tiny rooms: the printed value is rounded, not a method
        rel = printed / room["area_m2"] - 1
        out.append(
            {
                "id": f"c{len(out) + 1}",
                "quantity": "room_area",
                "subject": {"kind": "room", "ref": room["id"]},
                "status": "agree" if abs(rel) <= 0.02 else "conflict",
                "tolerance": 0.02,
                "values": [
                    {
                        "value": printed,
                        "unit": "m2",
                        "method": "printed_label",
                        "page": 1,
                        "box": tbox,
                    },
                    {
                        "value": room["area_m2"],
                        "unit": "m2",
                        "method": "polygon_x_scale",
                        "page": 1,
                        "box": room["box"],
                    },
                ],
                "resolution": {"rule": "both methods agree", "value": printed},
                "note": f"room {room['attrs']['number']} {room['label']}: relative difference {rel:+.2%}",
            }
        )
    assert all(e["status"] == "agree" for e in out), (
        "a real swiss conflict turned up: judge it by hand"
    )
    return out[:: max(1, len(out) // limit)][:limit]


def cubicasa_agree(gold, mm, px, box, how):
    printed = gold["scale"]["m_per_unit"]
    dims = mm / 1000 / px
    rel = printed / dims - 1
    return {
        "id": "c1",
        "quantity": "scale",
        "subject": {"kind": "sheet", "ref": None},
        "status": "agree" if abs(rel) <= 0.02 else "conflict",
        "tolerance": 0.02,
        "values": [
            {"value": printed, "unit": "m/px", "method": "printed_label", "page": 1,
             "box": [0.0, 0.0, 1.0, 1.0]},
            {"value": round(dims, 6), "unit": "m/px", "method": "dimension_lines", "page": 1,
             "box": box},
        ],
        "resolution": {"rule": "both methods agree", "value": printed},
        "note": f"scale from printed room areas (gold) vs dimension lines ({how}); {rel:+.1%}",
    }  # fmt: skip


def render(source, out, gold, entry, cls):
    """Page with the plan box, and the elements or rooms the drawn value counts, both values as caption."""
    if str(source).endswith(".pdf"):
        page = pdfium.PdfDocument(source)[0]
        img = page.render(scale=1.6).to_pil().convert("RGB")
    else:
        img = Image.open(source).convert("RGB")
        img.thumbnail((2000, 2000))
    d = ImageDraw.Draw(img)
    w, h = img.size
    pbox = gold["plans"][0]["box"] if gold.get("plans") else None
    if pbox:
        d.rectangle(
            [pbox[0] * w, pbox[1] * h, pbox[2] * w, pbox[3] * h],
            outline=(230, 0, 0),
            width=4,
        )
    storey = gold["plans"][0]["storey"] if gold.get("plans") else None
    if cls == "space":
        for r in gold["rooms"]:
            colour = (230, 0, 0) if r["attrs"].get("foreign") else (0, 150, 0)
            d.polygon(
                [(x * w, y * h) for x, y in r["polygon"]], outline=colour, width=3
            )
    elif cls:
        for e in gold["elements"]:
            if e["class"] == cls and e["attrs"].get("storey") == storey:
                b = e["box"]
                d.rectangle(
                    [b[0] * w - 6, b[1] * h - 6, b[2] * w + 6, b[3] * h + 6],
                    outline=(0, 90, 255),
                    width=4,
                )
    v = entry["values"]
    caption = f"{entry['quantity']} {cls or ''}: {v[0]['method']}={v[0]['value']} vs {v[1]['method']}={v[1]['value']}"
    d.rectangle([0, 0, w, 48], fill=(255, 255, 255))
    d.text((8, 8), caption, fill=(0, 0, 0))
    d.text((8, 26), entry["note"][:200], fill=(0, 0, 0))
    img.save(out)


# Part 2 lines (kind "conflict"): (stem, question, unit, type, dataset id or None, answer from, why)
# answer_from: "ifc" = the IFC-side value of the entry, "drawn" = the drawn value, or a number
EXTRAS = [
    ("bimspeed-gdynia_ruchu-oporu-18_plan-03-0", "space", 89373,
     "What is the total net floor area of all rooms (spaces) on '0', in m²?", "m2", "area"),
    ("rwth-digitalhub_digitalhub-fm-arc-v2_plan-01-b01-okrd", "space", 88077,
     "What is the total net floor area of all rooms (spaces) on 'B01_OKRD', in m²?", "m2", "area"),
    ("rwth-digitalhub_digitalhub-fm-arc-v2_plan-03-e01-okrd", "space", 88219,
     "What is the total net floor area of all rooms (spaces) on 'E01_OKRD', in m²?", "m2", "area"),
    ("bimspeed-gdynia_ruchu-oporu-18_plan-03-0", "space", None,
     "How many rooms are there on the storey '0' of this model?", "count", "count"),
    ("rwth-digitalhub_digitalhub-fm-arc-v2_plan-01-b01-okrd", "space", None,
     "How many rooms are there on the storey 'B01_OKRD' of this model?", "count", "count"),
    ("rwth-digitalhub_digitalhub-fm-arc-v2_plan-03-e01-okrd", "space", None,
     "How many rooms are there on the storey 'E01_OKRD' of this model?", "count", "count"),
    ("bimspeed-vitoria_ald26-before_plan-01-p0", "column", None,
     "How many columns are shown on the floor plan of 'P0'?", "count", "count"),
    ("bimspeed-vitoria_ald26-project_plan-01-p0", "column", None,
     "How many columns are shown on the floor plan of 'P0'?", "count", "count"),
    ("bimspeed-gdynia_ruchu-oporu-18_plan-03-0", "window", None,
     "How many windows are shown on the floor plan of '0'?", "count", "count"),
    ("bimspeed-gdynia_ruchu-oporu-18_plan-02-1", "window", None,
     "How many windows are shown on the floor plan of '-1'?", "count", "count"),
    ("bsc-esplanades_1807-ep-ar-v18_plan-02-2-korrus", "window", None,
     "How many windows are shown on the floor plan of '2.korrus'?", "count", "count"),
    ("tuwien-escape-route_real-world-escape-route-test-model-zdb_plan-05-dg1", "window", None,
     "How many windows are shown on the floor plan of 'DG1'?", "count", "count"),
]  # fmt: skip


def extras(dataset_rows):
    """Conflict lines for Part 2; the disputed values come from the gold, never typed in."""
    lines = []
    for n, (stem, cls, dataset_id, question, unit, kind) in enumerate(EXTRAS):
        gold = load(f"{GOLD}/{IFC}/{stem}.json")
        assert gold["split"] == "dev"
        if kind == "area":
            every = round(sum(r["area_m2"] for r in gold["rooms"]), 2)
            own = round(
                sum(
                    r["area_m2"] for r in gold["rooms"] if not r["attrs"].get("foreign")
                ),
                2,
            )
            answer, values = own, [every, own]
            why = "spaces of other storeys are drawn on the sheet; the question is about the storey"
        else:
            drawn, ifcv, _ = ifc_values(gold, cls)
            rule = next(
                r for st, c, _q, r, _k, _s in IFC_CONFLICTS if st == stem and c == cls
            )
            values = [drawn, ifcv]
            answer = ifcv if cls == "space" and "storey" in rule else drawn
            why = f"{cls} count: plan_drawing {drawn} vs ifc_model {ifcv}; {rule}"
        row = dataset_rows.get(dataset_id) if dataset_id else None
        if row:
            assert abs(row["answer"] - answer) < 0.01, (
                dataset_id,
                row["answer"],
                answer,
            )
        lines.append({
            "path": gold["file"], "question": question, "answer": answer, "unit": unit,
            "type": "area" if kind == "area" else "count", "id": 1001001 + n,
            "source": "ifc_models", "language": "en", "template": f"conflict_{cls}_{kind}",
            "group": None, "split": "dev", "kind": "conflict", "origin_id": dataset_id,
            "expect": {"answer": answer, "conflict_values": values}, "why": why,
        })  # fmt: skip
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/stoa/full/junction-dataset")
    ap.add_argument("--out", default=f"{GOLD}/_conflicts")
    ap.add_argument("--overlays", default=f"{GOLD}/_overlays/conflicts")
    ap.add_argument("--swiss-files", type=int, default=15)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    Path(args.overlays).mkdir(parents=True, exist_ok=True)
    lines = []
    summary = collections.Counter()

    by_file = collections.defaultdict(list)
    for stem, cls, quantity, rule, kind, seen in IFC_CONFLICTS:
        by_file[stem].append((cls, quantity, rule, kind, seen))
    for stem, items in by_file.items():
        gold = load(f"{GOLD}/{IFC}/{stem}.json")
        assert gold["split"] == "dev", stem
        entries = []
        for i, (cls, quantity, rule, kind, seen) in enumerate(items, 1):
            entry = ifc_entry(gold, i, cls, quantity, rule, kind, seen)
            assert entry["status"] == "conflict", (stem, cls)
            entries.append(entry)
            render(
                Path(args.dataset) / gold["file"],
                f"{args.overlays}/{stem}__{cls}.png",
                gold,
                entry,
                cls,
            )
        # agree entries of the same sheet are added below with the other agree entries
        lines.append({"file": gold["file"], "split": "dev", "conflicts": entries})
        summary["conflict"] += len(entries)

    for stem, mm, px, box, how in CUBICASA_DIMS:
        gold = load(f"{GOLD}/cubicasa5k/{stem}.json")
        assert gold["split"] == "dev"
        entry = cubicasa_agree(gold, mm, px, box, how)
        assert entry["status"] == "agree", (stem, entry["note"])
        lines.append({"file": gold["file"], "split": "dev", "conflicts": [entry]})
        summary["agree"] += 1

    ifc_seen = {s for s, *_ in IFC_CONFLICTS}
    for path in sorted(Path(f"{GOLD}/{IFC}").glob("*.json")):
        gold = load(path)
        if gold["split"] != "dev" or path.stem in ifc_seen:
            continue
        if "ifc_totals" not in " ".join(gold["notes"]):
            continue
        entries = ifc_agree(gold, 1, 3)
        if entries:
            lines.append({"file": gold["file"], "split": "dev", "conflicts": entries})
            summary["agree"] += len(entries)

    swiss = sorted(
        p
        for p in Path(f"{GOLD}/swiss_dwellings").glob("*.json")
        if not p.name.endswith(".png.json")
    )
    taken = 0
    for path in swiss:
        gold = load(path)
        if gold["split"] != "dev" or "printed_areas" not in gold["scale"]["evidence"]:
            continue
        if hash_slot(path.stem) % 16:
            continue  # deterministic spread over the sheets that print areas
        entries = swiss_agree(args.dataset, gold, 2)
        if entries:
            lines.append({"file": gold["file"], "split": "dev", "conflicts": entries})
            summary["agree"] += len(entries)
            taken += 1
        if taken >= args.swiss_files:
            break
    (out / "conflicts.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines)
    )
    rows = {}
    for line in Path("data/stoa/split/dev.jsonl").read_text().splitlines():
        r = json.loads(line)
        rows[r["id"]] = r
    ex = extras(rows)
    (out / "extras.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in ex)
    )
    print(dict(summary), "files", len(lines), "extras", len(ex))


def hash_slot(text):
    return sum(ord(c) * (i + 1) for i, c in enumerate(text))


if __name__ == "__main__":
    main()
