"""`vlm`: plan symbols read by Gemini (DISCIPLINE_PICTURES=gemini), one Carbon call per page.

The page alone is sent (no OCR legend: on scans the OCR legend reader finds nearly nothing, and
every local reader fails with it). The reply names the legend's symbol rows as printed, each
with the box of its sample, and every place on the plan where each row's symbol is drawn, as
boxes normalised to 0..1000 (Gemini's box_2d: ymin, xmin, ymax, xmax). A box of a label the
legend does not have is dropped. Measured on the rendered held-out building (pic-det, report
.agents/exp/pics-pic-det.md); its price is the Carbon client's, charged to the spend guard.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

from app.adapters.carbon import contract
from app.adapters.carbon.reader import CarbonModel, jpeg
from app.adapters.discipline_pictures import NO_LEGEND, nothing, read_image
from app.adapters.raster_ocr.gemini import GeminiError
from app.adapters.whole_file import write_whole
from app.core.ifc_facts import Spot
from app.core.picture_facts import LegendEntry, PictureReading, Sighting
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles

READER = "vlm"
PROMPT = """This is a building services plan (heating, plumbing, ventilation, electrical, fire or
structural) with a legend. First read the legend: every row that pairs a drawn symbol (or a line
style) with its label. Give each row's label exactly as printed, whether it is a line style (a
pipe or duct run) rather than a symbol, and the box of its drawn sample.
Then find every place on the PLAN (not in the legend) where each legend SYMBOL is drawn. Match a
symbol by its exact shape and fill as drawn in its legend row (outline, solid, with a dot, with a
number beside it). Give the box of every occurrence under its row's label; a symbol with none
gets an empty list. Boxes are box_2d [ymin, xmin, ymax, xmax] normalised to 0-1000 of the image.
If the page has no legend, return an empty legend."""
BOX = {"type": "array", "items": {"type": "integer"}}
SCHEMA = {
    "type": "object",
    "properties": {
        "legend": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "line": {"type": "boolean"},
                    "box": BOX,
                },
                "required": ["label", "line", "box"],
            },
        },
        "symbols": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "boxes": {"type": "array", "items": BOX},
                },
                "required": ["label", "boxes"],
            },
        },
    },
    "required": ["legend", "symbols"],
}
PROMPT_SHA = hashlib.sha256((PROMPT + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest()


class GeminiPictureReader:
    """`PictureReader`; `legend_of` is not asked: the reply carries its own legend.

    Replies are cached whole in `cache_dir` by the page file's sha256, the prompt (and schema)
    hash and the model, so a page is paid for once; only a reply that parses is kept. A failed
    call (no answer, budget spent) or a reply that is not the asked JSON raises `GeminiError`:
    the lane then keeps no sheet for the page (a sheet already kept stays), and the next ingest
    asks again."""

    def __init__(self, files: DrawingFiles, client: CarbonModel, cache_dir: Path) -> None:
        self._files = files
        self._client = client
        self._cache = cache_dir

    def read(self, source: DrawingFile, sheet: Sheet) -> PictureReading:
        data = self._files.read(source.path)
        name = f"vlm-{hashlib.sha256(data).hexdigest()}-{PROMPT_SHA[:12]}-{contract.MODEL}.json"
        path = self._cache / re.sub(r"[^A-Za-z0-9.-]", "_", name)
        if path.is_file():
            try:
                return reading_of(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):  # unreadable: asked again
                pass
        rgb = read_image(READER, data, source, sheet)
        if isinstance(rgb, PictureReading):
            return rgb
        answer = self._client.generate(
            jpeg(Image.fromarray(rgb)), PROMPT, SCHEMA, contract.PAGE_MAX_TOKENS
        )  # GeminiError goes to the lane
        try:
            reading = reading_of(answer)
        except ValueError as error:
            raise GeminiError(f"{READER}: {error}") from None
        write_whole(path, json.dumps(answer, ensure_ascii=False))
        usd = contract.price(answer.get("usageMetadata") or {})
        return reading.model_copy(update={"cost_usd": round(usd, 6)})


def reading_of(answer: dict[str, Any]) -> PictureReading:
    """The reply as a reading: its legend, and its boxes of the legend's symbols. ValueError: the
    reply is not the asked JSON."""
    try:
        parts = answer["candidates"][0]["content"]["parts"]
        found = contract_json("".join(p.get("text", "") for p in parts if not p.get("thought")))
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("the reply is not the asked JSON") from None
    legend: list[LegendEntry] = []
    for row in found.get("legend") or []:
        label = str(row.get("label", "")).strip()
        if label and label not in {e.label for e in legend}:
            legend.append(
                LegendEntry(
                    label=label, group=None, line=bool(row.get("line")), box=_box(row.get("box"))
                )
            )
    if not legend:
        return nothing(READER, None, f"{READER}: {NO_LEGEND}")
    symbols = {e.label for e in legend if not e.line}
    sightings = [
        Sighting(label=row["label"], spot=Spot(page=1, box=box, reader=READER))
        for row in found.get("symbols") or []
        if row.get("label") in symbols
        for raw in row.get("boxes") or []
        if (box := _box(raw)) is not None
    ]
    sightings.sort(key=lambda s: (s.spot.box[1], s.spot.box[0]))
    return PictureReading(
        reader=READER, legend=tuple(legend), read=tuple(sorted(symbols)), sightings=tuple(sightings)
    )


def contract_json(text: str) -> dict[str, Any]:
    found = json.loads(text)
    if not isinstance(found, dict):
        raise ValueError("not an object")
    return found


def _box(raw: Any) -> tuple[float, float, float, float] | None:
    """box_2d [ymin, xmin, ymax, xmax] in 0..1000 as a page-fraction box; None if malformed."""
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in raw):
        return None
    y0, x0, y1, x1 = (min(max(v, 0), 1000) / 1000 for v in raw)
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)
