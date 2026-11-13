# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pypdfium2==5.15.2",
#     "pdfplumber==0.11.10",
#     "shapely==2.2.0",
# ]
# ///
"""Room-area questions on the ifc_models floor-plan PDFs, answered from the PDF alone.

Answers (source `ifc_models`, question type `area`, path ends in `_plan-*.pdf`):
  - "net floor area of the room 'Name (number)' on '<storey>'" (every language in the data)
  - "total net floor area of all rooms on '<storey>'"
Skipped: wall side-area questions (need wall heights, only in the IFC) and any `.ifc` path.

How: the sheets are rendered from IFC, every room is one filled path in the colour #e3edf7. The
label (name line + number line, text objects read one by one through pypdfium2, because
pdfplumber interleaves the characters of overlapping labels) gives an anchor; the smallest fill
polygon containing it is the room. Area = shoelace area x (scale)^2, scale read from the sheet
text ("1:100", Warmond is 1:200, so the scale is never hardcoded).
Storey totals: union of the room fills (nested spaces count once). When the question's storey
equals the prefix of the room numbers on the sheet ("0" vs "0.3"), only those rooms count:
the sheet also draws spaces of the storey below (same fill, same sheet).

Measured 2026-11-13 over all 1,862 questions it handles: 97.0% correct (rooms 97.3%, storey
totals 88.6%); per-template table in prototypes/pdf-extract/README.md. The rules (scale from the
sheet, label anchors, storey-prefix filter) were tuned on all of these questions, not on a
held-out part, so the number is optimistic: judge it on the sealed 20% eval split instead.
Run:  uv run prototypes/pdf-extract/ifc_plan_areas.py --dataset <root with questions.jsonl>
      --out answers.jsonl [--limit N]
Failure cases: a sheet that stacks several storeys (same label in several polygons: the first
one wins), rooms with holes in the IFC that the PDF fill does not show (corridor around a core),
tiny shafts (2% of 0.2 m2), labels hidden by overlapping text.
latency_s: the per-file parse is shared; each question gets its own time plus an equal share of
the file's parse time. cost_usd is 0 (no model call).
Licence: the drawings carry per-file licences (data/ifc_models/LICENSE.md); credit goes in any
picture shown to a judge, not in the JSONL.
"""

import argparse
import ctypes
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

SPACE_FILL = (0.890, 0.929, 0.969)  # #e3edf7, the room fill of every rendered plan
PT_MM = 25.4 / 72
MAX_BOXES = 200
WALL_WORDS = re.compile(r"wall|wände|wanden|vægge|seina|ścian|paredes|muros|murs", re.IGNORECASE)
QUOTES = [("„", "“"), ("„", "”"), ("«", "»"), ("“", "”")]


def parse_names(question: str) -> list[str] | None:
    """Quoted names in the question: [room, storey] or [storey]; handles apostrophes in names."""
    for opening, closing in QUOTES:
        found = re.findall(re.escape(opening) + r"(.*?)" + re.escape(closing), question)
        if found:
            return found
    marks = [i for i, ch in enumerate(question) if ch == "'"]
    if len(marks) == 2:
        return [question[marks[0] + 1 : marks[1]]]
    if len(marks) >= 4:
        return [question[marks[0] + 1 : marks[-3]], question[marks[-2] + 1 : marks[-1]]]
    return None


def split_room(room: str) -> tuple[str, str | None]:
    match = re.fullmatch(r"(.*) \(([^()]*)\)", room)
    return (match.group(1), match.group(2)) if match else (room, None)


def squash(text: str) -> str:
    return " ".join(text.split())


class Sheet:
    """Parsed plan: scale, room polygons (page points, origin bottom left) and text lines."""

    def __init__(self, path: Path):
        page = pdfplumber.open(path).pages[0]
        self.width, self.height = float(page.width), float(page.height)
        self.rotation = page.rotation
        found = re.search(r"(?<!\d)1\s*:\s*(\d{2,3})(?!\d)", page.extract_text() or "")
        self.scale = int(found.group(1)) if found else None
        self.polygons, self.areas = [], []
        for obj in page.curves + page.rects:
            colour = obj.get("non_stroking_color")
            if not obj.get("fill") or not colour or len(colour) != 3:
                continue
            if any(abs(a - b) > 0.03 for a, b in zip(colour, SPACE_FILL)):
                continue
            rings = [[(x, self.height - y) for x, y in ring] for ring in self._rings(obj)]
            if rings:
                self.polygons.append(unary_union([Polygon(r).buffer(0) for r in rings]))
                self.areas.append(abs(sum(_shoelace(r) for r in rings)))
        self.lines = _text_lines(path)

    @staticmethod
    def _rings(obj) -> list[list[tuple[float, float]]]:
        rings, current = [], []
        for op in obj["path"]:
            if op[0] == "m":
                if len(current) > 2:
                    rings.append(current)
                current = [op[1]]
            elif op[0] in ("l", "c"):
                current.append(op[-1])
        if len(current) > 2:
            rings.append(current)
        return rings

    def metres2(self, paper_pt2: float) -> float:
        return paper_pt2 * (PT_MM * self.scale / 1000) ** 2

    def box(self, polygon) -> list[float]:
        """Page fractions [x0, y0, x1, y1], origin top left (sheets are unrotated)."""
        x0, y0, x1, y1 = polygon.bounds
        w, h = self.width, self.height
        return [
            round(max(0.0, x0 / w), 4),
            round(max(0.0, (h - y1) / h), 4),
            round(min(1.0, x1 / w), 4),
            round(min(1.0, (h - y0) / h), 4),
        ]


def _shoelace(ring) -> float:
    n = len(ring)
    return (
        sum(ring[i][0] * ring[(i + 1) % n][1] - ring[(i + 1) % n][0] * ring[i][1] for i in range(n))
        / 2
    )


def _text_lines(path: Path) -> list[tuple[str, float, float]]:
    """One entry per PDF text object: (text, centre x, centre y), origin bottom left."""
    page = pdfium.PdfDocument(path)[0]
    textpage = page.get_textpage()
    lines = []
    for obj in page.get_objects(filter=[pdfium_raw.FPDF_PAGEOBJ_TEXT], max_depth=4):
        size = pdfium_raw.FPDFTextObj_GetText(obj.raw, textpage.raw, None, 0)
        buffer = (ctypes.c_ushort * size)()
        pdfium_raw.FPDFTextObj_GetText(obj.raw, textpage.raw, buffer, size)
        text = bytes(buffer).decode("utf-16le").rstrip("\x00")
        left, bottom, right, top = obj.get_bounds()
        lines.append((squash(text), (left + right) / 2, (bottom + top) / 2))
    return lines


def room_polygon(sheet: Sheet, room: str):
    """Index of the fill polygon holding this room's label, or None."""
    name, number = split_room(room)
    name = squash(name)
    anchors = []
    if number:
        number = squash(number)
        for text, x, y in sheet.lines:
            if text != number and not text.endswith(number.split()[-1]):
                continue
            near = [
                (abs(y - ny) + abs(x - nx), nx, ny)
                for t, nx, ny in sheet.lines
                if t == name and abs(nx - x) < 60 and abs(ny - y) < 25
            ]
            if near:
                _, nx, ny = min(near)
                anchors.append(((x + nx) / 2, (y + ny) / 2))
    else:
        anchors = [(x, y) for text, x, y in sheet.lines if text == name]
    for x, y in anchors:
        inside = [i for i, p in enumerate(sheet.polygons) if p.contains(Point(x, y))]
        if inside:
            return min(inside, key=lambda i: sheet.polygons[i].area)
    return None


def storey_total(sheet: Sheet, storey: str) -> tuple[float, list[int]]:
    """Union area of the room fills; restricted to the storey's own room-number prefix if any."""
    keep = list(range(len(sheet.polygons)))
    labelled = defaultdict(list)
    for text, x, y in sheet.lines:
        prefix = re.fullmatch(r"(-?\d+)\.\d+", text)
        if prefix:
            inside = [i for i, p in enumerate(sheet.polygons) if p.contains(Point(x, y))]
            if inside:
                labelled[prefix.group(1)].append(min(inside, key=lambda i: sheet.polygons[i].area))
    if storey.strip() in labelled and len(labelled) > 1:
        keep = sorted(set(labelled[storey.strip()]))
    union = unary_union([sheet.polygons[i] for i in keep])
    return sheet.metres2(union.area), keep


def handled(question: dict) -> tuple[str, list[str]] | None:
    """("room" | "total", names) for the questions this script answers."""
    path = question["path"]
    if not (path.startswith("data/ifc_models/") and path.endswith(".pdf")):
        return None
    if question["type"] != "area" or WALL_WORDS.search(question["question"]):
        return None
    names = parse_names(question["question"])
    if not names:
        return None
    return ("room", names) if len(names) == 2 else ("total", names)


def answer_one(sheet: Sheet, path: str, kind: str, names: list[str]) -> dict | None:
    if sheet.scale is None or sheet.rotation:
        return None
    if kind == "room":
        index = room_polygon(sheet, names[0])
        if index is None:
            return None
        value = sheet.metres2(sheet.areas[index])
        boxes = [sheet.box(sheet.polygons[index])]
    else:
        value, keep = storey_total(sheet, names[0])
        boxes = [sheet.box(sheet.polygons[i]) for i in keep[:MAX_BOXES]]
    evidence = [{"file": path, "page": 1, "box": box} for box in boxes]
    return {"answer": round(value, 3), "evidence": evidence}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    by_file = defaultdict(list)
    total = 0
    with open(args.dataset / "questions.jsonl", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.startswith('{"path": "data/ifc_models/'):
                continue
            question = json.loads(line)
            plan = handled(question)
            if plan:
                total += 1
                if args.limit is None or total <= args.limit:
                    by_file[question["path"]].append((line_no, question["unit"], *plan))

    written = skipped = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for path, items in by_file.items():
            start = time.perf_counter()
            try:
                sheet = Sheet(args.dataset / path)
            except (OSError, ValueError, pdfium.PdfiumError) as error:  # skip a broken PDF
                print(f"skip {path}: {error!r}", file=sys.stderr)
                skipped += len(items)
                continue
            share = (time.perf_counter() - start) / len(items)
            for line_no, unit, kind, names in items:
                begin = time.perf_counter()
                result = answer_one(sheet, path, kind, names)
                if result is None:
                    skipped += 1
                    continue
                record = {
                    "id": line_no,
                    **result,
                    "unit": unit,
                    "method": "pdf-vector",
                    "cost_usd": 0.0,
                    "latency_s": round(share + time.perf_counter() - begin, 4),
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
    print(f"handled {total} questions: wrote {written}, skipped {skipped}", file=sys.stderr)


if __name__ == "__main__":
    main()
