# /// script
# requires-python = ">=3.13"
# dependencies = ["pypdfium2==5.15.2", "shapely==2.2.0"]
# ///
"""Answer the four swiss_dwellings area questions from the PDF page only (no DXF/SVG/IFC sibling).

Templates (EN/DE/FR/IT): net area of room N.N; total area of rooms labelled X; net area of
apartment A/B/..; total net area of all numbered indoor rooms. Unit m2, one answer_v1 line each.

How: pypdfium2 reads the page's vector paths and text objects. A room is a filled path with stroke
(138,138,138) width 0.37; a unit (apartment) outline is the dashed red path (176,58,46). Scale
comes from "1:100"/"1:200" in the title block (A3 page, 1 pt = 25.4/72 mm of paper).
Rules that matter (found by checking against the dataset answers):
- Room net area = outline minus the polygons nested inside it. A room with cut-outs is ONE compound
  path (several sub-paths): largest ring = outline, the others = holes.
- Read each text object's own text. Cutting page text by bounding box mixes overlapping labels.
- Outdoor = a name in OUTDOOR_NAMES, or fill grey 228 (unnamed balcony strips have no name).
- Floor total: all numbered rooms except outdoor; lifts and stairwells stay IN (the question wording
  says "excluding shafts" but the dataset answer includes them).
- Apartment: rooms whose representative point lies in the unit outline holding the "Whg./App. X"
  label, minus outdoor rooms and fill-243 rooms (lifts, stairs, shafts). Not handled: an apartment
  spread over several outlines (tried "one label = all outlines": fixes 2 questions, breaks 4).
Measured on all 12,016 swiss area questions: 12,012 correct (99.97%) by the dataset's 2% rule;
per-template table in prototypes/pdf-extract/README.md. These rules were found and tuned on the
whole dataset, so this number is NOT a held-out result; use the sealed eval split for that.
Latency: each PDF is parsed once and that time is shared equally by the file's questions, plus the
measured time of the question itself.
Known failures: apartments spread over several outlines (4 questions); rooms drawn without a
number; PDFs with other fills or stroke styles.
Licence: swiss_dwellings is CC BY 4.0 (Archilyse AG); put the credit in any picture, not in the JSONL.
Run: uv run prototypes/pdf-extract/swiss_areas.py --dataset <root with questions.jsonl> --out a.jsonl
"""

import argparse
import ctypes
import json
import re
import time
from collections import defaultdict
from pathlib import Path

import pypdfium2 as pdfium
from pypdfium2 import raw
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

OUTDOOR_NAMES = {
    "Balkon", "Balcon", "Balcone", "Loggia", "Terrasse", "Terrazza", "Sitzplatz", "Garten",
    "Patio", "Arkade", "Jardin d'hiver", "Wintergarten", "Giardino d'inverno",
}  # fmt: skip
ROOM_STROKE, ROOM_WIDTH = (138, 138, 138), 0.37
UNIT_STROKE = (176, 58, 46)
OUTDOOR_FILL, SHAFT_FILL = 228, 243
NUMBER = re.compile(r"[A-Z]*\d+\.\d+")
UNIT_LABEL = re.compile(r"^(?:Whg|Wohnung|App|Appt|Appartement|Alloggio)\.?\s+([A-Z])$")
TOTAL_Q = re.compile(r"all numbered indoor|nummerierten|numérotées|numerati")
APT_Q = re.compile(r"(?:apartment|Wohnung|appartement|appartamento) ([A-Z])\b")
ROOM_Q = re.compile(r"(?:room|Raum|salle|pièce|locale|local) ([A-Z]*\d+\.\d+)")
LABEL_Q = re.compile(r"[«'] ?(.+?) ?[»']")
MAX_BOXES = 200


def classify(text: str) -> tuple[str, str | None]:
    if TOTAL_Q.search(text):
        return "total", None
    for kind, pattern in (("apt", APT_Q), ("room", ROOM_Q), ("label", LABEL_Q)):
        if m := pattern.search(text):
            return kind, m.group(1)
    return "other", None


def _color(obj, getter) -> tuple[int, int, int]:
    r, g, b, a = (ctypes.c_uint() for _ in range(4))
    getter(obj.raw, r, g, b, a)
    return r.value, g.value, b.value


def _rings(obj) -> list[list[tuple[float, float]]]:
    """Sub-paths of a path object in page coordinates."""
    matrix = raw.FS_MATRIX()
    raw.FPDFPageObj_GetMatrix(obj.raw, matrix)
    rings: list[list[tuple[float, float]]] = []
    for i in range(raw.FPDFPath_CountSegments(obj.raw)):
        seg = raw.FPDFPath_GetPathSegment(obj.raw, i)
        x, y = ctypes.c_float(), ctypes.c_float()
        raw.FPDFPathSegment_GetPoint(seg, x, y)
        if raw.FPDFPathSegment_GetType(seg) == raw.FPDF_SEGMENT_MOVETO or not rings:
            rings.append([])
        rings[-1].append((
            matrix.a * x.value + matrix.c * y.value + matrix.e,
            matrix.b * x.value + matrix.d * y.value + matrix.f,
        ))  # fmt: skip
    return rings


def _outline_and_holes(rings) -> tuple[Polygon, list[Polygon]] | None:
    polys = [p for r in rings if len(r) >= 3 and not (p := Polygon(r).buffer(0)).is_empty]
    if not polys:
        return None
    polys.sort(key=lambda p: -p.area)
    outline = polys[0]
    return outline, [p for p in polys[1:] if outline.buffer(0.3).contains(p)]


def _object_text(obj, textpage) -> str:
    n = raw.FPDFTextObj_GetText(obj.raw, textpage.raw, None, 0)
    if n <= 2:
        return ""
    buf = (ctypes.c_ushort * n)()
    raw.FPDFTextObj_GetText(
        obj.raw, textpage.raw, ctypes.cast(buf, ctypes.POINTER(ctypes.c_ushort)), n
    )
    return bytes(memoryview(buf).cast("B")).decode("utf-16-le").rstrip("\x00").strip()


class Page:
    """Rooms, unit outlines and room texts of one swiss floor-plan PDF."""

    def __init__(self, path: Path):
        page = pdfium.PdfDocument(str(path))[0]
        self.width, self.height = page.get_size()
        self.rotation = page.get_rotation()
        textpage = page.get_textpage()
        outlines, self.units, texts = [], [], []
        for obj in page.get_objects():
            if obj.type == raw.FPDF_PAGEOBJ_PATH:
                stroke = _color(obj, raw.FPDFPageObj_GetStrokeColor)
                width = ctypes.c_float()
                raw.FPDFPageObj_GetStrokeWidth(obj.raw, width)
                mode, _ = ctypes.c_int(), ctypes.c_int()
                raw.FPDFPath_GetDrawMode(obj.raw, mode, _)
                if (
                    stroke == ROOM_STROKE
                    and round(width.value, 2) == ROOM_WIDTH
                    and mode.value == 2
                ):
                    if shape := _outline_and_holes(_rings(obj)):
                        fill = _color(obj, raw.FPDFPageObj_GetFillColor)[0]
                        outlines.append((*shape, fill))
                elif (
                    stroke == UNIT_STROKE
                    and abs(width.value - 1.28) < 0.05
                    and (shape := _outline_and_holes(_rings(obj)))
                ):
                    self.units.append(shape[0])
            elif obj.type == raw.FPDF_PAGEOBJ_TEXT:
                left, bottom, right, top = obj.get_bounds()
                if text := _object_text(obj, textpage):
                    texts.append(((left + right) / 2, (bottom + top) / 2, text))
        full = textpage.get_text_range()
        scale = int(m.group(1)) if (m := re.search(r"1\s*:\s*(\d+)", full)) else 100
        self.m2_per_pt2 = (25.4 / 72 * scale / 1000) ** 2
        self.rooms = self._build_rooms(outlines, texts)

    def _build_rooms(self, outlines, texts) -> list[dict]:
        shapes = [o[0] for o in outlines]
        owner: dict[int, list[tuple[float, str]]] = defaultdict(list)
        for x, y, text in texts:
            inside = [
                (shapes[i].area, i) for i in range(len(shapes)) if shapes[i].contains(Point(x, y))
            ]
            if inside:
                owner[min(inside)[1]].append((y, text))
        rooms = []
        for i, lines in owner.items():
            outline, holes, fill = outlines[i]
            words = [t for _, t in sorted(lines, reverse=True)]
            number = next((t for t in words if NUMBER.fullmatch(t)), None)
            unit = next((m.group(1) for t in words if (m := UNIT_LABEL.match(t))), None)
            names = [t for t in words if t != number and not UNIT_LABEL.match(t) and "m²" not in t]
            nested = holes + [
                o for j, o in enumerate(shapes)
                if j != i and o.area < outline.area and outline.buffer(0.3).contains(o)
            ]  # fmt: skip
            net = outline.difference(unary_union(nested)).area if nested else outline.area
            rooms.append({
                "outline": outline, "fill": fill, "number": number, "unit": unit,
                "name": names[0] if names else None, "area": net * self.m2_per_pt2,
            })  # fmt: skip
        return rooms

    def box(self, shape: Polygon) -> list[float]:
        """Page fractions [x0, y0, x1, y1], origin top left, rotation-aware (clockwise degrees)."""
        left, bottom, right, top = shape.bounds
        w, h = self.width, self.height
        if self.rotation in (90, 270):  # get_size() is already the rotated page
            w, h = h, w
        corners = [(left, bottom), (right, bottom), (left, top), (right, top)]
        turned = []
        for x, y in corners:
            u, v = x / w, 1 - y / h
            for _ in range(self.rotation // 90):
                u, v = 1 - v, u
            turned.append((u, v))
        xs, ys = [c[0] for c in turned], [c[1] for c in turned]
        return [round(min(max(v, 0.0), 1.0), 4) for v in (min(xs), min(ys), max(xs), max(ys))]


def _is_outdoor(room: dict) -> bool:
    return room["name"] in OUTDOOR_NAMES or room["fill"] == OUTDOOR_FILL


def answer_rooms(page: Page, kind: str, key: str | None) -> list[dict]:
    """The rooms whose areas are summed for one question."""
    numbered = [r for r in page.rooms if r["number"]]
    if kind == "room":
        return [r for r in numbered if r["number"] == key]
    if kind == "label":
        return [r for r in numbered if r["name"] == key]
    if kind == "total":
        return [r for r in numbered if r["name"] not in OUTDOOR_NAMES and r["fill"] != OUTDOOR_FILL]
    labelled = [r for r in page.rooms if r["unit"] == key]
    if not labelled:
        return []
    point = labelled[0]["outline"].representative_point()
    holding = [u for u in page.units if u.contains(point)]
    if not holding:
        return []
    outlines = [min(holding, key=lambda u: u.area)]
    return [
        r for r in numbered
        if any(u.contains(r["outline"].representative_point()) for u in outlines)
        and not _is_outdoor(r) and r["fill"] != SHAFT_FILL
    ]  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None, help="stop after N answers")
    args = parser.parse_args()

    by_file: dict[str, list[tuple[int, str, str, str | None]]] = defaultdict(list)
    with open(args.dataset / "questions.jsonl", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            q = json.loads(line)
            if not q["path"].startswith("data/swiss_dwellings/") or q["type"] != "area":
                continue
            kind, key = classify(q["question"])
            if kind != "other":
                by_file[q["path"]].append((line_no, q["unit"], kind, key))

    written = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for path, questions in by_file.items():
            if args.limit is not None and written >= args.limit:
                break
            start = time.perf_counter()
            try:
                page = Page(args.dataset / path)
            except (RuntimeError, ValueError, OSError) as error:  # a broken PDF skips its questions
                print(f"skip {path}: {error}")
                continue
            shared = (time.perf_counter() - start) / len(questions)
            for line_no, unit, kind, key in questions:
                t0 = time.perf_counter()
                rooms = answer_rooms(page, kind, key)
                if not rooms:
                    continue
                row = {
                    "id": line_no,
                    "answer": round(sum(r["area"] for r in rooms), 2),
                    "unit": unit,
                    "evidence": [
                        {"file": path, "page": 1, "box": page.box(r["outline"])}
                        for r in rooms[:MAX_BOXES]
                    ],
                    "method": "pdf-vector",
                    "cost_usd": 0.0,
                    "latency_s": round(shared + time.perf_counter() - t0, 4),
                }
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += 1
    print(f"wrote {written} answers to {args.out}")


if __name__ == "__main__":
    main()
