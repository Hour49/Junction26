"""`KindProbe`: ingest's content probe (stage 3) with the sheet-kind signal on top.

It asks the wrapped probe first. For a drawing image (png_plan, jpeg_plan) it then reads the signal
and writes it into `Probed.did`, which ingest puts in the file's identify trace. One the signal
flags as a photo of a plan becomes `photo_plan`, so the rectifier sees it as a photo (the probe
alone needs camera EXIF for that). One it calls not a drawing (P >= 0.5) becomes `unknown`, which
ingest sets aside: no count is read off a page with no drawing (QA R2-qa5-1). When the signal is not
available, the probe's answer stands and the trace says "kind signal not available: <why>". Nothing
else is sent: on a PDF, a photo the camera EXIF already marks, a model or text the signal changes no
kind or route, and each call costs 0.6-2.9 s (ingest-4, 2026-11-14).
"""

from app.adapters.decisions_kind import KindReader, KindSignal
from app.core.ingest.model import ContentKind, Probed
from app.core.ingest.ports import ContentProbe

ASKED: frozenset[ContentKind] = frozenset({"png_plan", "jpeg_plan"})  # what it can change


class KindProbe:
    def __init__(self, inner: ContentProbe, reader: KindReader) -> None:
        self._inner = inner
        self._reader = reader

    def probe(self, data: bytes) -> Probed:
        probed = self._inner.probe(data)
        if probed.kind not in ASKED:
            return probed
        signal = self._reader.read(data)
        if not isinstance(signal, KindSignal):
            return probed.model_copy(update={"did": f"{probed.did}; {signal.note}"})
        if signal.not_drawing:
            return Probed(kind="unknown", did=f"not a drawing: {probed.did}; {signal.line()}")
        if signal.photo:
            return Probed(kind="photo_plan", did=f"{probed.did}; {signal.line()} -> photo_plan")
        return probed.model_copy(update={"did": f"{probed.did}; {signal.line()}"})
