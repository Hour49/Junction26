# /// script
# requires-python = ">=3.13"
# dependencies = ["pypdfium2==5.15.2"]
# ///
"""Answer the eight swiss_dwellings count templates from the drawing PDF alone.

Templates (all languages in the data: en, de, fr, it): rooms labelled X, apartments, doors,
windows, toilets, washbasins, bathtubs, showers. Reads only the PDF named in each question
(no DXF/SVG/IFC sibling) and the question text. Area questions are skipped.

Rules that matter (the PDFs come from one generator, so symbols have fixed styles):
- Text: read every PDF text object on its own. The page-level text joins neighbouring labels
  ("Bad Schlafzimmer 2.38") and loses them; per object, labels are exact. Rooms = objects equal
  to the quoted label (exact string, no synonyms). Apartments = tags "Whg. A" / "App. A", not
  the red dashed unit outlines (121 of 1040 floors draw outlines that carry no tag).
- Doors = grey (68,68,68) 5-segment outlines, one per opening, so a double door counts once
  (counting the swing arcs is wrong on 43% of floors).
- Toilets = black 2-segment lines of width 0.51 (the cistern); washbasins = black 48-segment
  outlines of width 0.51 minus toilets; bathtubs = 69-segment, showers = 5-segment, both stroke
  only, black, width 0.51.
- Windows = white-filled black 5-segment rectangle (width 0.51) with at least two parallel
  2-segment lines (black, width 0.37) along its long side, of 0.8-1.2x its length and centred
  in it. The test uses the rectangle's own axis, so rotated plans work. The lift (crossing
  diagonals) is rejected by the parallel test.

Measured: 25,546 of 25,568 (99.91%) on all swiss count questions; per-template table in
prototypes/pdf-extract/README.md. Run:
    uv run prototypes/pdf-extract/swiss_counts.py --dataset <root with questions.jsonl> \\
        --out answers.jsonl [--limit N]
Known failures: stair flights with two lines along the long side count as a window (+1 on 8
floors); on 3 floors the dataset's bathtub answer is one above the tubs drawn.
latency_s: the PDF parse and symbol extraction run once per file; that time is split equally over
the file's handled questions, plus each question's own matching time.
Licence: the drawings are CC BY 4.0 (Swiss Dwellings v3.0.0, Archilyse AG, doi:10.5281/zenodo.7788422).
Credit goes in any picture shown to a person; the JSONL carries none.
"""

import argparse
import ctypes
import json
import math
import re
import time
from collections import defaultdict
from pathlib import Path

import pypdfium2 as pdfium
from pypdfium2 import raw

MAX_BOXES = 200
BLACK = (0, 0, 0)
TEMPLATES = (
    ("apartments", r"apartments|Wohnungen|appartements|appartamenti"),
    ("doors", r"doors|Türen|portes|porte "),
    ("windows", r"windows|Fenster|fenêtres|finestre"),
    ("toilets", r"toilets|WCs? |WC sont|WC sono"),
    ("washbasins", r"washbasins|Lavabos|lavabos|lavabi"),
    ("bathtubs", r"bathtubs|Badewannen|baignoires|vasche"),
    ("showers", r"showers|Duschen|douches|docce"),
)
LABEL = re.compile(r"labelled '(.+)' are|«\s*(.+?)\s*»")


def classify(question: str) -> tuple[str, str | None] | None:
    """Return (template, label) for a count question, or None."""
    for name, pattern in TEMPLATES:
        if re.search(pattern, question):
            return name, None
    match = LABEL.search(question)
    if match:
        return "rooms", match.group(1) or match.group(2)
    return None


class Path_:
    """A PDF path object: segment count, draw mode, colours, stroke width, bounds, vertices."""

    def __init__(self, obj):
        self.n = raw.FPDFPath_CountSegments(obj.raw)
        r, g, b, a = (ctypes.c_uint() for _ in range(4))
        raw.FPDFPageObj_GetStrokeColor(obj.raw, r, g, b, a)
        self.stroke = (r.value, g.value, b.value)
        width = ctypes.c_float()
        raw.FPDFPageObj_GetStrokeWidth(obj.raw, width)
        self.width = round(width.value, 2)
        mode, stroked = ctypes.c_int(), ctypes.c_int()
        raw.FPDFPath_GetDrawMode(obj.raw, mode, stroked)
        self.mode = mode.value
        r, g, b, a = (ctypes.c_uint() for _ in range(4))
        raw.FPDFPageObj_GetFillColor(obj.raw, r, g, b, a)
        self.fill = (r.value, g.value, b.value)
        self.bounds = tuple(obj.get_bounds())
        self._obj = obj
        self._vertices = None

    def vertices(self) -> list[tuple[float, float]]:
        if self._vertices is None:
            a, b, c, d, e, f = self._obj.get_matrix().get()
            points = []
            for i in range(self.n):
                segment = raw.FPDFPath_GetPathSegment(self._obj.raw, i)
                x, y = ctypes.c_float(), ctypes.c_float()
                raw.FPDFPathSegment_GetPoint(segment, x, y)
                points.append((a * x.value + c * y.value + e, b * x.value + d * y.value + f))
            self._vertices = points
        return self._vertices


def inside(inner, outer, tol: float = 0.5) -> bool:
    return (
        inner[0] >= outer[0] - tol
        and inner[1] >= outer[1] - tol
        and inner[2] <= outer[2] + tol
        and inner[3] <= outer[3] + tol
    )


def is_window(rect: Path_, lines: list[Path_]) -> bool:
    """Rectangle with two or more parallel lines along its long side, same length, centred."""
    v = rect.vertices()[:4]
    e1 = (v[1][0] - v[0][0], v[1][1] - v[0][1])
    e2 = (v[2][0] - v[1][0], v[2][1] - v[1][1])
    l1, l2 = math.hypot(*e1), math.hypot(*e2)
    if min(l1, l2) < 1e-6:
        return False
    long_edge, length, width = (e1, l1, l2) if l1 >= l2 else (e2, l2, l1)
    ux, uy = long_edge[0] / length, long_edge[1] / length
    cx, cy = sum(p[0] for p in v) / 4, sum(p[1] for p in v) / 4
    parallel = 0
    for line in lines:
        (x0, y0), (x1, y1) = line.vertices()[:2]
        dx, dy = x1 - x0, y1 - y0
        size = math.hypot(dx, dy)
        if size < 1e-6 or abs(dx * uy - dy * ux) / size > 0.05:
            continue
        mx, my = (x0 + x1) / 2 - cx, (y0 + y1) / 2 - cy
        along, across = mx * ux + my * uy, -mx * uy + my * ux
        if (
            abs(along) <= 0.8
            and abs(across) <= width / 2 + 0.3
            and 0.8 * length <= size <= 1.2 * length
        ):
            parallel += 1
    return parallel >= 2


def extract(pdf_path: Path):
    """One pass over page 1: returns (text objects, symbol boxes per kind) in PDF user space."""
    page = pdfium.PdfDocument(str(pdf_path))[0]
    textpage = page.get_textpage()
    texts, paths = [], []
    for obj in page.get_objects():
        if obj.type == raw.FPDF_PAGEOBJ_TEXT:
            size = raw.FPDFTextObj_GetText(obj.raw, textpage.raw, None, 0)
            buffer = (ctypes.c_ushort * size)()
            raw.FPDFTextObj_GetText(obj.raw, textpage.raw, buffer, size)
            text = bytes(buffer).decode("utf-16-le").rstrip("\x00").strip()
            texts.append((text, tuple(obj.get_bounds())))
        elif obj.type == raw.FPDF_PAGEOBJ_PATH:
            paths.append(Path_(obj))

    def pick(n, mode, stroke, width):
        return [p for p in paths if (p.n, p.mode, p.stroke, p.width) == (n, mode, stroke, width)]

    lines051 = pick(2, 0, BLACK, 0.51)
    big = pick(48, 0, BLACK, 0.51)
    lines037 = pick(2, 0, BLACK, 0.37)
    kinds = {
        "doors": [p.bounds for p in pick(5, 0, (68, 68, 68), 0.37)],
        "bathtubs": [p.bounds for p in pick(69, 0, BLACK, 0.51)],
        "showers": [p.bounds for p in pick(5, 0, BLACK, 0.51)],
        "windows": [p.bounds for p in pick(5, 2, BLACK, 0.51) if is_window(p, lines037)],
    }
    toilet_boxes = []
    for line in lines051:
        parent = next((b for b in big if inside(line.bounds, b.bounds, 1.0)), None)
        toilet_boxes.append(parent.bounds if parent else line.bounds)
    kinds["toilets"] = toilet_boxes
    with_line = [b for b in big if any(inside(x.bounds, b.bounds, 1.0) for x in lines051)]
    free = [b.bounds for b in big if b not in with_line]
    # washbasins = all 48-segment outlines minus toilets (count as defined; boxes of the rest)
    kinds["washbasins"] = free
    kinds["washbasin_count"] = max(len(big) - len(lines051), 0)
    media = page.get_mediabox()
    return texts, kinds, media, page.get_rotation()


def to_fraction(box, media, rotation) -> list[float]:
    """PDF user-space box -> [x0, y0, x1, y1] page fractions, origin top left, rotation applied."""
    x0m, y0m, x1m, y1m = media
    width, height = x1m - x0m, y1m - y0m
    corners = [(box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3])]
    out = []
    for x, y in corners:
        u, v = (x - x0m) / width, 1 - (y - y0m) / height
        u, v = {0: (u, v), 90: (1 - v, u), 180: (1 - u, 1 - v), 270: (v, 1 - u)}[rotation % 360]
        out.append((u, v))
    clamp = lambda t: round(min(max(t, 0.0), 1.0), 4)
    return [
        clamp(min(p[0] for p in out)),
        clamp(min(p[1] for p in out)),
        clamp(max(p[0] for p in out)),
        clamp(max(p[1] for p in out)),
    ]


def answer_question(template: str, label: str | None, texts, kinds) -> tuple[int, list[tuple]]:
    """Return (count, boxes of the counted elements in PDF user space) for one question."""
    if template == "rooms":
        boxes = [b for t, b in texts if t == label]
    elif template == "apartments":
        boxes = [b for t, b in texts if re.fullmatch(r"(Whg\.|App\.)\s+\S+", t)]
    else:
        boxes = kinds[template]
    return (kinds["washbasin_count"] if template == "washbasins" else len(boxes)), boxes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    by_file: dict[str, list[tuple[int, str, str, str | None, str | None]]] = defaultdict(list)
    handled = 0
    with (args.dataset / "questions.jsonl").open(encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            row = json.loads(line)
            if not row["path"].startswith("data/swiss_dwellings/") or row["type"] != "count":
                continue
            found = classify(row["question"])
            if found is None:
                continue
            by_file[row["path"]].append((number, row["unit"], *found))
            handled += 1
            if args.limit and handled >= args.limit:
                break

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        for rel, questions in by_file.items():
            started = time.perf_counter()
            texts, kinds, media, rotation = extract(args.dataset / rel)
            parse_share = (time.perf_counter() - started) / len(questions)
            for number, unit, template, label in questions:
                started = time.perf_counter()
                count, boxes = answer_question(template, label, texts, kinds)
                row = {
                    "id": number,
                    "answer": count,
                    "unit": unit,
                    "evidence": [
                        {"file": rel, "page": 1, "box": to_fraction(b, media, rotation)}
                        for b in boxes[:MAX_BOXES]
                    ],
                    "method": "pdf-vector",
                    "cost_usd": 0.0,
                    "latency_s": round(parse_share + time.perf_counter() - started, 4),
                }
                out.write(json.dumps(row) + "\n")
    print(f"{handled} questions in {len(by_file)} files -> {args.out}")


if __name__ == "__main__":
    main()
