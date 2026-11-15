"""`RASTER_PRINTED_SCALE`: a raster sheet's printed scale and printed counts, read by a
`PrintedReader`, replace its estimated scale and check its counts (app/core/pipeline/printed.py).

`PrintedScale(inner, reader, files)` wraps the raster `Extractor` outside `PriorScale`, so the
door estimate is made first and kept as the second value of a `scale` conflict. The image's
resolution, which turns a printed ratio into metres per pixel, is what the file itself states
(PNG pHYs, JPEG density), trusted only as `printed.trusted_dpi` says.

The reader is the Carbon reader's `printed_scale` and `printed_facts` plus the scale bar's ends on
a full-resolution tile (`carbon`, app/adapters/printed_scale/carbon.py). It reads the sheet at the
same time as the inner reader (app/adapters/beside.py): neither needs the other's result. Its read
is a `printed_scale` step after the inner reader's steps (decision 0018).
"""

import io

from PIL import Image

from app.adapters.beside import beside
from app.core.pipeline.model import DrawingFile, Extracted, Sheet, StepTrace
from app.core.pipeline.ports import DrawingFiles, Extractor, PrintedReader
from app.core.pipeline.printed import PrintedSheet, trusted_dpi, with_printed
from app.core.pipeline.steps import Span, timed
from app.core.wording import SCALE_WORDS, count


class PrintedScale:
    def __init__(self, inner: Extractor, reader: PrintedReader, files: DrawingFiles) -> None:
        self._inner = inner
        self._reader = reader
        self._files = files

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        if not sheet.pages:
            return self._inner.extract(source, sheet)
        (found, _), (printed, span) = beside(  # independent reads: at the same time
            lambda: timed(lambda: self._inner.extract(source, sheet)),
            lambda: timed(lambda: self._reader.read(source, sheet)),
        )
        dpi = trusted_dpi(stated_dpi(self._files.read(source.path)))
        result = with_printed(found, printed, sheet.pages, dpi)
        steps = (*found.steps, _step(printed, span, result))
        return result.model_copy(update={"steps": steps})


def _step(printed: PrintedSheet, span: Span, result: Extracted) -> StepTrace:
    """The printed read as a step: what it read, and the scale the sheet ends with."""
    said = [f"printed scale {printed.printed_scale}" if printed.printed_scale else "no scale"]
    if printed.bars:
        said.append(count(len(printed.bars), "scale bar"))
    if printed.printed_facts:
        said.append(count(len(printed.printed_facts), "printed count"))
    said.append(f"the sheet's scale: {SCALE_WORDS[result.scale.status]}")
    if span.faults:
        said.append(f"{count(span.faults, 'model call')} got no answer")
    return StepTrace(
        id="printed_scale",
        label="Printed scale and counts (Gemini Carbon)",
        did="; ".join(said),
        at_ms=span.at_ms,
        ms=span.ms,
        cost_usd=span.cost_usd,
        state="failed" if span.faults else "done",
    )


def stated_dpi(data: bytes) -> tuple[float, float] | None:
    """The resolution the image file states, or None (no image, or none stated)."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            dpi = image.info.get("dpi")
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    if not isinstance(dpi, tuple) or len(dpi) != 2:
        return None
    x, y = (float(value) for value in dpi)
    return x, y
