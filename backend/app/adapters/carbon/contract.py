# ruff: noqa: E501, C420  (the contract is kept as written)
"""The Carbon reader's contract as code (r8 brief AS-2; .agents/exp/carbon-reader.md).

Two prompts with their reply schemas and hashes, the image encoding, the tile plan, the dedupe
rule across tiles, and `assemble`: the replies of one drawing as the parts of an extraction_v1
drawing (plans, elements, rooms, scale, tables, read, notes). Pure: no network, no image library.
The backend adapter copies PAGE_PROMPT, PAGE_SCHEMA, TILE_PROMPT, TILE_SCHEMA and the functions
word for word and pins READER_SHA in a test; the scoring run imports this file, so what is
measured is what is built.

Copied from prototypes/carbon-reader/contract.py (confidence, 2026-11-14) without its self-test
(tests/test_carbon_reader.py has it) and formatted; READER_SHA is pinned in that test.
"""

import hashlib
import json
import math

VERSION = "carbon-reader-1"  # change it with a prompt, a schema, the encoding or a rule below
MODEL = "gemini-4-carbon"
THINKING = "low"
TEMPERATURE = 0.2
PAGE_MAX_TOKENS = 16384
TILE_MAX_TOKENS = 8192
USD_PER_M_INPUT = 4.00  # the price the spend guard charges (brief AS); not confirmed
USD_PER_M_OUTPUT = 20.00  # thinking tokens are billed as output

MAX_SIDE = 3072  # long side of any JPEG sent (Lanczos down, never above this)
MIN_SIDE = 1536  # an image smaller than this on its long side is enlarged to it (Lanczos)
JPEG_QUALITY = 90
TILE = 3000  # px of the page: a tile's longest allowed side
OVERLAP = 300  # px shared by two neighbouring tiles
PAD = 0.02  # of the page's long side, added around a plan's box before it is tiled
MAX_TILES = 20  # a drawing that needs more is not tiled: its element classes are not read
SAME = 0.5  # of the smaller box: from here two boxes from different tiles are one item
MAX_ITEMS = 400  # a reply listing more items than this is a generation loop: a failed call

ROOM_TYPES = (
    "bedroom",
    "kitchen",
    "bathroom",
    "wc",
    "sauna",
    "balcony",
    "living",
    "hall",
    "storage",
    "outdoor",
    "shaft",
    "other",
)  # fmt: skip  (the drawing model's RoomType)
CLASSES = ("door", "window", "toilet", "sink", "shower", "bathtub", "sauna_stove")
TILE_ROOMS = ("kitchen", "sauna")
FACT_SUBJECTS = (*CLASSES, *(f"room:{kind}" for kind in ROOM_TYPES), "room", "floor_area",
                 "apartment_area", "storey", "other")  # fmt: skip
FACT_UNITS = ("count", "m2", "ft2", "other")
FT2 = 0.09290304  # m2 per square foot

PAGE_PROMPT = """This is one sheet with an architectural floor plan: a scan, an image export or a camera photo. It may be rotated or mirrored, and its text may be in any language (Finnish is common). Read it for a quantity takeoff and answer in JSON. Report only what you can see. Never guess: leave out what you cannot read, and say so in rooms_listed.

All box_2d values are [ymin, xmin, ymax, xmax] in 0-1000 coordinates of this image.

Fields:
- seen: one sentence on what is drawn.
- title_block: title, sheet_number, project, date and revision as printed in the title block or caption, each null when not printed. Never a private person's name, address or phone number.
- printed_scale: the scale as printed (for example "1:100" or "1/4 in = 1 ft"), "bar" when only a scale bar is drawn, else null.
- plans: one entry per floor plan drawn on the sheet, that is, per storey or per separate building plan shown from above with its rooms. A key plan, a location map, a site plan, an elevation, a section or a detail is not a floor plan. name: its printed caption or null. box_2d: around that plan's drawing, without the title block or legends.
- rooms: one entry per room or space of the floor plans, each room once. type is one of: bedroom (MH, makuuhuone; a dormitory room, hotel room or patient room with a bed), kitchen (K, KK, KT, keittiö, keittokomero; kitchenettes, open kitchens and utility kitchens count, as their own entry even when open to a living room), bathroom (KPH, PH, PESUH, KH, PSH: a room with a shower or bath), wc (a separate toilet room, WC), sauna (S, SAUNA), balcony (PARVEKE, also glazed), living (OH, olohuone, RUOK, dining), hall (ET, TK, AULA, eteinen, corridor, lobby), storage (VH, VAR, KHH, wardrobe, store, utility), outdoor (terrace, yard, porch), shaft (lift, duct, stairwell), other (every other room: classroom, office, plant room and so on). Use the printed label when there is one, else the fixtures and furniture drawn in the room. label: the text printed in the room, "" when nothing is printed. area_m2: the room's area only when it is printed in or next to the room, in square metres (convert square feet), else null. box_2d: around the room. On a mirrored page the text reads backwards: HM is MH, HV is VH.
- rooms_listed: "all" when every room of every plan is in rooms; "some" when rooms are missing because labels or walls are too small to read or there are too many; "none" when you could not list rooms.
- printed_facts: numbers printed on the sheet that state a takeoff quantity, such as "SECOND FLOOR = 48 DORMS" or "TOTAL 26,562 SF". text: as printed. subject: what it counts or measures (an element class, room:<type>, room for all rooms, floor_area, apartment_area, storey, other). value: the number. unit: count, m2, ft2 or other. box_2d: around the printed text. [] when there are none. Dimensions, room numbers and single room areas are not printed facts.
- tables: every area table, room schedule, door or window schedule printed on the sheet, at most 4 tables and 60 rows each. title: as printed or null. columns: the header texts left to right. rows: the cell texts of each row in column order, "" for an empty cell. box_2d: around the table. [] when there are none."""

TILE_PROMPT = """This image is a floor plan, or one part of a larger floor plan, at full resolution. It may be rotated or mirrored. List every one of the following items that is drawn in it, each once, with a box. Answer in JSON.

Classes:
- door: a doorway fitted with a door leaf (hinged with its swing arc, sliding, folding or revolving). A double door is one door. An open doorway without a door leaf is not a door. Cupboard and wardrobe doors are not doors.
- window: a window unit drawn in a wall. A unit with several panes in one frame is one window.
- toilet: a toilet bowl (WC seat). A urinal is not a toilet.
- sink: a sink or wash basin, in a kitchen, bathroom or anywhere else. A double-bowl sink is one sink.
- shower: a shower (tray, cubicle, or a shower drawn in a wet room).
- bathtub: a bathtub.
- sauna_stove: the stove of a sauna (kiuas).

Fields:
- elements: one entry per item: its class and box_2d = [ymin, xmin, ymax, xmax] in 0-1000 coordinates of this image, tight around the item. An item cut by the image edge is listed when more than half of it is visible. [] when none is drawn.
- rooms_seen: one entry per kitchen (also a kitchenette or an open kitchen: a counter with a sink and a hob) and per sauna room visible in this image, with its type and box_2d around the room or the kitchen area. [] when none.
- unreadable: the classes you cannot count reliably in this image because the items are too small, too faint or too crowded to tell apart. Never guess a count: name the class here instead, and still list the items of it you are sure of. [] when you could read all seven."""

_BOX = {"type": "ARRAY", "items": {"type": "INTEGER"}}
_TEXT = {"type": "STRING", "nullable": True}

PAGE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "seen": {"type": "STRING"},
        "title_block": {
            "type": "OBJECT",
            "properties": {name: _TEXT for name in
                           ("title", "sheet_number", "project", "date", "revision")},
            "required": ["title", "sheet_number", "project", "date", "revision"],
        },
        "printed_scale": _TEXT,
        "plans": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"name": _TEXT, "box_2d": _BOX},
            "required": ["name", "box_2d"],
        }},
        "rooms": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {
                "type": {"type": "STRING", "enum": list(ROOM_TYPES)},
                "label": {"type": "STRING"},
                "area_m2": {"type": "NUMBER", "nullable": True},
                "box_2d": _BOX,
            },
            "required": ["type", "label", "area_m2", "box_2d"],
        }},
        "rooms_listed": {"type": "STRING", "enum": ["all", "some", "none"]},
        "printed_facts": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING"},
                "subject": {"type": "STRING", "enum": list(FACT_SUBJECTS)},
                "value": {"type": "NUMBER"},
                "unit": {"type": "STRING", "enum": list(FACT_UNITS)},
                "box_2d": _BOX,
            },
            "required": ["text", "subject", "value", "unit", "box_2d"],
        }},
        "tables": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {
                "title": _TEXT,
                "columns": {"type": "ARRAY", "items": {"type": "STRING"}},
                "rows": {"type": "ARRAY", "items": {
                    "type": "OBJECT",
                    "properties": {"cells": {"type": "ARRAY", "items": {"type": "STRING"}}},
                    "required": ["cells"],
                }},
                "box_2d": _BOX,
            },
            "required": ["title", "columns", "rows", "box_2d"],
        }},
    },
    "required": ["seen", "title_block", "printed_scale", "plans", "rooms", "rooms_listed",
                 "printed_facts", "tables"],
    "propertyOrdering": ["seen", "title_block", "printed_scale", "plans", "rooms", "rooms_listed",
                         "printed_facts", "tables"],
}  # fmt: skip

TILE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "elements": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"class": {"type": "STRING", "enum": list(CLASSES)}, "box_2d": _BOX},
            "required": ["class", "box_2d"],
        }},
        "rooms_seen": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"type": {"type": "STRING", "enum": list(TILE_ROOMS)}, "box_2d": _BOX},
            "required": ["type", "box_2d"],
        }},
        "unreadable": {"type": "ARRAY", "items": {"type": "STRING", "enum": list(CLASSES)}},
    },
    "required": ["elements", "rooms_seen", "unreadable"],
    "propertyOrdering": ["elements", "rooms_seen", "unreadable"],
}  # fmt: skip


def _sha(prompt: str, schema: dict) -> str:
    return hashlib.sha256((prompt + json.dumps(schema, sort_keys=True)).encode()).hexdigest()


PAGE_SHA = _sha(PAGE_PROMPT, PAGE_SCHEMA)
TILE_SHA = _sha(TILE_PROMPT, TILE_SCHEMA)
# One hash for the reader: both prompts, both schemas, and every constant that changes a reading.
_RULES = [VERSION, MODEL, THINKING, TEMPERATURE, MAX_SIDE, MIN_SIDE, JPEG_QUALITY, TILE, OVERLAP,
          PAD, MAX_TILES, SAME]  # fmt: skip
READER_SHA = hashlib.sha256((PAGE_SHA + TILE_SHA + json.dumps(_RULES)).encode()).hexdigest()
SOURCE = f"carbon:{READER_SHA[:12]}"  # on every item it gives (`attrs.reader`) and in the notes

Px = tuple[int, int, int, int]  # x0, y0, x1, y1 in page pixels
Frac = tuple[float, float, float, float]  # x0, y0, x1, y1 as page fractions


def request_body(jpeg_b64: str, prompt: str, schema: dict, max_tokens: int) -> dict:
    return {
        "contents": [{"parts": [{"inlineData": {"mimeType": "image/jpeg", "data": jpeg_b64}},
                                {"text": prompt}]}],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "thinkingConfig": {"thinkingLevel": THINKING},
        },
    }  # fmt: skip


def sent_size(width: int, height: int) -> tuple[int, int]:
    """The pixel size an image (the page, or a tile's crop) is sent at: its own, enlarged until
    the long side is MIN_SIDE, reduced until it is MAX_SIDE."""
    long_side = max(width, height)
    scale = min(MAX_SIDE, max(MIN_SIDE, long_side)) / long_side
    return max(1, round(width * scale)), max(1, round(height * scale))


def cache_name(kind: str, pixel_sha256: str) -> str:
    """`kind` "page" or "tile"; `pixel_sha256`: of the image as decoded, before it is resized or
    encoded (the rooms reader's `pixel_digest`: RGB pixels and size), for a tile of its crop."""
    sha = PAGE_SHA if kind == "page" else TILE_SHA
    return f"carbon-{kind}-{pixel_sha256}-{sha[:12]}-{MODEL}-{THINKING}.json"


def price(usage: dict) -> float:
    """Dollars of one reply from its `usageMetadata`, at the price the spend guard charges."""
    tokens_in = int(usage.get("promptTokenCount", 0))
    tokens_out = int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0))
    return (tokens_in * USD_PER_M_INPUT + tokens_out * USD_PER_M_OUTPUT) / 1e6


def _cuts(start: int, end: int) -> list[tuple[int, int]]:
    """[start, end) cut into the fewest equal spans of at most TILE px that share OVERLAP px."""
    length = end - start
    if length <= TILE:
        return [(start, end)]
    n = math.ceil((length - OVERLAP) / (TILE - OVERLAP))
    side = math.ceil((length + (n - 1) * OVERLAP) / n)
    step = (length - side) / (n - 1)
    return [(start + round(i * step), start + round(i * step) + side) for i in range(n)]


def tile_plan(width: int, height: int, plans: list[Frac]) -> list[Px] | None:
    """The tiles of a page of `width` x `height` px whose floor plans have the boxes `plans`.

    A page of at most TILE px on its long side is one tile, the whole page, whatever the plans.
    A larger page: each plan's box, padded by PAD of the page's long side and clipped; boxes that
    then intersect become one region (their bounding box, repeated until none intersect); each
    region is cut by `_cuts` on both axes, rows first. [] when a large page has no plan (nothing
    to tile); None when the tiles would be more than MAX_TILES (the drawing is not tiled)."""
    if max(width, height) <= TILE:
        return [(0, 0, width, height)]
    pad = PAD * max(width, height)
    regions: list[Px] = []
    for x0, y0, x1, y1 in plans:
        box = (max(0, math.floor(x0 * width - pad)), max(0, math.floor(y0 * height - pad)),
               min(width, math.ceil(x1 * width + pad)), min(height, math.ceil(y1 * height + pad)))  # fmt: skip
        if box[2] > box[0] and box[3] > box[1]:
            regions.append(box)
    merged = True
    while merged:
        merged = False
        for i in range(len(regions)):
            for j in range(i + 1, len(regions)):
                a, b = regions[i], regions[j]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    regions[i] = (
                        min(a[0], b[0]),
                        min(a[1], b[1]),
                        max(a[2], b[2]),
                        max(a[3], b[3]),
                    )
                    del regions[j]
                    merged = True
                    break
            if merged:
                break
    tiles = [
        (x0, y0, x1, y1)
        for rx0, ry0, rx1, ry1 in sorted(regions, key=lambda r: (r[1], r[0]))
        for y0, y1 in _cuts(ry0, ry1)
        for x0, x1 in _cuts(rx0, rx1)
    ]
    return None if len(tiles) > MAX_TILES else tiles


def box_of(value: object) -> Frac | None:
    """A reply's box_2d ([ymin, xmin, ymax, xmax], 0-1000) as fractions of its image, x first;
    None when it is not four numbers or has no area."""
    if not isinstance(value, list) or len(value) != 4:
        return None
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in value):
        return None
    y0, x0, y1, x1 = (min(1.0, max(0.0, float(v) / 1000)) for v in value)
    x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def on_page(box: Frac, tile: Px, width: int, height: int) -> Frac:
    """A box given as fractions of `tile` as fractions of the page."""
    tx0, ty0, tx1, ty1 = tile
    w, h = tx1 - tx0, ty1 - ty0
    return ((tx0 + box[0] * w) / width, (ty0 + box[1] * h) / height,
            (tx0 + box[2] * w) / width, (ty0 + box[3] * h) / height)  # fmt: skip


def overlap(a: Frac, b: Frac) -> float:
    """The intersection's area over the smaller box's area."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h / smaller if smaller > 0 else 0.0


def _margin(box: Frac) -> float:
    """How far a box (fractions of its tile) stays from the tile's edge: the larger, the more
    of the item and its surroundings the tile saw."""
    return min(box[0], box[1], 1 - box[2], 1 - box[3])


def dedupe(found: list[dict]) -> list[dict]:
    """The items of every tile, each drawn item once. `found`: {"kind", "box" (page fractions),
    "tile" (index), "in_tile" (the box as fractions of its tile)}. Within one tile an exact repeat
    (same kind, same box) counts once. Across tiles, two items of the same kind are the same item
    when their boxes overlap by SAME of the smaller one; the one that lies farther from its own
    tile's edge is kept (ties: the lower tile index, then the order given) and names the other
    tiles in "tiles". Items of one tile are never merged with each other: two doors side by side
    are two doors."""
    seen: set[tuple[str, int, Frac]] = set()
    once: list[dict] = []
    for item in found:
        key = (item["kind"], item["tile"], item["box"])
        if key not in seen:
            seen.add(key)
            once.append(item)
    order = sorted(
        range(len(once)), key=lambda i: (-_margin(once[i]["in_tile"]), once[i]["tile"], i)
    )
    kept: list[dict] = []
    for index in order:
        item = once[index]
        same = next(
            (k for k in kept
             if k["kind"] == item["kind"] and item["tile"] not in k["tiles"]
             and overlap(k["box"], item["box"]) >= SAME),
            None,
        )  # fmt: skip
        if same is None:
            kept.append({**item, "tiles": [item["tile"]], "order": index})
        else:
            same["tiles"].append(item["tile"])
    kept.sort(key=lambda k: k["order"])
    return [{key: value for key, value in k.items() if key != "order"} for k in kept]


class ReplyError(ValueError):
    """A reply that is not the form: a failed call (nothing of it is used or cached)."""


def check_page(form: object) -> dict:
    if not isinstance(form, dict):
        raise ReplyError("the page reply is not an object")
    for name in PAGE_SCHEMA["required"]:
        if name not in form:
            raise ReplyError(f"the page reply has no {name}")
    if form["rooms_listed"] not in ("all", "some", "none"):
        raise ReplyError("rooms_listed is not all, some or none")
    for name in ("plans", "rooms", "printed_facts", "tables"):
        if not isinstance(form[name], list):
            raise ReplyError(f"{name} is not a list")
    if len(form["rooms"]) > MAX_ITEMS or len(form["plans"]) > MAX_ITEMS:
        raise ReplyError("more plans or rooms than a sheet can hold: a generation loop")
    return form


def check_tile(form: object) -> dict:
    if not isinstance(form, dict):
        raise ReplyError("the tile reply is not an object")
    for name in TILE_SCHEMA["required"]:
        if not isinstance(form.get(name), list):
            raise ReplyError(f"the tile reply has no list {name}")
    if len(form["elements"]) > MAX_ITEMS:
        raise ReplyError("more elements than a tile can hold: a generation loop")
    return form


def assemble(
    width: int,
    height: int,
    page: dict | None,
    tiles: list[Px] | None,
    tile_forms: list[dict | None],
    why_not: str | None = None,
) -> dict:
    """One drawing's replies as the parts of an extraction_v1 drawing: `plans`, `elements`,
    `rooms`, `scale`, `tables`, `read`, `notes`, plus `facts` (the printed facts, kept for the
    review screen and for stage 8; not an extraction_v1 field).

    `page`: the checked page reply; None when that call failed (`why_not` says why): nothing was
    read, `read` is [] and the first note is the reason. `tiles`: `tile_plan`'s result (None: too
    many tiles; []: a large page without a plan). `tile_forms`: the checked reply of each tile in
    order, None for a tile whose call failed.

    `read`: "room" only when rooms_listed is "all". An element class only when every tile's call
    succeeded and no tile names it in `unreadable`; none when the drawing was not tiled. A class
    that is not in `read` has no count: its questions are refused."""
    if page is None:
        return {"plans": [], "elements": [], "rooms": [], "scale": {"status": "no_scale"},
                "tables": None, "read": [], "facts": [],
                "notes": [f"carbon: not read: {why_not or 'no usable reply'}"]}  # fmt: skip
    notes = [f"carbon: {SOURCE} ({MODEL}, {VERSION})"]
    plans = []
    for entry in page["plans"]:
        box = box_of(entry.get("box_2d"))
        if box is not None:
            plans.append({"id": f"p{len(plans) + 1}", "page": 1, "box": list(box), "storey": None})
    rooms = []
    for entry in page["rooms"]:
        kind = entry.get("type")
        if kind not in ROOM_TYPES:
            continue
        box = box_of(entry.get("box_2d")) or (0.0, 0.0, 1.0, 1.0)
        area = entry.get("area_m2")
        printed = isinstance(area, int | float) and not isinstance(area, bool) and area > 0
        rooms.append({
            "id": f"r{len(rooms) + 1}", "type": kind, "label": str(entry.get("label") or "").strip() or None,
            "page": 1, "box": list(box), "area_m2": round(float(area), 2) if printed else None,
            "area_status": "exact" if printed else None, "area_source": "printed" if printed else None,
            "outdoor": kind in ("balcony", "outdoor"), "attrs": {"reader": SOURCE},
        })  # fmt: skip
    read: list[str] = []
    if page["rooms_listed"] == "all":
        read.append("room")
    else:
        notes.append(f"carbon: rooms not read: the model listed {page['rooms_listed']} of them")

    found: list[dict] = []
    unreadable: set[str] = set()
    failed = 0
    if tiles is None:
        notes.append(f"carbon: elements not read: the sheet needs more than {MAX_TILES} tiles")
    elif not tiles:
        notes.append("carbon: elements not read: no floor plan was found to tile")
    else:
        for index, (tile, form) in enumerate(zip(tiles, tile_forms, strict=True)):
            if form is None:
                failed += 1
                continue
            unreadable.update(kind for kind in form["unreadable"] if kind in CLASSES)
            for entry in form["elements"]:
                box = box_of(entry.get("box_2d"))
                if entry.get("class") in CLASSES and box is not None:
                    found.append({"kind": entry["class"], "tile": index, "in_tile": box,
                                  "box": on_page(box, tile, width, height)})  # fmt: skip
            if len(tiles) > 1:  # on a one-tile page the page call's rooms are the rooms
                for entry in form["rooms_seen"]:
                    box = box_of(entry.get("box_2d"))
                    if entry.get("type") in TILE_ROOMS and box is not None:
                        found.append({"kind": f"room:{entry['type']}", "tile": index, "in_tile": box,
                                      "box": on_page(box, tile, width, height)})  # fmt: skip
        if failed:
            notes.append(f"carbon: elements not read: {failed} of {len(tiles)} tile calls failed")
        else:
            read += [kind for kind in CLASSES if kind not in unreadable]
            if unreadable:
                said = ", ".join(kind for kind in CLASSES if kind in unreadable)
                notes.append(f"carbon: not read, too small or crowded to count: {said}")
    elements = []
    for item in dedupe(found):
        if item["kind"].startswith("room:"):
            kind = item["kind"].split(":", 1)[1]
            x, y = (item["box"][0] + item["box"][2]) / 2, (item["box"][1] + item["box"][3]) / 2
            held = any(r["type"] == kind and r["box"][0] <= x <= r["box"][2]
                       and r["box"][1] <= y <= r["box"][3] for r in rooms)  # fmt: skip
            if not held and "room" in read:
                rooms.append({
                    "id": f"r{len(rooms) + 1}", "type": kind, "label": None, "page": 1,
                    "box": [min(1.0, max(0.0, v)) for v in item["box"]], "area_m2": None,
                    "area_status": None, "area_source": None, "outdoor": False,
                    "attrs": {"reader": SOURCE, "from": "tile"},
                })  # fmt: skip
            continue
        if item["kind"] not in read:
            continue  # a class that was not read lists nothing: a partial list is not a count
        attrs: dict = {"reader": SOURCE}
        if len(tiles or []) > 1:
            attrs["tiles"] = ",".join(str(t) for t in sorted(item["tiles"]))
        elements.append({"id": f"e{len(elements) + 1}", "class": item["kind"], "page": 1,
                         "box": [min(1.0, max(0.0, v)) for v in item["box"]], "attrs": attrs})  # fmt: skip
    scale: dict = {"status": "no_scale"}
    if page["printed_scale"]:
        scale["text"] = str(page["printed_scale"])
        notes.append(
            f"carbon: printed scale {scale['text']}: read, not used (an image has no paper size)"
        )
    tables = []
    for entry in page["tables"]:
        box = box_of(entry.get("box_2d"))
        columns = [str(c) for c in entry.get("columns") or []]
        if box is None or not columns:
            continue
        rows = [{"cells": [(str(c) or None) for c in (row.get("cells") or [])][: len(columns)]}
                for row in entry.get("rows") or [] if isinstance(row, dict)]  # fmt: skip
        for row in rows:
            row["cells"] += [None] * (len(columns) - len(row["cells"]))
        tables.append({"id": f"t{len(tables) + 1}", "page": 1, "box": list(box),
                       "title": entry.get("title") or None, "columns": columns, "rows": rows})  # fmt: skip
    facts = []
    for entry in page["printed_facts"]:
        value = entry.get("value")
        if entry.get("subject") not in FACT_SUBJECTS or not isinstance(value, int | float):
            continue
        unit = entry.get("unit") if entry.get("unit") in FACT_UNITS else "other"
        if unit == "ft2":
            value, unit = round(float(value) * FT2, 2), "m2"
        box = box_of(entry.get("box_2d"))
        facts.append({"text": str(entry.get("text") or ""), "subject": entry["subject"],
                      "value": value, "unit": unit, "box": None if box is None else list(box)})  # fmt: skip
        notes.append(f"carbon: printed on the sheet: {facts[-1]['text']}")
    title = page.get("title_block") or {}
    said = ", ".join(f"{name} {title[name]}" for name in ("title", "sheet_number", "project", "date",
                                                         "revision") if title.get(name))  # fmt: skip
    if said:
        notes.append(f"carbon: title block: {said}")
    return {"plans": plans, "elements": elements, "rooms": rooms, "scale": scale,
            "tables": tables or None, "read": read, "facts": facts, "notes": notes}  # fmt: skip
