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

from app.adapters.answer_prior import DEV_PRIOR, NoPrior, TablePrior
from app.adapters.dataset_files import DatasetFiles, DatasetSheetModels
from app.adapters.hello import (
    HelloExtractor,
    HelloParser,
    HelloSecondCounter,
    HelloSourceFinder,
)
from app.adapters.ifc_model import IfcModelExtractor, IfcModels, IfcSecondCounter
from app.adapters.page_sizes import PageSizes
from app.adapters.question_templates import TemplateParser
from app.adapters.vector_pdf import PdfSecondCounter, PdfVectorExtractor
from app.core.answering.answer import answer_questions
from app.core.answering.model import Question
from app.core.answering.ports import (
    AnswerPrior,
    AnswerSink,
    Clock,
    DrawingSource,
    QuestionParser,
)
from app.core.pipeline.ingest import ingest
from app.core.pipeline.model import IngestReport, Route
from app.core.pipeline.ports import (
    DrawingFiles,
    DrawingSink,
    Extractor,
    PageReader,
    SecondCounter,
    SourceFinder,
)
from app.settings import (
    AnswerPriorName,
    ExtractorName,
    QuestionParserName,
    SecondCounterName,
    Settings,
)


@dataclass(frozen=True)
class Pipeline:
    """The use cases with their adapters wired in."""

    files: DrawingFiles
    finder: SourceFinder
    pages: PageReader
    extractors: Mapping[Route, Extractor]
    second_counter: SecondCounter
    parser: QuestionParser
    prior: AnswerPrior
    clock: Clock

    def ingest(self, paths: Iterable[str], sink: DrawingSink) -> IngestReport:
        return ingest(
            paths,
            files=self.files,
            finder=self.finder,
            pages=self.pages,
            extractors=self.extractors,
            second_counter=self.second_counter,
            sink=sink,
        )

    def answer_questions(
        self, questions: Iterable[Question], drawings: DrawingSource, sink: AnswerSink
    ) -> dict[str, int]:
        return answer_questions(
            questions,
            drawings=drawings,
            parser=self.parser,
            clock=self.clock,
            sink=sink,
            prior=self.prior,
        )


def build_pipeline(settings: Settings, dataset: Path) -> Pipeline:
    """`dataset` is the folder that the drawings' paths (`data/<source>/<name>`) are relative to."""
    files = DatasetFiles(dataset)
    models = IfcModels(files)
    # A sheet is paired with its building model only when the model route can read it.
    with_models = settings.extractor_bim == "ifc"
    return Pipeline(
        files=files,
        finder=DatasetSheetModels(dataset) if with_models else HelloSourceFinder(),
        pages=PageSizes(files),
        extractors={
            "bim": _extractor(settings.extractor_bim, files, models),
            "cad": _extractor(settings.extractor_cad, files, models),
            "vector": _extractor(settings.extractor_vector, files, models),
            "raster": _extractor(settings.extractor_raster, files, models),
        },
        second_counter=_second_counter(settings.second_counter, files, models),
        parser=_parser(settings.question_parser),
        prior=_prior(settings.answer_prior),
        clock=time.perf_counter,
    )


def _extractor(name: ExtractorName, files: DrawingFiles, models: IfcModels) -> Extractor:
    match name:
        case "hello":
            return HelloExtractor()
        case "pdf":
            return PdfVectorExtractor(files)
        case "ifc":
            return IfcModelExtractor(files, models)


def _second_counter(
    name: SecondCounterName, files: DrawingFiles, models: IfcModels
) -> SecondCounter:
    match name:
        case "hello":
            return HelloSecondCounter()
        case "pdf":
            return PdfSecondCounter(files)
        case "ifc":
            return IfcSecondCounter(files, models, PdfSecondCounter(files))


def _parser(name: QuestionParserName) -> QuestionParser:
    match name:
        case "hello":
            return HelloParser()
        case "templates":
            return TemplateParser()


def _prior(name: AnswerPriorName) -> AnswerPrior:
    match name:
        case "none":
            return NoPrior()
        case "dev":
            return TablePrior(DEV_PRIOR)
