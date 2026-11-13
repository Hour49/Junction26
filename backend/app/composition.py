"""Composition root: the one place that picks an adapter for each port, from the settings.

Entry points (app/cli.py now, API routes later) build a `Pipeline` here and call its two use
cases; they never import an adapter of a pipeline port themselves. Plugging in a new extractor,
second counter or parser: write the adapter, add its name to the Literal in app/settings.py and a
case below (docs/decisions/0005-pipeline-core.md).
"""

import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from app.adapters.dataset_files import DatasetFiles
from app.adapters.hello import HelloExtractor, HelloParser, HelloSecondCounter
from app.adapters.page_sizes import PageSizes
from app.core.answering.answer import answer_questions
from app.core.answering.model import Question
from app.core.answering.ports import AnswerSink, Clock, DrawingSource, QuestionParser
from app.core.pipeline.ingest import ingest
from app.core.pipeline.model import IngestReport, Route
from app.core.pipeline.ports import DrawingFiles, DrawingSink, Extractor, PageReader, SecondCounter
from app.settings import ExtractorName, QuestionParserName, SecondCounterName, Settings


@dataclass(frozen=True)
class Pipeline:
    """The use cases with their adapters wired in."""

    files: DrawingFiles
    pages: PageReader
    extractors: Mapping[Route, Extractor]
    second_counter: SecondCounter
    parser: QuestionParser
    clock: Clock

    def ingest(self, paths: Iterable[str], sink: DrawingSink) -> IngestReport:
        return ingest(
            paths,
            files=self.files,
            pages=self.pages,
            extractors=self.extractors,
            second_counter=self.second_counter,
            sink=sink,
        )

    def answer_questions(
        self, questions: Iterable[Question], drawings: DrawingSource, sink: AnswerSink
    ) -> dict[str, int]:
        return answer_questions(
            questions, drawings=drawings, parser=self.parser, clock=self.clock, sink=sink
        )


def build_pipeline(settings: Settings, dataset: Path) -> Pipeline:
    """`dataset` is the folder that the drawings' paths (`data/<source>/<name>`) are relative to."""
    files = DatasetFiles(dataset)
    return Pipeline(
        files=files,
        pages=PageSizes(files),
        extractors={
            "bim": _extractor(settings.extractor_bim),
            "cad": _extractor(settings.extractor_cad),
            "vector": _extractor(settings.extractor_vector),
            "raster": _extractor(settings.extractor_raster),
        },
        second_counter=_second_counter(settings.second_counter),
        parser=_parser(settings.question_parser),
        clock=time.perf_counter,
    )


def _extractor(name: ExtractorName) -> Extractor:
    match name:
        case "hello":
            return HelloExtractor()


def _second_counter(name: SecondCounterName) -> SecondCounter:
    match name:
        case "hello":
            return HelloSecondCounter()


def _parser(name: QuestionParserName) -> QuestionParser:
    match name:
        case "hello":
            return HelloParser()
