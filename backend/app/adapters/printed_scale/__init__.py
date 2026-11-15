"""`RASTER_PRINTED_SCALE`: a raster sheet's printed scale and printed counts, read by a
`PrintedReader`, replace its estimated scale and check its counts (app/core/pipeline/printed.py).

`PrintedScale(inner, reader, files)` wraps the raster `Extractor` outside `PriorScale`, so the
door estimate is made first and kept as the second value of a `scale` conflict. The image's
resolution, which turns a printed ratio into metres per pixel, is what the file itself states
(PNG pHYs, JPEG density), trusted only as `printed.trusted_dpi` says, and never on a camera
photo (`kind_of`: ingest's content kind), whose dpi is the camera's, not the paper's.

The reader is the Carbon reader's `printed_scale` and `printed_facts` plus the scale bar's ends on
a full-resolution tile (`carbon`, app/adapters/printed_scale/carbon.py). It reads the sheet at the
same time as the inner reader (app/adapters/beside.py): neither needs the other's result. Its read
is a `printed_scale` step after the inner reader's steps (decision 0018).
"""

import io
from collections.abc import Callable

from PIL import Image

from app.adapters.beside import beside
from app.core.pipeline.model import DrawingFile, Extracted, Sheet, StepTrace
from app.core.pipeline.ports import DrawingFiles, Extractor, PrintedReader
from app.core.pipeline.printed import PrintedSheet, trusted_dpi, with_printed
from app.core.pipeline.printed_answer import printed_answers
from app.core.pipeline.steps import Span, cached_words, timed
from app.core.wording import SCALE_WORDS, count

# The content kinds of a camera photo (ingest's probe: camera EXIF): a camera writes its own
# dpi, which says nothing about the paper (QA R3-B6, T4: a book page at "300 dpi" gave 227 m²)
CAMERA = frozenset({"photo_plan", "photo"})


class PrintedScale:
    def __init__(
        self,
        inner: Extractor,
        reader: PrintedReader,
        files: DrawingFiles,
        kind_of: Callable[[str], str | None] = lambda path: None,
        answers: bool = False,
    ) -> None:
        self._inner = inner
        self._reader = reader
        self._files = files
        self._kind_of = kind_of  # the content kind ingest gave a file, by its path
        self._answers = answers  # PRINTED_TOTAL_ANSWERS: an exactly matching count is reported

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        if not sheet.pages:
            return self._inner.extract(source, sheet)
        (found, _), (printed, span) = beside(  # independent reads: at the same time
            lambda: timed(lambda: self._inner.extract(source, sheet)),
            lambda: timed(lambda: self._reader.read(source, sheet)),
        )
        # a printed ratio needs the paper's resolution: never a camera's (QA R3-B6)
        camera = self._kind_of(source.path) in CAMERA
        dpi = None if camera else trusted_dpi(stated_dpi(self._files.read(source.path)))
        result = with_printed(found, printed, sheet.pages, dpi)
        if self._answers:
            result = printed_answers(result, printed.printed_facts)
        steps = (*found.steps, _step(printed, span, result))
        return result.model_copy(update={"steps": steps})


def _step(printed: PrintedSheet, span: Span, result: Extracted) -> StepTrace:
    """The printed read as a step: what it read, and the scale the sheet ends with."""
    said = [f"printed scale {printed.printed_scale}" if printed.printed_scale else "no scale"]
    # why a read scale was not used ("...: read, not used (... no resolution to trust)", or "...
    # more than 2x the scale estimated from the doors: not used, ..."), from with_printed's notes
    why = next((n for n in result.notes if n.startswith("printed scale") and "not used" in n), None)
    if printed.printed_scale and why is not None:
        said[0] = why
    if printed.bars:
        said.append(count(len(printed.bars), "scale bar"))
    if printed.printed_facts:
        said.append(count(len(printed.printed_facts), "printed count"))
    said.append(f"the sheet's scale: {SCALE_WORDS[result.scale.status]}")
    if span.faults:
        said.append(f"{count(span.faults, 'model call')} got no answer")
    if cached := cached_words(span):
        said.append(cached)
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
