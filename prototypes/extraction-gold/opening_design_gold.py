# /// script
# requires-python = ">=3.13"
# dependencies = ["pdfplumber==0.11.7"]
# ///
"""Extraction gold (extraction_v1 + `tables`) for the three opening_design sheets that have questions.

  A-801 Door and Finish Schedules (Sports_Complex, dev):  4 tables, truth "tables"
  A700 SCHEDULES (CTR, eval split):                        3 tables, truth "tables"
  A-701 Restrooms (Sports_Complex, dev):                   no schedule; the fixtures of the plans
                                                           the questions ask about, truth "elements"

Cells come from the PDF text layer: pdfplumber finds each table from its ruling lines and reads the
text inside every cell, so blank cells stay blank (the trap of plain text extraction: columns
shift). What the text layer gets wrong or does not hold goes in as data below (HEADERS, COLUMN_FIX,
CELL_FIX, DROP_RED) so a rerun writes the same files. Header rows that span several printed lines
or have a group heading ("Door" over "Width") are written by hand as one string per column. The
A-701 fixtures are not text: they are block symbols, so their boxes were read off the drawing at
100 dpi (crop origin + pixel box, converted below); every box was checked in the overlay.

The rule check (printed at the end): the dataset's counting rules applied to the written JSON only
must reproduce all 64 answers. A miss is a gold error or a suspect dataset answer.
Run: uv run prototypes/extraction-gold/opening_design_gold.py [--dataset <root>] [--split <dir>]
     [--out <dir>] [--overlays <dir>]
Licence of the drawings: see data/opening_design/LICENSE.md in the dataset.
"""

import argparse
import json
import re
from pathlib import Path

import pdfplumber
from PIL import ImageDraw

REPO = Path(__file__).resolve().parents[2]
PREFIX = "data/opening_design/"
SPORTS = "Sports_Complex/Sheets - Current Set/"
A801 = SPORTS + "A-801 - Door and Finish Schedules & Wall Types.pdf"
A701 = SPORTS + "A-701 - Restrooms.pdf"
A700 = "CTR/Most Current Set/Full size sheets/A700 - SCHEDULES.pdf"

# Table specs. region: pt box (page frame after /Rotate 90, origin top left) that holds only this
# table's ruling lines; body_top: rows above it are headers/titles (written by hand in `columns`).
TABLES = {
    A801: [
        {
            "id": "t1",
            "title": "Door Schedule",
            "region": (130, 100, 930, 670),
            "body_top": 170,
            "columns": [
                "Door Number",
                "Room Name",
                "Room Number",
                "Door Width",
                "Door Height",
                "Door Type",
                "Door Matl",
                "Frame Matl",
                "Frame Type",
                "Hardware Group - see Specs",
                "Notes",
            ],
        },
        {
            "id": "t2",
            "title": "KEYNOTE - DOOR SCHEDULE",
            "key_column": 1,
            "region": (950, 100, 1560, 430),
            "body_top": 170,
            "columns": ["Category", "Keynote", "Note"],
        },
        {
            "id": "t3",
            "title": "FINISH ROOM SCHEDULE",
            "key_column": 1,
            "region": (130, 760, 1330, 1400),
            "body_top": 860,
            "columns": [
                "Area",
                "Room Number",
                "Room Name",
                "Floor Finish",
                "Base Finish",
                "Wall Finishes North Wall",
                "Wall Finishes South Wall",
                "Wall Finishes East Wall",
                "Wall Finishes West Wall",
                "Ceiling Finish",
                "Comments",
            ],
        },
        {
            "id": "t4",
            "title": "FINISH KEY",
            "region": (130, 1420, 830, 1720),
            "body_top": 1500,
            "columns": ["Finish Key", "Finish - Description"],
        },
    ],
    A700: [
        {
            "id": "t1",
            "title": "DOOR SCHEDULE - NUMBER",
            "key_column": 3,
            "region": (125, 80, 1445, 820),
            "body_top": 140,
            "columns": [
                "From Room: Name",
                "Type Mark",
                "Level",
                "Mark",
                "Type",
                "Width",
                "Height",
                "Fire Rating",
                "Door Type",
                "Door Material",
                "Frame Type",
                "Frame Material",
                "Type Comments",
                "Comments",
                "Hardware Set",
            ],
        },
        {
            "id": "t2",
            "title": "DOOR SCHEDULE - TYPE",
            "key_column": 1,
            "region": (125, 860, 1230, 1290),
            "body_top": 910,
            "columns": [
                "Count",
                "Type Mark",
                "Type",
                "Width",
                "Height",
                "Fire Rating",
                "Door Type",
                "Door Material",
                "Frame Type",
                "Frame Material",
                "Type Comments",
                "DS_Hardware_ Set_(SFT)",
            ],
        },
        {
            "id": "t3",
            "title": "WINDOW SCHEDULE - SIMPLIFIED",
            "region": (2140, 75, 2540, 245),
            "body_top": 140,
            "columns": ["Type Mark", "Type", "Count", "Width", "Height"],
        },
    ],
}
# The red revision cloud and its "07/15/2020" tag sit over the Comments column of the A700 door
# schedule (rows 111.B, 112.A): drawn markup, not table content. Those objects are dropped.
DROP_RED = {A700}
# Text-layer cells replaced after reading the render: (file, table id, body row, column) -> text.
# Empty so far: every cell of every table matched the render (see the report).
CELL_FIX: dict[tuple[str, str, int, str], str | None] = {}

# A-701: crop origins (px at 100 dpi) and pixel boxes read off the drawing. Plan id = detail number.
A701_PLANS = {
    "p6A": {"title": "RESTROOMS", "origin": (300, 2020), "box": (25, 35, 562, 718)},
    "p6B": {
        "title": "RESTROOM WITH SHOWER",
        "origin": (380, 1470),
        "box": (42, 25, 584, 425),
    },
    "p6E": {
        "title": "ADA WATER CLOSET TYP.",
        "origin": (300, 290),
        "box": (183, 42, 435, 295),
    },
    "p6D": {
        "title": "WATER CLOSET TYP.",
        "origin": (440, 820),
        "box": (43, 27, 293, 178),
    },
}
A701_FIXTURES = [  # (plan, class, source label, pixel box in the plan's crop)
    ("p6A", "toilet", "water closet", (445, 228, 532, 372)),
    ("p6A", "toilet", "water closet", (445, 378, 532, 512)),
    ("p6A", "sink", "lavatory", (183, 287, 272, 368)),
    ("p6A", "sink", "lavatory", (183, 380, 272, 455)),
    ("p6B", "toilet", "water closet", (78, 286, 170, 418)),
    ("p6B", "sink", "lavatory", (297, 350, 388, 420)),
    ("p6B", "shower", "shower", (430, 262, 586, 418)),
    ("p6E", "toilet", "water closet", (190, 180, 318, 268)),
    ("p6D", "toilet", "water closet", (45, 60, 175, 148)),
]
A701_SCALE_M_PER_PT = (
    2 / 72 * 0.3048
)  # 1/2" = 1'-0": one paper pt is 2/72 ft of building


def clean(text: str | None) -> str | None:
    text = " ".join((text or "").split())
    return text or None


def is_red(obj: dict) -> bool:
    for key in ("stroking_color", "non_stroking_color"):
        c = obj.get(key)
        if (
            isinstance(c, (tuple, list))
            and len(c) == 3
            and c[0] > 0.8
            and c[1] < 0.2
            and c[2] < 0.2
        ):
            return True
    return False


def read_tables(page, file: str, specs: list[dict]) -> list[dict]:
    width, height = float(page.width), float(page.height)
    if file in DROP_RED:
        page = page.filter(lambda o: not is_red(o))
    out = []
    for spec in specs:
        crop = page.crop(spec["region"])
        found = crop.find_tables()
        if not found:
            raise SystemExit(f"{file} {spec['id']}: no table found in {spec['region']}")
        rows = []
        for table in found:
            for row in table.rows:
                if row.bbox[1] >= spec["body_top"] - 1:
                    rows.append(row)
        rows.sort(key=lambda r: r.bbox[1])
        body = []
        for number, row in enumerate(rows, 1):
            cells = [crop.crop(c).extract_text() for c in row.cells if c is not None]
            if len(cells) != len(spec["columns"]):
                raise SystemExit(
                    f"{file} {spec['id']} row {number}: {len(cells)} cells"
                )
            values = [clean(c) for c in cells]
            for index, column in enumerate(spec["columns"]):
                key = (file, spec["id"], number, column)
                if key in CELL_FIX:
                    values[index] = CELL_FIX[key]
            x0, y0, x1, y1 = row.bbox
            body.append({"cells": values, "box": frac(x0, y0, x1, y1, width, height)})
        x0 = min(t.bbox[0] for t in found)
        y0 = min(t.bbox[1] for t in found)
        x1 = max(t.bbox[2] for t in found)
        y1 = max(t.bbox[3] for t in found)
        out.append(
            {
                "id": spec["id"],
                "page": 1,
                "box": frac(x0, y0, x1, y1, width, height),
                "title": spec["title"],
                "columns": spec["columns"],
                "rows": body,
                **({"key_column": spec["key_column"]} if "key_column" in spec else {}),
            }
        )
    return out


def frac(x0, y0, x1, y1, width, height) -> list[float]:
    return [
        round(x0 / width, 5),
        round(y0 / height, 5),
        round(x1 / width, 5),
        round(y1 / height, 5),
    ]


def px_box(
    origin: tuple[int, int], box: tuple[int, int, int, int], width: float, height: float
):
    """A pixel box at 100 dpi inside a crop that starts at `origin` -> page fractions."""
    k = 72 / 100
    ox, oy = origin
    x0, y0, x1, y1 = box
    return frac(
        (ox + x0) * k, (oy + y0) * k, (ox + x1) * k, (oy + y1) * k, width, height
    )


def base(file: str, split: str, page, truth: str) -> dict:
    return {
        "schema": "extraction_v1",
        "file": PREFIX + file,
        "split": split,
        "truth": truth,
        "pages": [
            {
                "page": 1,
                "width": float(page.width),
                "height": float(page.height),
                "unit": "pt",
            }
        ],
        "scale": {"status": "no_scale"},
        "plans": [],
        "elements": [],
        "rooms": [],
        "apartments": [],
        "counts": None,
        "tables": [],
        "notes": [],
    }


def build_schedule(page, file: str, split: str) -> dict:
    doc = base(file, split, page, "tables")
    doc["tables"] = read_tables(page, file, TABLES[file])
    doc["notes"] = [
        (
            "Header text is the printed header; a group heading is put in front of its columns "
            "(Door Width, Frame Matl, Wall Finishes North Wall); two-line headers use one space."
        ),
        "Cells are the printed text with whitespace collapsed; null = blank cell; '-' is printed.",
    ]
    if file == A801:
        doc["notes"] += [
            (
                "KEYNOTE - DOOR SCHEDULE is one table: the printed header over three groups "
                "(DOOR/FRAME/NOTES rows), the gaps between the groups are not rows."
            ),
            "FINISH KEY: header box and body box are one table.",
            "The sheet scale is 'As indicated' (per detail): scale status no_scale.",
        ]
    else:
        doc["notes"] += [
            (
                "A red revision cloud and its '07/15/2020' tag sit over the Comments column of the "
                "DOOR SCHEDULE - NUMBER; they are markup, not cells (rows 111.B and 112.A are blank)."
            ),
            "No printed scale on the sheet (the detail drawings carry their own).",
        ]
    return doc


def build_restrooms(page, file: str, split: str) -> dict:
    doc = base(file, split, page, "elements")
    width, height = float(page.width), float(page.height)
    doc["scale"] = {
        "status": "scaled",
        "m_per_unit": round(A701_SCALE_M_PER_PT, 6),
        "evidence": ["scale_text"],
        "text": '1/2" = 1\'-0"',
        "source": 'title block: 1/2" = 1\'-0" on a 30 x 42 in sheet, 1 pt = 2/72 ft',
    }
    for plan_id, plan in A701_PLANS.items():
        doc["plans"].append(
            {
                "id": plan_id,
                "page": 1,
                "storey": None,
                "box": px_box(plan["origin"], plan["box"], width, height),
            }
        )
    for number, (plan_id, cls, label, box) in enumerate(A701_FIXTURES, 1):
        origin = A701_PLANS[plan_id]["origin"]
        doc["elements"].append(
            {
                "id": f"e{number}",
                "class": cls,
                "page": 1,
                "plan": plan_id,
                "box": px_box(origin, box, width, height),
                "polygon": None,
                "attrs": {"source_class": f"{label} (block symbol)"},
            }
        )
    doc["notes"] = [
        (
            "Plan ids are the detail numbers: p6A RESTROOMS, p6B RESTROOM WITH SHOWER, and the two "
            "typical water-closet plans p6E (ADA) and p6D. Elevations and sections also draw fixtures "
            "and are not listed."
        ),
        (
            "Fixtures are block symbols without labels in the plan; boxes were read off the drawing. "
            "The two round items left of plan 6A are drinking fountains (no class), not lavatories."
        ),
        "tables: none, the sheet has no schedule.",
    ]
    return doc


# ---- rule check ---------------------------------------------------------------------------------


def col(table: dict, name: str) -> int:
    return table["columns"].index(name)


def rows_of(table: dict) -> list[dict[str, str | None]]:
    return [dict(zip(table["columns"], r["cells"], strict=True)) for r in table["rows"]]


def ft(text: str) -> str:
    return re.sub(r"'\s*-\s*", "'-", text or "")


def sf(text: str | None) -> int | None:
    m = re.fullmatch(r"(\d+) SF", text or "")
    return int(m.group(1)) if m else None


def norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9/\"]+", " ", text.lower()).split())


def answers_a801(doc: dict) -> dict[int, object]:
    t = {x["id"]: rows_of(x) for x in doc["tables"]}
    door, key, fin, fkey = t["t1"], t["t2"], t["t3"], t["t4"]
    by_door = {r["Door Number"]: r for r in door}
    desc = {r["Finish Key"]: r["Finish - Description"] for r in fkey}
    room = {r["Room Number"]: r for r in fin}

    def count(f, rows=door):
        return sum(1 for r in rows if f(r))

    def notes(r):
        return {n.strip() for n in (r["Notes"] or "").split(",")}

    def meaning(codes: str) -> str:
        return " and ".join(desc[c.strip()] for c in codes.split("&"))

    a: dict[int, object] = {89397: len(door)}
    for qid, typ in zip(
        range(89398, 89404), ["A1", "A2", "B1", "B2", "B3", "C1"], strict=True
    ):
        a[qid] = count(lambda r, typ=typ: r["Door Type"] == typ)
    a[89404] = count(lambda r: r["Door Matl"] == "WD-1")
    a[89405] = count(lambda r: r["Frame Matl"] == "STL-1")
    a[89406] = count(lambda r: r["Frame Matl"] in ("AL-1", "AL-2"))
    for qid, n in zip((89407, 89408, 89409), "ABC", strict=True):
        a[qid] = count(lambda r, n=n: n in notes(r))
    a[89410] = count(lambda r: r["Door Width"] == "3' - 0\"")
    a[89411] = count(lambda r: r["Door Height"] == "7' - 0\"")
    a[89412] = count(lambda r: r["Room Number"] == "118")
    a[89413] = count(lambda r: r["Room Number"] == "128")
    a[89414] = ft(by_door["121.A"]["Door Width"])
    a[89415] = by_door["121.A"]["Door Type"]
    a[89416] = (
        f"{ft(by_door['128.B']['Door Width'])} wide x "
        f"{ft(by_door['128.B']['Door Height'])} high"
    )
    a[89417] = by_door["107.A"]["Hardware Group - see Specs"]
    a[89418] = by_door["115.A"]["Door Matl"]
    heights = {
        by_door[n]["Door Height"] for n in ("118.A1", "118.A2", "118.B1", "118.B2")
    }
    a[89419] = ft(heights.pop()) if len(heights) == 1 else "mixed"
    a[89420] = len(fin)
    for qid, n in zip(
        (89421, 89422, 89423, 89424), ("128", "118", "122", "121"), strict=True
    ):
        a[qid] = sf(room[n]["Area"])
    areas = [sf(r["Area"]) for r in fin if sf(r["Area"]) is not None]
    a[89425] = sum(areas)
    a[89426] = sum(sf(r["Area"]) or 0 for r in fin if r["Room Name"] == "OFFICE")
    a[89427] = sum(sf(r["Area"]) or 0 for r in fin if r["Room Name"] == "RESTROOM")
    a[89428] = sum(
        sf(r["Area"]) or 0 for r in fin if "LOCKER" in (r["Room Name"] or "")
    )
    f0 = [r for r in fin if r["Floor Finish"] == "F0"]
    a[89429] = f"{len(f0)} rooms, {sum(sf(r['Area']) or 0 for r in f0)} SF"
    a[89430] = sum(sf(r["Area"]) or 0 for r in fin if r["Floor Finish"] == "F4")
    a[89431] = count(lambda r: r["Base Finish"] == "B2", fin)
    walls = [c for c in fin[0] if c.startswith("Wall Finishes")]
    a[89432] = count(lambda r: all(r[w] == "W1" for w in walls), fin)
    a[89433] = f"{room['113']['Floor Finish']} - {meaning(room['113']['Floor Finish'])}"
    a[89434] = f"{room['128']['Floor Finish']} - {meaning(room['128']['Floor Finish'])}"
    a[89435] = (
        f"{room['128']['Ceiling Finish']} - {meaning(room['128']['Ceiling Finish'])}"
    )
    nw = room["118"]["Wall Finishes North Wall"]
    a[89436] = f"{nw} - {meaning(nw)}"
    big = max((r for r in fin if sf(r["Area"])), key=lambda r: sf(r["Area"]))
    a[89437] = f"Room {big['Room Number']} {big['Room Name']} ({sf(big['Area'])} SF)"
    del key
    return a


def answers_a700(doc: dict) -> dict[int, object]:
    t = {x["id"]: rows_of(x) for x in doc["tables"]}
    typ, win = t["t2"], t["t3"]
    by_mark = {r["Type Mark"]: r for r in typ}
    wby = {r["Type Mark"]: r for r in win}

    def n(r):
        return int(r["Count"])

    a: dict[int, object] = {
        89441: n(by_mark["U01"]),
        89442: n(by_mark["U02"]),
        89443: sum(n(r) for r in typ if "MARVIN ESSENTIAL SLIDING" in r["Type"]),
        89444: sum(
            n(r)
            for r in typ
            if "MARVIN ESSENTIAL SLIDING" in r["Type"] and "3RD FLOOR" in r["Type"]
        ),
        89445: sum(
            n(r) for r in typ if "VISTAGRANDE" in r["Type"] and "1ST FLOOR" in r["Type"]
        ),
        89446: n(by_mark["U41"]),
        89447: sum(n(r) for r in typ),
        89448: sum(n(r) for r in typ if r["Type"].startswith("SWING")),
        89449: n(by_mark["U06"]) + n(by_mark["U44"]),
        89450: by_mark["U01"]["Fire Rating"],
        89451: by_mark["U01"]["Frame Material"],
        89452: n(by_mark["U22"]),
        89453: sum(n(r) for r in win),
        89454: n(wby["SS"]),
        89455: n(wby["RR"]),
        89456: n(wby["QQ"]),
        89457: n(wby["VV"]),
        89458: sum(n(wby[m]) for m in ("SS", "TT", "UU")),
        89459: sum(int(r["Type"][0]) * n(r) for r in win),
    }
    sizes = {(r["Width"], r["Height"]) for r in win}
    w, h = sizes.pop() if len(sizes) == 1 else ("mixed", "mixed")
    a[89460] = f"{w} wide x {h} high"
    return a


def answers_a701(doc: dict) -> dict[int, object]:
    def n(plan: str, cls: str) -> int:
        return sum(
            1 for e in doc["elements"] if e["plan"] == plan and e["class"] == cls
        )

    return {
        89438: n("p6A", "toilet"),
        89439: n("p6A", "sink"),
        89440: f"{n('p6B', 'toilet')} water closet, {n('p6B', 'sink')} lavatory, "
        f"{n('p6B', 'shower')} shower",
    }


def same(got: object, want: object, qid: int) -> bool:
    if isinstance(got, int) and not isinstance(want, str):
        return got == want
    if qid in (
        89433,
        89434,
        89435,
        89436,
        89415,
        89451,
    ):  # the dataset shortens descriptions
        return norm(str(want)).startswith(norm(str(got))) or norm(str(got)).startswith(
            norm(str(want))
        )
    return norm(str(got)) == norm(str(want))


def rule_check(docs: dict[str, dict], questions: dict[int, dict]) -> int:
    got: dict[int, object] = {}
    got.update(answers_a801(docs[A801]))
    got.update(answers_a700(docs[A700]))
    got.update(answers_a701(docs[A701]))
    ok = 0
    for qid in sorted(got):
        want = questions[qid]["answer"]
        if isinstance(want, str) and qid in (89421, 89422, 89423, 89424):
            want = int(re.sub(r"\D", "", want))
        if same(got[qid], want, qid):
            ok += 1
        else:
            print(f"  MISS {qid}: gold gives {got[qid]!r}, dataset says {want!r}")
    missing = sorted(set(questions) - set(got))
    for qid in missing:
        print(f"  NOT CHECKED {qid}")
    print(
        f"rule check: {ok}/{len(questions)} dataset answers reproduced from the gold files"
    )
    return len(questions) - ok


# ---- overlays -----------------------------------------------------------------------------------


def overlay(page, doc: dict, path: Path, dpi: int = 50) -> None:
    img = page.to_image(resolution=dpi).original.convert("RGB")
    w, h = img.size
    d = ImageDraw.Draw(img)

    def rect(box, colour, width):
        d.rectangle(
            [box[0] * w, box[1] * h, box[2] * w, box[3] * h],
            outline=colour,
            width=width,
        )

    for table in doc["tables"]:
        rect(table["box"], (255, 0, 0), 3)
        for index, row in enumerate(table["rows"], 1):
            if index % 5 == 0:
                rect(row["box"], (0, 160, 0), 2)
    for plan in doc["plans"]:
        rect(plan["box"], (255, 0, 0), 3)
    colours = {"toilet": (0, 0, 255), "sink": (0, 160, 0), "shower": (200, 0, 200)}
    for e in doc["elements"]:
        rect(e["box"], colours[e["class"]], 3)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dataset", type=Path, default=REPO / "data/stoa/full/junction-dataset"
    )
    parser.add_argument("--split", type=Path, default=REPO / "data/stoa/split")
    parser.add_argument(
        "--out", type=Path, default=REPO / "data/stoa/extraction_gold/opening_design"
    )
    parser.add_argument(
        "--overlays",
        type=Path,
        default=REPO / "data/stoa/extraction_gold/_overlays/opening_design",
    )
    args = parser.parse_args()

    split_of: dict[str, str] = {}
    for name in ("dev", "eval"):
        for line in (args.split / f"{name}.jsonl").read_text().splitlines():
            q = json.loads(line)
            if "opening_design" in q["path"]:
                split_of[q["path"].removeprefix(PREFIX)] = name
    questions = {}
    for number, line in enumerate(
        (args.dataset / "questions.jsonl").read_text().splitlines(), 1
    ):
        q = json.loads(line)
        if "opening_design" in q["path"]:
            questions[number] = q

    docs: dict[str, dict] = {}
    for file, builder in (
        (A801, build_schedule),
        (A700, build_schedule),
        (A701, build_restrooms),
    ):
        with pdfplumber.open(args.dataset / PREFIX / file) as pdf:
            page = pdf.pages[0]
            doc = builder(page, file, split_of[file])
            docs[file] = doc
            target = args.out / Path(file).with_suffix(".json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
            stem = Path(file).stem.replace(" ", "_")
            overlay(page, doc, args.overlays / f"{stem}.png")
        rows = sum(len(t["rows"]) for t in doc["tables"])
        print(
            f"{target.relative_to(args.out.parent)}: {len(doc['tables'])} tables, {rows} rows, "
            f"{len(doc['elements'])} elements ({doc['split']})"
        )
    raise SystemExit(1 if rule_check(docs, questions) else 0)


if __name__ == "__main__":
    main()
