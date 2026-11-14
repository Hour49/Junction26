# ruff: noqa: E501  (the prompts are kept as measured in prototypes/printed-scale/measure.py)
"""`RASTER_PRINTED_SCALE=carbon`: the `PrintedReader` on gemini-4-carbon (the merged Carbon client).

Per sheet, page 1 of the image file:

1. The Carbon reader's page call (contract.PAGE_PROMPT): its `printed_scale` and `printed_facts`.
   It is cached under the contract's own page name, so a sheet the Carbon reader read already
   (CARBON_READER) costs nothing more.
2. A small page call for the scale bars (BARS_PROMPT): each bar's box and labels.
3. One call per bar on a full-resolution crop around it (TICKS_PROMPT): the two numbered ticks
   furthest apart, their values in metres and their points. The crop is sent as the contract sends
   any image (`jpeg`: at most 3072 px, so a bar on a 14000 px sheet keeps its pixels).
4. Only when no bar was read: a small page call for the printed dimensions (DIMS_PROMPT: up to 4,
   the longest first, each box and value), then one call per dimension, at most MAX_DIMENSIONS,
   on a full-resolution crop around it (ENDS_PROMPT, which names the value): its length in
   metres and the two ends of its dimension line. The median of their metres per pixel is the
   sheet's scale when it prints no bar and no ratio with a resolution to trust (printed.py).

Calls go through `CarbonModel` (CarbonClient: GEMINI_API_KEY, the spend guard, the trace's cost)
one after the other on the reading thread. Each checked reply is cached as a whole under a name
that holds the pixel sha256 of the image sent and the prompt's sha. A failed call (an HTTP error,
the budget used up, a reply that is not the form) is not cached: what it would have given is left
out and a note says why. Prompts and schemas are the ones measured in
prototypes/printed-scale/measure.py (22/22 Swiss Dwellings dev PNGs within 0.33% of gold).
"""

import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image

from app.adapters.carbon import contract
from app.adapters.carbon.reader import CarbonModel, jpeg
from app.adapters.eight_bit import eight_bit
from app.adapters.raster_ocr.gemini import GeminiError, pixel_digest, reply_text
from app.adapters.whole_file import write_whole
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles
from app.core.pipeline.printed import Dimension, PrintedFact, PrintedSheet, ScaleBar

MAX_TOKENS = 8192
FT2 = 0.09290304  # m² per square foot, as the contract converts a printed area
PAD_X = 0.15  # of the bar's width, added each side of its box for the crop
PAD_Y = 1.0  # of the bar's height, added above and below (the labels sit over or under it)
PAD_MIN = 0.005  # of the page, at least, each way

BARS_PROMPT = """This is an architectural drawing sheet. Report how it states its scale, in JSON.
All box_2d values are [ymin, xmin, ymax, xmax] in 0-1000 coordinates of this image.
- printed_scale: the scale as printed (for example "1:100", "1/4\\" = 1'-0\\"", "1\\" = 40'"), the one for the floor plan when several are printed; null when none is printed.
- scale_bars: every graphic scale bar (a ruler-like bar with numbered ticks): box_2d around the bar and its numbers, labels: its numbers and unit as printed. [] when there is none."""
BARS_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "printed_scale": {"type": "STRING", "nullable": True},
        "scale_bars": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}},
            "labels": {"type": "STRING"}}, "required": ["box_2d", "labels"]}},
    },
    "required": ["printed_scale", "scale_bars"],
}  # fmt: skip
TICKS_PROMPT = """This crop shows a graphic scale bar of an architectural drawing. Find the two numbered tick marks of the bar that are furthest apart (usually 0 and the largest number). For each: label as printed, metres (its value converted to metres: feet x 0.3048, inches x 0.0254), and point: [y, x] of the tick mark itself on the bar's edge, in 0-1000 coordinates of this crop. Answer in JSON."""
TICKS_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {"ticks": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "label": {"type": "STRING"}, "metres": {"type": "NUMBER"},
        "point": {"type": "ARRAY", "items": {"type": "NUMBER"}}},
        "required": ["label", "metres", "point"]}}},
    "required": ["ticks"],
}  # fmt: skip
DIMS_PROMPT = """This is an architectural drawing sheet. Find the printed dimensions of its floor plan: a dimension line (a straight line with ticks, dots, slashes or arrows at its two ends, usually between two extension lines) with its length printed along it, for example 12'-0", 3600, 12,00 or 4.50. Report up to 4, the longest first; prefer long overall dimensions across the building over short ones, and skip chains of several values on one line unless it is one value per line segment you report. For each: box_2d: [ymin, xmin, ymax, xmax] in 0-1000 coordinates of this image around the dimension line from end to end and its value; text: the value as printed. dimensions is [] when none is printed. Answer in JSON."""
DIMS_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {"dimensions": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}},
        "text": {"type": "STRING"}}, "required": ["box_2d", "text"]}}},
    "required": ["dimensions"],
}  # fmt: skip
ENDS_PROMPT = """This crop shows a printed dimension of an architectural drawing: a dimension line with its length printed along it. The value meant: {text}. Report text: the value as printed; metres: that length in metres (feet x 0.3048 plus inches x 0.0254; on a metric drawing a plain number without a decimal separator is millimetres, 3600 = 3.6, and one with a decimal comma or point is metres, 12,00 = 12); start and end: [y, x] of the two ends of that dimension line, each where the line meets its extension line, or the centre of its end tick, dot or slash, or the tip of its arrow, in 0-1000 coordinates of this crop. Answer in JSON."""
ENDS_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "text": {"type": "STRING"}, "metres": {"type": "NUMBER"},
        "start": {"type": "ARRAY", "items": {"type": "NUMBER"}},
        "end": {"type": "ARRAY", "items": {"type": "NUMBER"}},
    },
    "required": ["text", "metres", "start", "end"],
}  # fmt: skip
MAX_DIMENSIONS = 3  # ends calls per sheet: the median of three is robust to one misread
DIM_PAD = 0.08  # of the dimension's longer side, added each way, at least PAD_MIN of the page
_SHAS = {
    kind: hashlib.sha256((prompt + json.dumps(schema, sort_keys=True)).encode()).hexdigest()
    for kind, prompt, schema in (
        ("bars", BARS_PROMPT, BARS_SCHEMA),
        ("ticks", TICKS_PROMPT, TICKS_SCHEMA),
        ("dims", DIMS_PROMPT, DIMS_SCHEMA),
        ("ends", ENDS_PROMPT, ENDS_SCHEMA),
    )
}

Frac = tuple[float, float, float, float]  # x0, y0, x1, y1 as page fractions


def cache_name(kind: str, pixel_sha256: str) -> str:
    """The cache file of a bars or ticks reply, as contract.cache_name names the reader's."""
    sha = _SHAS[kind][:12]
    return (
        f"printed-{kind}-{pixel_sha256}-{sha}-{contract.REQUEST_SHA[:8]}-{contract.MODEL}-"
        f"{contract.THINKING}.json"
    )


def check_bars(form: object) -> dict[str, Any]:
    if not isinstance(form, dict) or not isinstance(form.get("scale_bars"), list):
        raise ValueError("the bars reply has no scale_bars list")
    return form


def check_dims(form: object) -> dict[str, Any]:
    if not isinstance(form, dict) or not isinstance(form.get("dimensions"), list):
        raise ValueError("the dimensions reply has no dimensions list")
    return form


def check_ends(form: object) -> dict[str, Any]:
    if not isinstance(form, dict) or not all(key in form for key in ("metres", "start", "end")):
        raise ValueError("the ends reply has no metres, start and end")
    return form


def check_ticks(form: object) -> dict[str, Any]:
    if not isinstance(form, dict) or not isinstance(form.get("ticks"), list):
        raise ValueError("the ticks reply has no ticks list")
    return form


class CarbonPrinted:
    def __init__(self, model: CarbonModel, files: DrawingFiles, cache_dir: Path | None) -> None:
        self._model = model
        self._files = files
        self._cache = cache_dir

    def read(self, source: DrawingFile, sheet: Sheet) -> PrintedSheet:
        with Image.open(io.BytesIO(self._files.read(source.path))) as image:
            page = eight_bit(image).convert("RGB")
        notes: list[str] = []
        form = self._ask("page", page, notes)
        bars_form = self._ask("bars", page, notes)
        text = form.get("printed_scale") if form is not None else None
        if not text and bars_form is not None:
            text = bars_form.get("printed_scale")
        bars: list[ScaleBar] = []
        for entry in (bars_form or {}).get("scale_bars") or []:
            box = contract.box_of(entry.get("box_2d")) if isinstance(entry, dict) else None
            if box is None:
                continue
            crop = _padded(box)
            pixels = _pixels(crop, page.size)
            ticks = self._ask("ticks", page.crop(pixels), notes)
            bar = _bar(ticks, crop, entry.get("labels"))
            if bar is not None:
                bars.append(bar)
        dimensions: list[Dimension] = []
        if not bars:  # a sheet with no bar: its printed dimensions give the scale
            dims_form = self._ask("dims", page, notes)
            entries = [e for e in (dims_form or {}).get("dimensions") or [] if isinstance(e, dict)]
            for entry in entries[:MAX_DIMENSIONS]:
                box = contract.box_of(entry.get("box_2d"))
                if box is None:
                    continue
                crop = _around(box)
                said = str(entry.get("text") or "")[:40]
                ends = self._ask("ends", page.crop(_pixels(crop, page.size)), notes, said)
                dimension = _dimension(ends, crop)
                if dimension is not None:
                    dimensions.append(dimension)
        facts = _facts(form["printed_facts"]) if form is not None else []
        return PrintedSheet(
            printed_scale=str(text) if text else None,
            bars=tuple(bars),
            dimensions=tuple(dimensions),
            printed_facts=tuple(facts),
            notes=tuple(notes),
        )

    def _ask(
        self, kind: str, image: Image.Image, notes: list[str], said: str = ""
    ) -> dict[str, Any] | None:
        """One checked reply, from the cache or paid for; None, with a note, when it failed.
        `said`: the value the dims reply printed, which the ends prompt names."""
        digest = pixel_digest(image)
        if said:  # the same crop asked about another value is another question
            digest = hashlib.sha256(f"{digest}:{said}".encode()).hexdigest()
        name = contract.cache_name("page", digest) if kind == "page" else cache_name(kind, digest)
        path = None if self._cache is None else self._cache / name
        check = {
            "page": contract.check_page,
            "bars": check_bars,
            "ticks": check_ticks,
            "dims": check_dims,
            "ends": check_ends,
        }[kind]
        if path is not None and path.is_file():
            try:
                return check(json.loads(reply_text(json.loads(path.read_text()))))
            except (ValueError, GeminiError, AttributeError, TypeError, KeyError, IndexError):
                pass  # a cached file that does not parse is a miss
        prompt, schema, tokens = {
            "page": (contract.PAGE_PROMPT, contract.PAGE_SCHEMA, contract.PAGE_MAX_TOKENS),
            "bars": (BARS_PROMPT, BARS_SCHEMA, MAX_TOKENS),
            "ticks": (TICKS_PROMPT, TICKS_SCHEMA, MAX_TOKENS),
            "dims": (DIMS_PROMPT, DIMS_SCHEMA, MAX_TOKENS),
            "ends": (
                ENDS_PROMPT.replace("{text}", said or "the one printed"),
                ENDS_SCHEMA,
                MAX_TOKENS,
            ),
        }[kind]
        try:
            answer = self._model.generate(jpeg(image), prompt, schema, tokens)
            form = check(json.loads(reply_text(answer)))
        except GeminiError as error:
            notes.append(f"printed scale: the {kind} call failed: {error}")
            return None
        except (ValueError, AttributeError, TypeError, KeyError, IndexError) as error:
            said = str(error) if isinstance(error, ValueError) else type(error).__name__
            notes.append(f"printed scale: the {kind} reply is not the form: {said}")
            return None
        if path is not None:
            write_whole(path, json.dumps(answer, ensure_ascii=False))
        return form


def _padded(box: Frac) -> Frac:
    x0, y0, x1, y1 = box
    pad_x = PAD_X * (x1 - x0) + PAD_MIN
    pad_y = PAD_Y * (y1 - y0) + PAD_MIN
    return max(0.0, x0 - pad_x), max(0.0, y0 - pad_y), min(1.0, x1 + pad_x), min(1.0, y1 + pad_y)


def _around(box: Frac) -> Frac:
    """A dimension's crop: its box with DIM_PAD of its longer side each way."""
    x0, y0, x1, y1 = box
    pad = DIM_PAD * max(x1 - x0, y1 - y0) + PAD_MIN
    return max(0.0, x0 - pad), max(0.0, y0 - pad), min(1.0, x1 + pad), min(1.0, y1 + pad)


def _pixels(crop: Frac, size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    x0, y0, x1, y1 = crop
    return round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height)


def _bar(ticks: dict[str, Any] | None, crop: Frac, labels: object) -> ScaleBar | None:
    """The bar between the lowest and the highest valued tick of a ticks reply, its points on
    the page; None with fewer than two usable ticks or no length between them."""
    usable: list[tuple[float, tuple[float, float]]] = []
    for tick in (ticks or {}).get("ticks") or []:
        if not isinstance(tick, dict):
            continue
        metres, point = tick.get("metres"), tick.get("point")
        if not isinstance(metres, int | float) or isinstance(metres, bool):
            continue
        if not isinstance(point, list) or len(point) != 2:
            continue
        if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in point):
            continue
        y, x = (min(1.0, max(0.0, float(v) / 1000)) for v in point)
        x0, y0, x1, y1 = crop
        usable.append((float(metres), (x0 + x * (x1 - x0), y0 + y * (y1 - y0))))
    if len(usable) < 2:
        return None
    low, high = min(usable), max(usable)
    if high[0] - low[0] <= 0:
        return None
    text = labels if isinstance(labels, str) and labels else None
    return ScaleBar(page=1, start=low[1], end=high[1], length_m=high[0] - low[0], text=text)


def _point(value: object, crop: Frac) -> tuple[float, float] | None:
    """A reply's [y, x] in 0-1000 crop coordinates as a page point, or None."""
    if not isinstance(value, list) or len(value) != 2:
        return None
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in value):
        return None
    y, x = (min(1.0, max(0.0, float(v) / 1000)) for v in value)
    x0, y0, x1, y1 = crop
    return x0 + x * (x1 - x0), y0 + y * (y1 - y0)


def _dimension(ends: dict[str, Any] | None, crop: Frac) -> Dimension | None:
    """The dimension an ends reply gives; None without a positive finite length or two ends."""
    if ends is None:
        return None
    metres = ends.get("metres")
    if not isinstance(metres, int | float) or isinstance(metres, bool):
        return None
    if not math.isfinite(metres) or metres <= 0:
        return None
    start, end = _point(ends.get("start"), crop), _point(ends.get("end"), crop)
    if start is None or end is None:
        return None
    text = ends.get("text")
    return Dimension(page=1, start=start, end=end, length_m=float(metres),
                     text=text if isinstance(text, str) and text else None)  # fmt: skip


def _facts(entries: list[Any]) -> list[PrintedFact]:
    """The page reply's printed facts as the contract reads them (a printed ft² in m²)."""
    facts: list[PrintedFact] = []
    for entry in entries:
        value = entry.get("value") if isinstance(entry, dict) else None
        if (
            not isinstance(value, int | float)
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            continue  # JSON's Infinity and NaN are no printed quantity
        if entry.get("subject") not in contract.FACT_SUBJECTS:
            continue
        unit = entry.get("unit") if entry.get("unit") in contract.FACT_UNITS else "other"
        if unit == "ft2":
            value, unit = round(float(value) * FT2, 2), "m2"
        facts.append(
            PrintedFact(
                text=str(entry.get("text") or ""),
                subject=str(entry["subject"]),
                value=float(value),
                unit=str(unit),
                box=contract.box_of(entry.get("box_2d")),
            )
        )
    return facts
