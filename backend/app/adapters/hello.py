"""The hello-world adapters: each one implements a port by doing nothing, so the whole pipeline
runs end to end and scores near zero. A real adapter replaces one of them in app/composition.py;
these stay as the floor to compare against."""

from collections.abc import Sequence

from app.core.answering.model import Query, Unsupported
from app.core.drawing.model import Scale
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, Sheet


class HelloExtractor:
    """The `Extractor` port: reads nothing, so the drawing has no elements and no scale, and says
    it looked for nothing (`read` empty), so none of its counts is a zero."""

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return Extracted(
            method="other",
            scale=Scale(status="no_scale"),
            read=(),
            notes=("hello-world extractor: nothing was read from the drawing",),
        )


class HelloSourceFinder:
    """The `SourceFinder` port: knows of no source beyond the files a run was given."""

    def sources(self, path: str) -> Sequence[str]:
        return ()


class HelloSecondCounter:
    """The `SecondCounter` port: measures nothing a second time, so nothing is ever contested."""

    def measure(self, source: DrawingFile, sheet: Sheet) -> list[Measurement]:
        return []


class HelloParser:
    """The `QuestionParser` port: understands no question, so every answer is a refusal."""

    def parse(self, text: str) -> Query | Unsupported:
        return Unsupported(reason="hello-world parser: no question type is supported yet")
