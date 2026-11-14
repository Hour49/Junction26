"""The plan picture of one storey of a stored services model (spec SV-29), and a services change
drawn over it (SV-30's overlay, for a before/after picture without the frontend).

Rooms and walls light grey, runs coloured per system, terminals as squares and equipment as
discs, each labelled with its id, and a legend. The picture is the storey's `frame_m` (SV-6), so
a page fraction is a fraction of the picture: the overlay and the frontend draw on it as is.
"""

import functools
import io
import itertools
import math
from collections.abc import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont

from app.core.errors import NotFoundError
from app.core.services.edit import RunChange, ServicesChange
from app.core.services.ops import EQUIPMENT_CATEGORIES, EQUIPMENT_GROUPS
from app.core.services.stored import Element, Point, Point2, ServicesModel, Storey, fraction

RGB = tuple[int, int, int]
WIDTH = 1600  # px; the height follows the frame
PAPER: RGB = (255, 255, 255)
ROOM: RGB = (242, 242, 242)
ROOM_LINE: RGB = (205, 205, 205)
WALL: RGB = (190, 190, 190)
DOOR: RGB = (255, 255, 255)
INK: RGB = (40, 40, 40)
REMOVED: RGB = (150, 150, 150)
ADDED: RGB = (0, 150, 70)
MOVED: RGB = (200, 30, 120)
# One colour per system on the storey, in the order of their names (colour-blind safe first).
PALETTE: tuple[RGB, ...] = (
    (213, 94, 0),
    (0, 114, 178),
    (0, 158, 115),
    (204, 121, 167),
    (230, 159, 0),
    (86, 180, 233),
    (120, 80, 40),
    (90, 90, 160),
)
NO_SYSTEM: RGB = (110, 110, 110)
RUN_PX, ADDED_PX, MARK_PX = 3, 7, 7


def storey_png(model: ServicesModel, storey_id: str, width: int = WIDTH) -> bytes:
    """The storey drawn from the model; NotFoundError for a storey the model lacks."""
    return _png(_draw(model, _storey(model, storey_id), width))


def change_png(model: ServicesModel, change: ServicesChange, width: int = WIDTH) -> bytes:
    """The storey of the change with the change on top: removed runs dashed grey, added runs
    thick, a moved element as a hollow mark at its old place and an arrow to the new one."""
    return _png(_overlaid(model, change, width))


def before_after_png(model: ServicesModel, change: ServicesChange, width: int = WIDTH) -> bytes:
    """Before (the model as it is) and after (the change drawn on it), side by side."""
    before = _draw(model, _storey(model, change.storey or ""), width)
    after = _overlaid(model, change, width)
    gap, head = 24, 40
    both = Image.new("RGB", (2 * width + gap, before.height + head), PAPER)
    text = ImageDraw.Draw(both)
    for x, picture, title in ((0, before, "Before"), (width + gap, after, "After")):
        both.paste(picture, (x, head))
        text.text((x + 12, 10), title, fill=INK, font=_font(22))
    return _png(both)


def legend(model: ServicesModel, storey_id: str) -> list[tuple[str, RGB]]:
    """The legend: each system on the storey with its colour (each system type when there are
    more systems than colours), then the two symbols."""
    on = _on(model, storey_id)
    by_type = len({s for e in on for s in e.systems}) > len(PALETTE)
    keys = sorted({k for e in on if (k := _key(e, by_type))})
    colours = [(name, PALETTE[i % len(PALETTE)]) for i, name in enumerate(keys)]
    return [*colours, ("terminal", INK), ("equipment", INK)]


def _key(e: Element, by_type: bool) -> str | None:
    """What an element is coloured by: its first system, or its system's type."""
    if by_type and e.system_type:
        return e.system_type
    return None if by_type or not e.systems else e.systems[0]


# --- drawing --------------------------------------------------------------------------------


def _storey(model: ServicesModel, storey_id: str) -> Storey:
    found = next((s for s in model.storeys if s.id == storey_id), None)
    if found is None:
        raise NotFoundError(f"no storey {storey_id} in this services model")
    return found


def _on(model: ServicesModel, storey_id: str) -> list[Element]:
    return [e for e in model.elements if e.storey == storey_id]


class _Page:
    def __init__(self, storey: Storey, width: int) -> None:
        x0, y0, x1, y1 = storey.frame_m
        self.storey = storey
        self.size = (width, max(1, round(width * (y1 - y0) / (x1 - x0))))

    def px(self, point: Point) -> tuple[float, float]:
        return self.at(fraction(self.storey, point))

    def at(self, fractions: Point2) -> tuple[float, float]:
        return (fractions[0] * self.size[0], fractions[1] * self.size[1])


def _draw(model: ServicesModel, storey: Storey, width: int) -> Image.Image:
    page = _Page(storey, width)
    image = Image.new("RGB", page.size, PAPER)
    draw = ImageDraw.Draw(image)
    small = _font(13)
    for room in (r for r in model.rooms if r.storey == storey.id):
        draw.polygon([page.px(p) for p in room.polygon], fill=ROOM, outline=ROOM_LINE)
    for wall in (w for w in model.walls if w.storey == storey.id):
        draw.polygon([page.px(p) for p in wall.polygon], fill=WALL)
    for opening in (o for o in model.openings if o.storey == storey.id and o.kind == "door"):
        draw.line([page.px(p) for p in opening.segment], fill=DOOR, width=RUN_PX + 2)
    for room in (r for r in model.rooms if r.storey == storey.id):
        xs, ys = zip(*(page.px(p) for p in room.polygon), strict=True)
        draw.text((sum(xs) / len(xs), sum(ys) / len(ys)), room.name, fill=REMOVED, font=small)
    colours = dict(legend(model, storey.id))
    elements = _on(model, storey.id)
    by_type = len({s for e in elements for s in e.systems}) > len(PALETTE)
    for e in elements:  # runs first, symbols on top
        colour = colours.get(_key(e, by_type) or "", NO_SYSTEM)
        if e.path and len(e.path) >= 2:
            draw.line([page.px(p) for p in e.path], fill=colour, width=RUN_PX)
        elif e.group == "flow_fitting" and e.at is not None:
            _disc(draw, page.px(e.at), RUN_PX, colour)
    for e in elements:
        if e.at is None or e.path:
            continue
        x, y = page.px(e.at)
        if _is_equipment(e):
            _disc(draw, (x, y), MARK_PX + 2, INK)
        elif e.group == "flow_terminal":
            r = MARK_PX
            draw.rectangle((x - r, y - r, x + r, y + r), fill=PAPER, outline=INK, width=2)
        else:
            continue
        draw.text((x + MARK_PX + 3, y - MARK_PX - 12), e.id, fill=INK, font=small)
    _legend(image, legend(model, storey.id), small)
    return image


def _is_equipment(e: Element) -> bool:
    return (
        e.group in EQUIPMENT_GROUPS
        or e.kind.startswith("electric_distribution")
        or e.category in EQUIPMENT_CATEGORIES
    )


def _legend(
    image: Image.Image,
    entries: Sequence[tuple[str, RGB]],
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
) -> None:
    """The legend box, in the corner where it hides the least of the plan."""
    draw = ImageDraw.Draw(image)
    line, margin = 18, 8
    w = 46 + max(draw.textlength(name, font=font) for name, _ in entries)
    h = 8 + line * len(entries)
    corners = [
        (x, y)
        for y in (margin, image.height - margin - h)
        for x in (margin, image.width - margin - w)
    ]

    def drawn(corner: tuple[float, float]) -> int:  # pixels of the plan under the box
        x, y = int(corner[0]), int(corner[1])
        box = image.crop((x, y, int(x + w), int(y + h)))
        colours = box.getcolors(box.width * box.height) or []
        return sum(n for n, colour in colours if colour != PAPER)

    x0, y0 = min(corners, key=drawn)  # the first of a tie: top left
    draw.rectangle((x0, y0, x0 + w, y0 + h), fill=PAPER, outline=ROOM_LINE)
    for i, (name, colour) in enumerate(entries):
        y = y0 + 4 + i * line + line / 2
        if name == "terminal":
            draw.rectangle((x0 + 8, y - 5, x0 + 18, y + 5), fill=PAPER, outline=INK, width=2)
        elif name == "equipment":
            _disc(draw, (x0 + 13, y), 6, INK)
        else:
            draw.line([(x0 + 4, y), (x0 + 22, y)], fill=colour, width=RUN_PX)
        draw.text((x0 + 30, y - 7), name, fill=INK, font=font)


def _disc(draw: ImageDraw.ImageDraw, at: tuple[float, float], r: float, colour: RGB) -> None:
    draw.ellipse((at[0] - r, at[1] - r, at[0] + r, at[1] + r), fill=colour)


def _overlaid(model: ServicesModel, change: ServicesChange, width: int) -> Image.Image:
    page = _Page(_storey(model, change.storey or ""), width)
    image = _draw(model, page.storey, width)
    draw = ImageDraw.Draw(image)
    for run in change.removed:
        points = _points(page, run)
        if len(points) >= 2:
            _dashed(draw, points, REMOVED, RUN_PX + 1)
        else:  # a removed terminal or fitting: a cross where it was
            (x, y), r = points[0], MARK_PX + 2
            draw.line([(x - r, y - r), (x + r, y + r)], fill=REMOVED, width=3)
            draw.line([(x - r, y + r), (x + r, y - r)], fill=REMOVED, width=3)
    for run in change.added:
        points = _points(page, run)
        if len(points) >= 2:
            draw.line(points, fill=ADDED, width=ADDED_PX, joint="curve")
        else:
            _disc(draw, points[0], ADDED_PX, ADDED)
    for moved in change.moved:
        if moved.from_ is None or moved.to is None:
            continue
        start, end = page.at(moved.from_), page.at(moved.to)
        r = MARK_PX + 3
        draw.ellipse(
            (start[0] - r, start[1] - r, start[0] + r, start[1] + r), outline=MOVED, width=3
        )
        _arrow(draw, start, end, r)
    return image


def _points(page: _Page, run: RunChange) -> list[tuple[float, float]]:
    return [page.at(p) for p in run.polyline]


def _dashed(
    draw: ImageDraw.ImageDraw, points: Iterable[tuple[float, float]], colour: RGB, width: int
) -> None:
    dash, gap = 10.0, 7.0
    for (ax, ay), (bx, by) in itertools.pairwise(points):
        length = math.hypot(bx - ax, by - ay)
        at = 0.0
        while at < length:
            stop = min(at + dash, length)
            draw.line(
                [(ax + (bx - ax) * at / length, ay + (by - ay) * at / length),
                 (ax + (bx - ax) * stop / length, ay + (by - ay) * stop / length)],
                fill=colour,
                width=width,
            )  # fmt: skip
            at = stop + gap


def _arrow(
    draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], skip: float
) -> None:
    """From the edge of the old mark to the new place, with a head."""
    length = math.hypot(end[0] - start[0], end[1] - start[1])
    if length <= skip:
        return
    ux, uy = (end[0] - start[0]) / length, (end[1] - start[1]) / length
    draw.line([(start[0] + ux * skip, start[1] + uy * skip), end], fill=MOVED, width=3)
    head = 14.0
    left = (end[0] - head * (ux - uy * 0.5), end[1] - head * (uy + ux * 0.5))
    right = (end[0] - head * (ux + uy * 0.5), end[1] - head * (uy - ux * 0.5))
    draw.polygon([end, left, right], fill=MOVED)


@functools.cache
def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """DejaVu Sans when the system has it (umlauts, "Rücklauf"), else PIL's own."""
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=False, compress_level=3)
    return buffer.getvalue()
