"""`vlm-runs`: a services plan's runs (pipes, ducts) read by Gemini (DISCIPLINE_RUNS=gemini), one
Carbon call per page, in place of the `mask` reader's runs.

The reply names each legend line style (one pipe or duct system) as printed, the size labels
printed beside its runs, and its runs as polylines ([y, x] normalised to 0..1000, Gemini's box_2d
convention), each with the size printed beside it or null. A run's length is its polyline's length
in page pixels at the sheet's scale (`ScaleOf`, the product's scale reader: the printed ratio at
the file's dpi, or a scale bar); the model's own metres are asked for but not used (26% of systems
within 10% against 63% from its polylines, .agents/exp/pics-pic-cls.md round 5). Without a scale
there are no runs and the notes say `NO_SCALE`, as `mask`. Runs are summed per (system, size).

Measured (pre-registered, rendered bench): DigitalHub v2 clean + scan, systems' drawn length within
10% on 34/54 (63%), printed sizes right 165/180 (92%); the mask reader 8% on Tudor's bench.

Replies are cached whole by the page file's sha256, VERSION, the prompt (and schema) hash and the
model. A failed call or a reply that is not the asked JSON raises `GeminiError` (the lane keeps no
sheet, and a sheet it had stays); a reply with no system is not kept, so the next ingest asks again.
"""

import hashlib
import json
import math
import re
from collections import defaultdict
from itertools import pairwise
from pathlib import Path
from typing import Any

from PIL import Image

from app.adapters.carbon import contract
from app.adapters.carbon.reader import CarbonModel, jpeg
from app.adapters.discipline_pictures import NO_LEGEND, ScaleOf, nothing, page_box, read_image
from app.adapters.raster_ocr.gemini import GeminiError
from app.adapters.whole_file import write_whole
from app.core.ifc_facts import Spot
from app.core.picture_facts import NO_SCALE, LegendEntry, PictureReading, Run
from app.core.pipeline.model import DrawingFile, Sheet
from app.core.pipeline.ports import DrawingFiles

READER = "vlm-runs"
# In the cache key with PROMPT_SHA: bump it with what that hash does not see (the Carbon model's
# thinking level, MAX_TOKENS, the JPEG encoding), so old replies are not served after it
VERSION = "vlm-runs-1"
MAX_TOKENS = 32768  # a dense ventilation floor took 12k output tokens on the bench
# The prompt and schema of the measured run (round 5), word for word
PROMPT = """This is a building services plan (pipes or ducts drawn over a light grey floor plan) with a
legend on the right. In the legend, each LINE STYLE row (a short coloured or dashed line next to a name) is one
pipe or duct system.
For each line-style system in the legend:
- label: the system name exactly as printed in the legend.
- sizes: every size label printed on the plan beside this system's lines (for example "DN70 mm" or "200/250"),
  each once, exactly as printed.
- runs: every run of this system drawn on the plan (not in the legend), as polylines that follow the drawn line
  from end to end through each bend. Points are [y, x] normalised to 0-1000 of the image (box_2d convention).
  A run's size is the size label printed beside it, else null. Include short runs too.
- length_m: your estimate of the total length of this system's lines on the plan in metres, using the scale bar
  or the printed ratio.
Ignore walls (light grey), symbols and text. Report only systems that are in the legend."""  # noqa: E501
_POINT = {"type": "array", "items": {"type": "number"}}
_RUN = {
    "type": "object",
    "properties": {
        "size": {"type": "string", "nullable": True},
        "points": {"type": "array", "items": _POINT},
    },
    "required": ["size", "points"],
}
_SYSTEM = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "sizes": {"type": "array", "items": {"type": "string"}},
        "runs": {"type": "array", "items": _RUN},
        "length_m": {"type": "number"},
    },
    "required": ["label", "sizes", "runs", "length_m"],
}
SCHEMA = {
    "type": "object",
    "properties": {"systems": {"type": "array", "items": _SYSTEM}},
    "required": ["systems"],
}
PROMPT_SHA = hashlib.sha256((PROMPT + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest()


class GeminiRunReader:
    """`PictureReader` of runs; its legend is the reply's line rows (no OCR legend)."""

    def __init__(
        self, files: DrawingFiles, client: CarbonModel, cache_dir: Path, scale_of: ScaleOf
    ) -> None:
        self._files = files
        self._client = client
        self._cache = cache_dir
        self._scale_of = scale_of

    def read(self, source: DrawingFile, sheet: Sheet) -> PictureReading:
        data = self._files.read(source.path)
        rgb = read_image(READER, data, source, sheet)
        if isinstance(rgb, PictureReading):
            return rgb
        m_per_unit = self._scale_of(source, sheet).m_per_unit
        if m_per_unit is None:  # no call: there would be no runs to give
            return nothing(READER, None, f"{READER}: {NO_SCALE}")
        height, width = rgb.shape[:2]
        m_per_px = m_per_unit * sheet.pages[0].width / width
        digest = hashlib.sha256(data).hexdigest()
        name = f"vlm-runs-{digest}-{VERSION}-{PROMPT_SHA[:12]}-{contract.MODEL}.json"
        path = self._cache / re.sub(r"[^A-Za-z0-9.-]", "_", name)
        if path.is_file():
            try:
                return reading_of(
                    json.loads(path.read_text(encoding="utf-8")), width, height, m_per_px
                )
            except (OSError, ValueError):  # unreadable: asked again
                pass
        answer = self._client.generate(
            jpeg(Image.fromarray(rgb)), PROMPT, SCHEMA, MAX_TOKENS
        )  # GeminiError goes to the lane
        try:
            reading = reading_of(answer, width, height, m_per_px)
        except ValueError as error:
            raise GeminiError(f"{READER}: {error}") from None
        if reading.legend is not None:  # no system: not kept, the next ingest asks again
            write_whole(path, json.dumps(answer, ensure_ascii=False))
        usd = contract.price(answer.get("usageMetadata") or {})
        return reading.model_copy(update={"cost_usd": round(usd, 6)})


def reading_of(answer: dict[str, Any], width: int, height: int, m_per_px: float) -> PictureReading:
    """The reply as runs: per system and printed size, the summed polyline length at `m_per_px`,
    one spot per polyline (its box). ValueError: the reply is not the asked JSON."""
    try:
        parts = answer["candidates"][0]["content"]["parts"]
        found = json.loads("".join(p.get("text", "") for p in parts if not p.get("thought")))
        systems = found["systems"]
        if not isinstance(systems, list):
            raise TypeError
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("the reply is not the asked JSON") from None
    legend: dict[str, LegendEntry] = {}
    lengths: dict[tuple[str, str | None], float] = defaultdict(float)
    spots: dict[tuple[str, str | None], list[Spot]] = defaultdict(list)
    for system in systems:
        label = str(system.get("label", "")).strip() if isinstance(system, dict) else ""
        if not label:
            continue
        legend.setdefault(label, LegendEntry(label=label, group=None, line=True, box=None))
        for run in system.get("runs") or []:
            points = _points(run.get("points") if isinstance(run, dict) else None, width, height)
            if len(points) < 2:
                continue
            size = run.get("size")
            key = (label, size.strip() if isinstance(size, str) and size.strip() else None)
            lengths[key] += m_per_px * sum(math.dist(a, b) for a, b in pairwise(points))
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            box = page_box(min(xs), min(ys), max(xs), max(ys), width, height)
            spots[key].append(Spot(page=1, box=box, reader=READER))
    if not legend:
        return nothing(READER, None, f"{READER}: {NO_LEGEND}")
    runs = tuple(
        Run(label=label, size=size, length_m=round(length, 3), spots=tuple(spots[(label, size)]))
        for (label, size), length in sorted(lengths.items(), key=lambda item: str(item[0]))
        if length > 0
    )
    return PictureReading(reader=READER, legend=tuple(legend.values()), read=None, runs=runs)


def _points(raw: Any, width: int, height: int) -> list[tuple[float, float]]:
    """[y, x] points in 0..1000 as page pixels (x, y); malformed points are dropped."""
    out = []
    for point in raw if isinstance(raw, list) else []:
        if (
            isinstance(point, list)
            and len(point) == 2
            and all(isinstance(v, int | float) and not isinstance(v, bool) for v in point)
        ):
            y, x = (min(max(float(v), 0.0), 1000.0) / 1000 for v in point)
            out.append((x * width, y * height))
    return out
