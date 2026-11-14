"""The drawn plan in the README pictures: a three-room flat we designed and draw here as a vector
PDF at 1:100, so no partner drawing is in a picture.

    cd backend && uv run python ../tools/readme-media/make_plan.py <out.pdf>

It uses the drawing conventions the vector reader has rules for (app/adapters/vector_pdf/swiss.py
and wall_fills.py), like backend/scripts/make_sample_archive.py, whose page writer it borrows:
walls are grey fills with a gap at each door, a door is a grey rectangle across its gap, a window a
white rectangle with two lines, a toilet, basin and bathtub outlines of 48, 48 and 69 points, a
room a filled outline holding its name, number and area. The door swings and the kitchen counter
are decoration in a grey no rule reads.

What the app should read from it: 8 doors, 6 windows, 1 toilet, 2 sinks, 1 bathtub, 2 bedrooms
(Zimmer 1.01 14.40 m², Zimmer 1.02 12.00 m²), 83.81 m² indoors.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "scripts"))

from make_sample_archive import BLACK, DOOR_GREY, GREY, RED, WHITE, SheetPdf, rect

M = 72 / 25.4 * 1000 / 100  # points per metre at 1:100
LEFT, TOP = 57.0, 34.0  # the inner corner of the flat's north-west walls, in points
OUTER, INNER = 0.25, 0.12  # wall thickness in metres
WALL = (191, 191, 191)
DECOR = (120, 120, 120)
Point = tuple[float, float]

# name, number, x0, y0, x1, y1 in metres from the inner north-west corner, fill grey, where its
# label starts, and whether the label is one line (a low room) or three
ROOMS = [
    ("Zimmer", "1.01", 0.0, 0.0, 3.6, 4.0, 255, (1.2, 1.6), False),
    ("Zimmer", "1.02", 3.72, 0.0, 6.72, 4.0, 255, (4.6, 1.6), False),
    ("Wohnen", "1.03", 6.84, 0.0, 11.0, 4.0, 255, (8.3, 1.6), False),
    ("Korridor", "1.04", 0.0, 4.12, 11.0, 5.42, 255, (5.6, 4.87), True),
    ("Bad", "1.05", 0.0, 5.54, 2.6, 8.0, 255, (1.05, 6.55), False),
    ("Reduit", "1.06", 2.72, 5.54, 4.2, 8.0, 255, (2.9, 6.9), False),
    ("Küche", "1.07", 4.32, 5.54, 11.0, 8.0, 255, (8.9, 6.4), False),
    ("Balkon", "1.08", 6.0, 8.25, 11.0, 9.75, 228, (6.3, 9.1), True),
]
# wall rectangles, already cut at the doors
WALLS = [
    (-OUTER, -OUTER, 11 + OUTER, 0.0),  # north
    (-OUTER, 0.0, 0.0, 4.27),  # west, above the entrance
    (-OUTER, 5.27, 0.0, 8.0),
    (11.0, 0.0, 11 + OUTER, 8.0),  # east
    (-OUTER, 8.0, 7.2, 8 + OUTER),  # south, left of the balcony door
    (8.1, 8.0, 11 + OUTER, 8 + OUTER),
    (0.0, 4.0, 2.5, 4.12),  # between the rooms and the corridor
    (3.4, 4.0, 4.0, 4.12),
    (4.9, 4.0, 8.0, 4.12),
    (9.0, 4.0, 11.0, 4.12),
    (0.0, 5.42, 1.5, 5.54),  # between the corridor and the south rooms
    (2.3, 5.42, 3.05, 5.54),
    (3.85, 5.42, 5.0, 5.54),
    (5.9, 5.42, 11.0, 5.54),
    (3.6, 0.0, 3.72, 4.0),  # Zimmer 1.01 | Zimmer 1.02
    (6.72, 0.0, 6.84, 4.0),  # Zimmer 1.02 | Wohnen
    (2.6, 5.54, 2.72, 8.0),  # Bad | Reduit
    (4.2, 5.54, 4.32, 8.0),  # Reduit | Küche
]
# door gaps: x0, y0, x1, y1 of the gap in its wall, then the hinge corner and the swing's side
DOORS = [
    (2.5, 4.0, 3.4, 4.12, "up"),
    (4.0, 4.0, 4.9, 4.12, "up"),
    (8.0, 4.0, 9.0, 4.12, "up"),
    (1.5, 5.42, 2.3, 5.54, "down"),
    (3.05, 5.42, 3.85, 5.54, "down"),
    (5.0, 5.42, 5.9, 5.54, "down"),
    (7.2, 8.0, 8.1, 8 + OUTER, "up"),
    (-OUTER, 4.27, 0.0, 5.27, "right"),
]
WINDOWS = [
    (1.0, -OUTER, 2.6, 0.0),
    (4.42, -OUTER, 6.02, 0.0),
    (7.6, -OUTER, 10.2, 0.0),
    (11.0, 1.0, 11 + OUTER, 3.0),
    (9.0, 8.0, 10.4, 8 + OUTER),
    (0.9, 8.0, 1.7, 8 + OUTER),
]


def at(x: float, y: float) -> Point:
    return LEFT + x * M, TOP + y * M


def box(x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
    return (*at(x0, y0), *at(x1, y1))


def oval(cx: float, cy: float, rx: float, ry: float, points: int) -> list[Point]:
    """A closed oval of `points` points, the last one on the first."""
    turn = 2 * math.pi / (points - 1)
    ring = [
        at(cx + rx * math.cos(turn * i), cy + ry * math.sin(turn * i)) for i in range(points - 1)
    ]
    return [*ring, ring[0]]


def tub(x0: float, y0: float, x1: float, y1: float, radius: float = 0.15) -> list[Point]:
    """A rounded rectangle of 69 points: 17 on each corner, and the first one again."""
    corners = [(x1 - radius, y1 - radius, 0), (x0 + radius, y1 - radius, 90),
               (x0 + radius, y0 + radius, 180), (x1 - radius, y0 + radius, 270)]  # fmt: skip
    ring = [
        at(cx + radius * math.cos(math.radians(start + 90 * i / 16)),
           cy + radius * math.sin(math.radians(start + 90 * i / 16)))
        for cx, cy, start in corners
        for i in range(17)
    ]  # fmt: skip
    return [*ring, ring[0]]


def swing(sheet: SheetPdf, x0: float, y0: float, x1: float, y1: float, side: str) -> None:
    """The open leaf and its arc, hinged at the gap's first corner, into the room on `side`."""
    if side == "right":
        hinge, radius, start, end = (x1, y0), y1 - y0, 0.0, 90.0
    elif side == "up":
        hinge, radius, start, end = (x0, y0), x1 - x0, 270.0, 360.0
    else:
        hinge, radius, start, end = (x0, y1), x1 - x0, 90.0, 0.0
    arc = [
        at(hinge[0] + radius * math.cos(math.radians(start + (end - start) * i / 12)),
           hinge[1] + radius * math.sin(math.radians(start + (end - start) * i / 12)))
        for i in range(13)
    ]  # fmt: skip
    sheet.path(arc, stroke=DECOR, width=0.3)
    sheet.path([at(*hinge), arc[0]], stroke=DECOR, width=0.3)


def plan() -> SheetPdf:
    sheet = SheetPdf(440, 350)
    for _, _, x0, y0, x1, y1, fill, _, _ in ROOMS:
        sheet.path(rect(*box(x0, y0, x1, y1)), stroke=GREY, width=0.37, fill=(fill, fill, fill))
    for wall in WALLS:
        sheet.path(rect(*box(*wall)), stroke=BLACK, width=0.99, fill=WALL)
    sheet.path(
        rect(*box(-OUTER - 0.1, -OUTER - 0.1, 11.1 + OUTER, 8.1 + OUTER)), stroke=RED, width=1.28
    )
    for x0, y0, x1, y1, side in DOORS:
        swing(sheet, x0, y0, x1, y1, side)
        a, b, c, d = box(x0, y0, x1, y1)
        across = (a - 2, b, c + 2, d) if side == "right" else (a, b - 2, c, d + 2)
        sheet.path(rect(*across), stroke=DOOR_GREY, width=0.37)
    for x0, y0, x1, y1 in WINDOWS:
        a, b, c, d = box(x0, y0, x1, y1)
        sheet.path(rect(a, b, c, d), width=0.51, fill=WHITE)
        if c - a > d - b:
            lines = [[(a, y), (c, y)] for y in (b + 1.5, d - 1.5)]
        else:
            lines = [[(x, b), (x, d)] for x in (a + 1.5, c - 1.5)]
        for line in lines:
            sheet.path(line, width=0.37)
    # bathroom: bathtub on the west wall, toilet with its tank line on the east wall, basin
    sheet.path(tub(0.08, 6.2, 0.83, 7.9), width=0.51)
    sheet.path(oval(2.2, 7.3, 0.27, 0.19, 48), width=0.51)
    sheet.path([at(2.53, 7.08), at(2.53, 7.52)], width=0.51)
    sheet.path(oval(0.62, 5.84, 0.26, 0.19, 48), width=0.51)
    # kitchen: an L-shaped counter (decoration) with a sink in it
    counter = [(4.32, 6.5), (4.92, 6.5), (4.92, 7.4), (6.9, 7.4), (6.9, 8.0)]
    sheet.path([at(x, y) for x, y in counter], stroke=DECOR, width=0.3)
    sheet.path(oval(5.9, 7.7, 0.26, 0.18, 48), width=0.51)
    for name, number, x0, y0, x1, y1, _, label, one_line in ROOMS:
        x, y = at(*label)
        for line, text in enumerate((name, number, f"{(x1 - x0) * (y1 - y0):.2f} m²")):
            sheet.text(text, x + (34 * line if one_line else 0), y + (0 if one_line else 8 * line))
    sheet.text("Whg. A", *at(1.6, 4.87))
    for a, b in (((20, 318), (420, 318)), ((20, 14), (420, 14)), ((20, 14), (20, 338)),
                 ((420, 14), (420, 338)), ((20, 338), (420, 338))):  # fmt: skip
        sheet.path([a, b], width=0.8)
    sheet.text("Sample flat, drawn by code for the Vellum README", 28, 331, size=7)
    sheet.text("Massstab 1:100", 356, 331, size=7)
    return sheet


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: make_plan.py <out.pdf>")
    out = Path(sys.argv[1])
    out.write_bytes(plan().pdf())
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
