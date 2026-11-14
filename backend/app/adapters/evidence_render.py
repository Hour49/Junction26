"""`evidence.png`: an answer's proof drawn on its page, as docs/GOLDEN.md lists it, for a screen
that can't draw it yet and for the pitch. The page comes from page_render; this draws on top:

- counted marks outlined in their class colour and numbered; added ones the same, dashed by a
  double outline; rejected ones thin grey;
- a sum's rooms filled with their colour and value; excluded items greyed with their reason;
- a schedule's rows highlighted and numbered;
- under the page: the question and answer, the arithmetic, the colour key and the licence credit.

An answer about a building model with no page is drawn as its tables: the objects with their
GlobalIds and the storey table.
"""

import io
import math
from collections.abc import Callable, Sequence
from typing import NamedTuple

from PIL import Image, ImageDraw, ImageFont

from app.core.review.model import MarkView
from app.core.review.proof import GREY, Proof, colour, number

INK = (20, 20, 20)
HIGHLIGHT = (255, 214, 10)
MARGIN = 16
FONT = "DejaVuSans.ttf"  # found in the system's font folders by name
MAX_OBJECTS = 40  # rows of the objects table drawn; the rest is summed up in one line


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """DejaVu Sans when the system has it (Debian: fonts-dejavu-core), for ä, ü and ²; else
    Pillow's own font, which has ASCII only."""
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default(size=size)


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    value = hex_colour.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def render(
    page_png: bytes | None,
    page: int,
    marks: Sequence[MarkView],
    proof: Proof,
    headline: str,
    credit: str | None,
    width: int,
) -> bytes:
    """The evidence picture, `width` pixels wide: `page_png` (page `page` of the drawing) with the
    marks on it, zoomed to the schedule's table for a schedule answer, or, with no page, the
    proof's tables; under it the headline, arithmetic, colour key and credit."""
    unplaced: list[str] = []
    if page_png is None:
        picture = _tables(proof)
    else:
        with Image.open(io.BytesIO(page_png)) as found:
            picture = found.convert("RGB")
        unplaced = _draw_marks(picture, [mark for mark in marks if mark.page == page], proof)
        if proof.schedule is not None:
            picture = _zoom(picture, proof.schedule.box)
        if picture.width != width:
            height = round(picture.height * width / picture.width)
            picture = picture.resize((width, height), Image.Resampling.LANCZOS)
    picture = _with_footer(picture, headline, proof, credit, unplaced)
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    return buffer.getvalue()


def _draw_marks(picture: Image.Image, marks: Sequence[MarkView], proof: Proof) -> list[str]:
    """Draws the marks and their labels; returns the labels there was no room for on the page."""
    width, height = picture.size
    size = max(11, width // (130 if len(marks) > 20 else 60))  # few marks: larger numbers
    tints = {key.label: key.colour for key in proof.legend}

    def tint_of(mark: MarkView) -> str:
        if proof.kind == "count" and len(proof.legend) == 1:  # one class: one colour
            return proof.legend[0].colour
        return tints.get(mark.label or "added") or colour(mark.label or "added")

    layer = Image.new("RGBA", picture.size, (0, 0, 0, 0))
    fill = ImageDraw.Draw(layer)
    schedule = proof.kind == "schedule"
    for mark in marks:  # fills first, so outlines and numbers stay on top
        points = _points(mark, width, height)
        if mark.state == "excluded":
            fill.polygon(points, fill=(*_rgb(GREY), 110))
        elif schedule and mark.state == "counted":
            fill.polygon(points, fill=(*HIGHLIGHT, 70))
        elif proof.kind == "sum" and mark.state in ("counted", "added"):
            fill.polygon(points, fill=(*_rgb(tint_of(mark)), 70))
    picture.paste(Image.alpha_composite(picture.convert("RGBA"), layer).convert("RGB"))
    draw = ImageDraw.Draw(picture)
    line = max(2, width // 600)
    labels: list[Label] = []
    tinted: list[tuple[int, int, int]] = []
    for mark in marks:
        points = _points(mark, width, height)
        x0, y0 = min(x for x, _ in points), min(y for _, y in points)
        if mark.state in ("rejected", "excluded"):
            draw.polygon(points, outline=_rgb(GREY), width=1)
            if mark.reason:
                labels.append(Label(mark.reason, points, size - 2))
                tinted.append((110, 110, 110))
            continue
        tint = (200, 150, 0) if schedule else _rgb(tint_of(mark))
        draw.polygon(points, outline=tint, width=1 if schedule else line)
        if mark.state == "added":
            inner = [(x + line * 2, y + line * 2) for x, y in points]
            draw.polygon(inner, outline=tint, width=1)
        text = str(mark.n) if mark.n is not None else ""
        if proof.kind == "sum" and mark.value is not None:  # the value inside the room
            text = number(mark.value)
        if text and schedule:  # left of the row, so its key cell stays readable
            row_height = max(y for _, y in points) - y0
            small = _font(max(9, int(row_height * 0.8)))
            draw.text((x0 - 4, y0 + row_height / 2), text, fill=tint, font=small, anchor="rm")
        elif text:
            labels.append(Label(text, points, size))
            tinted.append(tint)
    unplaced: list[str] = []
    for label, tint, spot in zip(
        labels, tinted, place_labels(labels, _measure, width, height), strict=True
    ):
        if spot.rect is None:
            unplaced.append(label.text)
            continue
        if spot.leader is not None:
            draw.line(spot.leader, fill=tint, width=1)
        draw.rectangle(spot.rect, fill=tint)
        centre = ((spot.rect[0] + spot.rect[2]) / 2, (spot.rect[1] + spot.rect[3]) / 2)
        draw.text(centre, label.text, fill="white", font=_font(spot.size), anchor="mm")
    return unplaced


Point = tuple[float, float]
Rect = tuple[float, float, float, float]
MIN_LABEL = 10  # px: a label is not shrunk below this
RINGS = 8  # how far out a label moved off its mark is tried, in label heights
DIRECTIONS = 16
SHEET = 0.5  # a mark's box over this share of the page marks the whole sheet, not a place on it


class Label(NamedTuple):
    text: str
    points: list[Point]  # the outline it labels, in pixels
    size: int  # the largest font size it may have


class Placed(NamedTuple):
    rect: Rect | None  # where its box goes; None: no room on the page
    size: int
    leader: tuple[Point, Point] | None  # from its mark to the box, when the box is outside it


def _measure(text: str, size: int) -> tuple[float, float]:
    left, top, right, bottom = _font(size).getbbox(text)
    return right - left + 6, bottom - top + 4


def place_labels(
    labels: Sequence[Label],
    measure: Callable[[str, int], tuple[float, float]],
    width: int,
    height: int,
) -> list[Placed]:
    """Where each label's box goes, so no two boxes overlap. A label sits inside its own outline,
    sized to it; when it doesn't fit there at a readable size (60% of its own) it moves outside on
    a leader line, shrinking down to MIN_LABEL, clear of the other labels and marks (but not of a
    mark over the whole sheet); then inside at MIN_LABEL; when all fail it gets no place (the
    picture lists it under the page). Small outlines are placed first: they have the fewest
    spots."""
    boxes = [_bounds(label.points) for label in labels]
    taken: list[Rect] = []
    out: list[Placed] = [Placed(None, 0, None)] * len(labels)
    for at in sorted(range(len(labels)), key=lambda at: _area(boxes[at])):
        label, own = labels[at], boxes[at]
        readable = max(MIN_LABEL, int(label.size * 0.6))
        # a whole-sheet box covers every spot, so it would push the numbers of the marks that
        # have a place off the page (QA R6-c-1)
        others = [
            box
            for other, box in enumerate(boxes)
            if other != at and _area(box) <= SHEET * width * height
        ]
        found = (
            _inside(label, own, measure, taken, readable)
            or _outside(label, own, measure, taken, others, width, height)
            or _inside(label, own, measure, taken, MIN_LABEL)
        )
        if found is not None and found.rect is not None:
            out[at] = found
            taken.append(found.rect)
    return out


def _inside(
    label: Label,
    own: Rect,
    measure: Callable[[str, int], tuple[float, float]],
    taken: list[Rect],
    smallest: int,
) -> Placed | None:
    x0, y0, x1, y1 = own
    start = min(label.size, max(MIN_LABEL, int(min(x1 - x0, y1 - y0) * 0.5)))
    centre = (sum(x for x, _ in label.points) / len(label.points),
              sum(y for _, y in label.points) / len(label.points))  # fmt: skip
    grid = [
        (x0 + (x1 - x0) * i / 6, y0 + (y1 - y0) * j / 6) for i in range(1, 6) for j in range(1, 6)
    ]
    spots = [centre, *sorted(grid, key=lambda p: (p[0] - centre[0]) ** 2 + (p[1] - centre[1]) ** 2)]
    for size in range(start, smallest - 1, -1):
        w, h = measure(label.text, size)
        # top-left corner first: a room's printed name is usually in its middle
        corner = (x0 + w / 2 + 4, y0 + h / 2 + 4)
        for cx, cy in [corner, *spots]:
            rect = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            corners = [
                (rect[0], rect[1]),
                (rect[2], rect[1]),
                (rect[2], rect[3]),
                (rect[0], rect[3]),
            ]
            if all(_in_polygon(p, label.points) for p in (*corners, (cx, cy))) and _free(
                rect, taken
            ):
                return Placed(rect, size, None)
    return None


def _outside(
    label: Label,
    own: Rect,
    measure: Callable[[str, int], tuple[float, float]],
    taken: list[Rect],
    others: list[Rect],
    width: int,
    height: int,
) -> Placed | None:
    cx, cy = (own[0] + own[2]) / 2, (own[1] + own[3]) / 2
    half_w, half_h = (own[2] - own[0]) / 2, (own[3] - own[1]) / 2
    for size in range(max(MIN_LABEL, int(label.size * 0.8)), MIN_LABEL - 1, -2):
        w, h = measure(label.text, size)
        for ring in range(RINGS):
            gap = 2 + ring * h
            for step in range(DIRECTIONS):
                angle = 2 * math.pi * step / DIRECTIONS - math.pi / 2  # from up, clockwise
                dx, dy = math.cos(angle), math.sin(angle)
                x = cx + dx * (half_w + w / 2 + gap)
                y = cy + dy * (half_h + h / 2 + gap)
                rect = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                on_page = rect[0] >= 0 and rect[1] >= 0 and rect[2] <= width and rect[3] <= height
                if on_page and _free(rect, [*taken, *others, own]):
                    return Placed(rect, size, ((cx, cy), (x, y)))
    return None


def _bounds(points: Sequence[Point]) -> Rect:
    return (min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points), max(y for _, y in points))  # fmt: skip


def _area(rect: Rect) -> float:
    return (rect[2] - rect[0]) * (rect[3] - rect[1])


def _free(rect: Rect, taken: Sequence[Rect]) -> bool:
    return not any(_overlap(rect, other) for other in taken)


def _overlap(a: Rect, b: Rect) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Ray casting; a point on the outline counts as inside."""
    x, y = point
    inside = False
    for (ax, ay), (bx, by) in zip(polygon, [*polygon[1:], polygon[0]], strict=True):
        if min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by):
            cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
            if abs(cross) < 1e-6:
                return True
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


def _zoom(picture: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    """The part of the page around `box` (fractions), with room for the row numbers on its left."""
    x0, y0, x1, y1 = box
    pad_x, pad_y = 0.04 + 0.02 * (x1 - x0), 0.02
    left, right = max(0.0, x0 - pad_x), min(1.0, x1 + 0.02)
    top, bottom = max(0.0, y0 - pad_y), min(1.0, y1 + pad_y)
    w, h = picture.size
    return picture.crop((int(left * w), int(top * h), int(right * w), int(bottom * h)))


def _points(mark: MarkView, width: int, height: int) -> list[tuple[float, float]]:
    """The mark's polygon, or its box when it has none or the polygon spans less than half of
    the box either way (a dashed railing's polygon is its first dash: QA R6-c-1)."""
    x0, y0, x1, y1 = mark.box
    if mark.polygon:
        xs, ys = [x for x, _ in mark.polygon], [y for _, y in mark.polygon]
        if max(xs) - min(xs) >= (x1 - x0) / 2 and max(ys) - min(ys) >= (y1 - y0) / 2:
            return [(x * width, y * height) for x, y in mark.polygon]
    return [(x0 * width, y0 * height), (x1 * width, y0 * height), (x1 * width, y1 * height),
            (x0 * width, y1 * height)]  # fmt: skip


def _tables(proof: Proof) -> Image.Image:
    """A model fact with no page: the objects it rests on and the storey table, as text."""
    lines: list[str] = []
    objects = proof.objects or ()
    if objects:
        lines += ["Objects (GlobalId, class, name, storey)"]
        lines += [
            f"  {item.global_id or '-'}  {item.class_}  {item.name or '-'}  {item.storey or '-'}"
            for item in objects[:MAX_OBJECTS]
        ]
        if len(objects) > MAX_OBJECTS:
            lines.append(f"  ... and {len(objects) - MAX_OBJECTS} more")
        lines.append("")
    if proof.storeys:
        lines.append("Storeys (objects per class)")
        for row in proof.storeys:
            counts = ", ".join(f"{name} {count}" for name, count in row.counts.items())
            lines.append(f"  {row.storey}: {counts}")
    if not lines:
        lines = ["No page and no model objects to show."]
    font = _font(18)
    width = 1600
    height = MARGIN * 2 + 26 * len(lines)
    picture = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(picture)
    for at, text in enumerate(lines):
        draw.text((MARGIN, MARGIN + 26 * at), text, fill=INK, font=font)
    return picture


def _with_footer(
    picture: Image.Image, headline: str, proof: Proof, credit: str | None, unplaced: list[str]
) -> Image.Image:
    width = picture.width
    size = max(14, min(22, width // 70))
    big, small = _font(size + 4), _font(size - 2)
    room = width - 2 * MARGIN
    rows: list[tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont, tuple[int, int, int]]] = []
    rows += [(text, big, INK) for text in _wrap(headline, big, room)]
    for said in (proof.arithmetic or "").splitlines():  # "\n" starts a line (issues.zip)
        rows += [(text, _font(size), INK) for text in _wrap(said, _font(size), room)]
    if proof.check:
        rows += [(text, _font(size), INK) for text in _wrap(proof.check, _font(size), room)]
    if unplaced:  # labels with no room on the page, so nothing is silently dropped
        listed = "Not labelled on the page (no room): " + ", ".join(unplaced)
        rows += [(text, _font(size), INK) for text in _wrap(listed, _font(size), room)]
    keys = _legend_lines(proof, _font(size), size, room)
    credit_rows = _wrap(credit, small, room) if credit else []
    line = size + 10
    height = MARGIN * 2 + line * (len(rows) + len(keys)) + (size + 4) * len(credit_rows)
    out = Image.new("RGB", (width, picture.height + height), "white")
    out.paste(picture, (0, 0))
    draw = ImageDraw.Draw(out)
    draw.line((0, picture.height, width, picture.height), fill=(200, 200, 200), width=2)
    y = picture.height + MARGIN
    for text, font, ink in rows:
        draw.text((MARGIN, y), text, fill=ink, font=font)
        y += line
    for keyed in keys:
        for x, swatch, text in keyed:
            if swatch is not None:
                draw.rectangle((x, y + 3, x + size, y + 3 + size), fill=_rgb(swatch))
                x += size + 6
            draw.text((x, y), text, fill=INK, font=_font(size))
        y += line
    for text in credit_rows:
        draw.text((MARGIN, y), text, fill=(90, 90, 90), font=small)
        y += size + 4
    return out


def _legend_lines(
    proof: Proof, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, size: int, room: int
) -> list[list[tuple[int, str | None, str]]]:
    """The colour key, as lines of (x, colour, text) that fit `room`: one entry per counted class,
    with how many of it are counted without a mark. A key too wide for a line goes on to lines
    of its own, with no colour."""
    lines: list[list[tuple[int, str | None, str]]] = []
    x = MARGIN
    for key in proof.legend:
        if not key.count:
            continue
        text = key.label if proof.kind == "sum" else f"{key.label} {key.count}"  # sum: values
        text += f" ({key.note})" if key.note else ""  # are on the page
        wide = size + 6 + int(font.getlength(text))
        if not lines or (x > MARGIN and x + wide > MARGIN + room):
            lines.append([])
            x = MARGIN
        if wide > room:
            first, *rest = _wrap(text, font, room - size - 6)
            lines[-1].append((x, key.colour, first))
            for part in rest:  # under the first line's text, with no colour of its own
                lines.append([(MARGIN + size + 6, None, part)])
            lines.append([])
            continue
        lines[-1].append((x, key.colour, text))
        x += wide + 24
    return [line for line in lines if line]


def _wrap(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, room: int) -> list[str]:
    """`text` in lines no wider than `room` pixels, broken between words."""
    lines: list[str] = []
    for word in text.split():
        if lines and font.getlength(f"{lines[-1]} {word}") <= room:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines
