"""Composition root: the one place that picks an adapter for each port, from the settings.

Entry points (app/cli.py now, API routes later) build a `Pipeline` here and call its two use
cases; they never import an adapter of a pipeline port themselves. Plugging in a new extractor,
second counter or parser: write the adapter, add its name to the Literal in app/settings.py and a
case below (docs/decisions/0005-pipeline-core.md).
"""

import secrets
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache, partial
from pathlib import Path

from app.adapters.answer_policy import load_policy
from app.adapters.answer_prior import DEV_PRIOR, NoPrior, TablePrior
from app.adapters.archive import (
    DiskProjectStore,
    ExifFrame,
    FileProbe,
    InlineRunner,
    NoRectifier,
    ThreadRunner,
    ZipUnpacker,
)
from app.adapters.archive.probe import is_scanned_pdf
from app.adapters.dataset_files import DatasetFiles, DatasetSheetModels
from app.adapters.decisions.client import DecisionsClient
from app.adapters.decisions.g1main import G1MainReader
from app.adapters.decisions.uses import DecisionsConfidence, DecisionsCountExtractor
from app.adapters.decisions_kind import KindReader
from app.adapters.decisions_kind.probe import KindProbe
from app.adapters.hello import (
    HelloExtractor,
    HelloParser,
    HelloSecondCounter,
    HelloSourceFinder,
)
from app.adapters.ifc_model import IfcModelExtractor, IfcModels, IfcSecondCounter
from app.adapters.page_sizes import PageSizes
from app.adapters.paths import inside
from app.adapters.pdf_tables import PdfTables
from app.adapters.pdf_tables.schedule_check import ScheduleTagCounter
from app.adapters.question_templates import TemplateParser
from app.adapters.raster import assemble, parse_components
from app.adapters.raster.precomputed import PrecomputedExtractor, WholePagePlan
from app.adapters.raster_detector import OnnxDetector
from app.adapters.raster_ocr.gemini import GeminiClient, GeminiRoomExtractor, GeminiRoomReader
from app.adapters.raster_ocr.region_rooms import RegionRooms, SegmenterRegion
from app.adapters.raster_region import RegionDetector, load_region
from app.adapters.raster_remote import HttpReaderClient, RemoteReader
from app.adapters.raster_scale import PriorScale
from app.adapters.rectifier import R3Rectifier
from app.adapters.rectifier.uvdoc import OnnxUvdoc
from app.adapters.vector_pdf import PdfSecondCounter, PdfVectorExtractor
from app.core.answering.answer import answer_questions
from app.core.answering.model import Question
from app.core.answering.ports import (
    AnswerConfidence,
    AnswerPrior,
    AnswerSink,
    Clock,
    DrawingSource,
    QuestionParser,
)
from app.core.errors import DomainError, InvalidInputError
from app.core.ingest.ports import ContentProbe, Rectifier
from app.core.ingest.service import IngestService
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
from app.core.pipeline.route import RICHEST_FIRST
from app.settings import (
    AnswerPriorName,
    ExtractorName,
    QuestionParserName,
    RectifierName,
    SecondCounterName,
    Settings,
    TablesName,
)

# The experiment arms' extraction_v1 files: data/stoa/exp/<track>/<arm>/ (RASTER_COMPONENTS exp:).
EXP_DIR = Path(__file__).resolve().parents[2] / "data" / "stoa" / "exp"
# core's exported detectors: data/models/detector/<arm>/ (RASTER_COMPONENTS detector:<arm>).
DETECTOR_DIR = Path(__file__).resolve().parents[2] / "data" / "models" / "detector"
UVDOC_MODEL = Path(__file__).resolve().parents[2] / "data" / "models" / "photo" / "uvdoc.onnx"
# core's tune runs (counts.py tune): detector:<arm>:<run> reads <run>.thresholds.json from here.
DETECTOR_RUNS = EXP_DIR / "detector" / "raw"


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
    prior_families: frozenset[tuple[str, str]] = frozenset()  # ANSWER_POLICY
    # The routes whose extractor reads something: a route on "hello" never takes a drawing from
    # one that has a reader (stage 5)
    readable: frozenset[Route] = frozenset(RICHEST_FIRST)
    # Whether a PDF is a scan, which stage 5 routes to the raster reader; None: none is
    scanned: Callable[[bytes], bool] | None = None
    # Gemini Decisions' probability for each drawing answer (DECISIONS_CONFIDENCE); None: off
    confidence: AnswerConfidence | None = None

    def ingest(self, paths: Iterable[str], sink: DrawingSink) -> IngestReport:
        return ingest(
            paths,
            files=self.files,
            finder=self.finder,
            pages=self.pages,
            extractors=self.extractors,
            second_counter=self.second_counter,
            sink=sink,
            readable=self.readable,
            scanned=self.scanned,
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
            prior_families=self.prior_families,
            confidence=self.confidence,
        )


def build_pipeline(settings: Settings, dataset: Path) -> Pipeline:
    """`dataset` is the folder that the drawings' paths (`data/<source>/<name>`) are relative to."""
    files = DatasetFiles(dataset)
    models = IfcModels(files)
    # A sheet is paired with its building model only when the model route can read it.
    with_models = settings.extractor_bim == "ifc"
    # One Decisions reader for the count swap and the confidence, made only when one is used.
    decisions = cache(lambda: decisions_reader(settings))
    return Pipeline(
        files=files,
        finder=DatasetSheetModels(dataset) if with_models else HelloSourceFinder(),
        pages=PageSizes(files),
        extractors={
            "bim": _extractor(settings.extractor_bim, files, models),
            "cad": _extractor(settings.extractor_cad, files, models),
            "vector": _tables(
                settings.tables, _extractor(settings.extractor_vector, files, models), files
            ),
            # A precomputed arm finds an uploaded sheet in the Stoa dataset by its content. A PDF
            # whose page 1 is not a vector plan is read here, so its schedules are read (and its
            # schedule checks noted) as on the vector route.
            "raster": _tables(
                settings.tables, _scaled(settings, _raster(settings, files, decisions)), files
            ),
        },
        second_counter=_checked(
            settings.tables, _second_counter(settings.second_counter, files, models), files
        ),
        parser=_parser(settings.question_parser),
        prior=_prior(settings.answer_prior),
        clock=time.perf_counter,
        prior_families=_policy(settings.answer_policy),
        readable=_readable(settings),
        scanned=is_scanned_pdf,
        confidence=DecisionsConfidence(files, decisions())
        if settings.decisions_confidence
        else None,
    )


def _probe(settings: Settings) -> ContentProbe:
    """Ingest's content probe; with DECISIONS_KIND, the Gemini sheet-kind signal on top."""
    if not settings.decisions_kind:
        return FileProbe()
    client = DecisionsClient(
        settings.gemini_api_key.get_secret_value(), settings.decisions_timeout_s
    )
    return KindProbe(FileProbe(), KindReader(client, settings.decisions_cache_dir))


def _rectifier(name: RectifierName) -> Rectifier:
    match name:
        case "none":
            return NoRectifier()
        case "r3":
            try:
                return R3Rectifier(OnnxUvdoc(UVDOC_MODEL))
            except DomainError as error:
                raise InvalidInputError(f"RECTIFIER=r3: {error}") from error


def _readable(settings: Settings) -> frozenset[Route]:
    """The routes whose extractor is not the hello-world one."""
    names: dict[Route, str] = {
        "bim": settings.extractor_bim,
        "cad": settings.extractor_cad,
        "vector": settings.extractor_vector,
        "raster": settings.extractor_raster,
    }
    return frozenset(found for found, name in names.items() if name != "hello")


@dataclass(frozen=True)
class Answering:
    """What the API answers a question with: the parser and prior the settings name."""

    parser: QuestionParser
    prior: AnswerPrior
    clock: Clock
    prior_families: frozenset[tuple[str, str]]  # ANSWER_POLICY, as the pipeline has it
    # DECISIONS_CONFIDENCE: the answer confidence over the files a drawing was read from; None: off
    confidence: Callable[[DrawingFiles], AnswerConfidence] | None = None
    signal: str | None = None  # what that confidence's score is, by name (`g1main`)


def build_answering(settings: Settings) -> Answering:
    confidence: Callable[[DrawingFiles], AnswerConfidence] | None = None
    signal: str | None = None
    if settings.decisions_confidence:
        reader = decisions_reader(settings)  # one reader: its disk cache is the count swap's too
        confidence = partial(DecisionsConfidence, reader=reader)
        signal = DECISIONS_SIGNAL
    return Answering(
        parser=_parser(settings.question_parser),
        prior=_prior(settings.answer_prior),
        clock=time.perf_counter,
        prior_families=_policy(settings.answer_policy),
        confidence=confidence,
        signal=signal,
    )


def readers(settings: Settings) -> dict[str, str]:
    """The adapter each port uses, by port, as the API reports it."""
    return {
        "bim": settings.extractor_bim,
        "cad": settings.extractor_cad,
        "vector": settings.extractor_vector,
        "raster": settings.extractor_raster,
        "tables": settings.tables,
        "second_counter": settings.second_counter,
        "rectifier": settings.rectifier,
        "question_parser": settings.question_parser,
        "answer_prior": settings.answer_prior,
        "decisions_kind": str(settings.decisions_kind),  # as ingest records it
    }


# The answer confidence's score: Gemini Decisions' probability for the answered count (G1main's
# choice distribution), raw: not calibrated against right answers
DECISIONS_SIGNAL = "g1main"
# RASTER_COMPONENTS sources that call a service with a key (Gemini, the Verda model server)
KEYED_SOURCES = frozenset({"gemini", "regionrooms", "verda", "decisions", "decisions-s1536"})


def uses_keys(settings: Settings) -> bool:
    """Whether a reader or the answer confidence calls a service that needs an API key."""
    sources = [part.partition("=")[2] for part in settings.raster_components.split(",") if part]
    keyed = any(source.split(":", 1)[0] in KEYED_SOURCES for source in sources)
    raster = settings.extractor_raster == "composite" and keyed
    return raster or settings.decisions_confidence or settings.decisions_kind


def build_ingest(settings: Settings, root: Path, *, background: bool = True) -> IngestService:
    """Project ingest over the projects folder `root` (data/projects/). `background` False runs
    each upload inside `start` (CLI, tests). The readers' names are part of the cache key, so a
    changed reader ingests a file again. Reader settings that do not build raise here, so the
    app fails at startup instead of setting every upload aside."""
    build_pipeline(settings, root)
    store = DiskProjectStore(root)
    names = {
        "bim": settings.extractor_bim,
        "cad": settings.extractor_cad,
        "vector": settings.extractor_vector,
        "raster": settings.extractor_raster,
        "raster_components": settings.raster_components,
        "tables": settings.tables,
        "second_counter": settings.second_counter,
        "rectifier": settings.rectifier,  # it makes the frame every box is in
        "decisions_kind": str(settings.decisions_kind),  # it can make an image a photo
    }
    if settings.raster_scale != "off":  # named only when on: the default keeps its cache keys
        names["raster_scale"] = settings.raster_scale
    service = IngestService(
        unpacker=ZipUnpacker(),
        probe=_probe(settings),
        frame=ExifFrame(),
        rectifier=_rectifier(settings.rectifier),
        store=store,
        readers=lambda project_id: build_pipeline(settings, store.files_dir(project_id)),
        reader_names=names,
        runner=ThreadRunner() if background else InlineRunner(),
        clock=time.perf_counter,
        now=lambda: datetime.now(UTC).isoformat(timespec="seconds"),
        new_id=lambda: secrets.token_hex(6),
    )
    service.recover()  # a project a restart cut off is marked failed, not left running
    return service


def _extractor(name: ExtractorName, files: DrawingFiles, models: IfcModels) -> Extractor:
    match name:
        case "hello":
            return HelloExtractor()
        case "pdf":
            return PdfVectorExtractor(files)
        case "ifc":
            return IfcModelExtractor(files, models)


def _tables(name: TablesName, inner: Extractor, files: DrawingFiles) -> Extractor:
    match name:
        case "off":
            return inner
        case "pdf":
            return PdfTables(inner, files)


def _raster(
    settings: Settings, files: DrawingFiles, decisions: Callable[[], G1MainReader]
) -> Extractor:
    components = settings.raster_components
    match settings.extractor_raster:
        case "hello":
            return HelloExtractor()
        case "composite":
            try:
                return assemble(
                    parse_components(components),
                    lambda source: _raster_component(source, settings, files, decisions),
                )
            except DomainError as error:
                raise InvalidInputError(f"RASTER_COMPONENTS={components!r}: {error}") from error


def _scaled(settings: Settings, inner: Extractor) -> Extractor:
    """RASTER_SCALE=priors: a raster sheet without a scale gets an estimated one."""
    match settings.raster_scale:
        case "off":
            return inner
        case "priors":
            composite = settings.extractor_raster == "composite"
            if composite and "scale" in parse_components(settings.raster_components):
                raise InvalidInputError(
                    "RASTER_SCALE=priors estimates the scale itself: drop scale= from "
                    "RASTER_COMPONENTS, or set RASTER_SCALE=off"
                )
            return PriorScale(inner)


def _raster_component(
    source: str, settings: Settings, files: DrawingFiles, decisions: Callable[[], G1MainReader]
) -> Extractor:
    """The reader of one RASTER_COMPONENTS source name. A precomputed arm finds an uploaded sheet
    in the Stoa dataset (CREDIT_DATASET, the folder its files are relative to) by its content."""
    kind, _, where = source.partition(":")
    match kind:
        case "one-plan" if not where:
            return WholePagePlan()
        case "exp" if where:
            return PrecomputedExtractor(EXP_DIR / where, settings.credit_dataset)
        case "dir" if where:
            return PrecomputedExtractor(Path(where), settings.credit_dataset)
        case "detector" if where:
            arm, _, run = where.partition(":")
            tuned = inside(DETECTOR_RUNS, f"{run}.thresholds.json") if run else None
            return OnnxDetector.from_folder(files, inside(DETECTOR_DIR, arm), tuned)
        case "verda" if not where:
            client = HttpReaderClient(
                settings.verda_reader_url,
                settings.verda_inference_api_key.get_secret_value(),
                max_in_flight=settings.verda_reader_max_in_flight,
            )
            return RemoteReader(files, client)
        case "gemini" if not where:
            return _gemini_rooms(settings, files)
        case "regionrooms" if not where:
            if not settings.region_model_dir:
                raise InvalidInputError("RASTER_COMPONENTS: regionrooms needs REGION_MODEL_DIR")
            region = SegmenterRegion(*load_region(Path(settings.region_model_dir)))
            return RegionRooms(_gemini_rooms(settings, files), files, region)
        case "region" if where:
            region = Path(settings.region_model_dir) if settings.region_model_dir else None
            return RegionDetector.from_folders(files, inside(DETECTOR_DIR, where), region)
        case "decisions" if where:
            inner = _raster_component(where, settings, files, decisions)
            return DecisionsCountExtractor(inner, files, decisions())
        case "decisions-s1536" if where:
            inner = _raster_component(where, settings, files, decisions)
            return DecisionsCountExtractor(inner, files, decisions(), arm="S1536")
        case _:
            raise InvalidInputError(
                f"RASTER_COMPONENTS: unknown source {source!r}; sources are "
                "exp:<track>/<arm>, dir:<path>, detector:<arm>[:<tune run>], region:<arm>, verda, "
                "gemini, regionrooms, decisions:<source>, decisions-s1536:<source> and one-plan"
            )


def _gemini_rooms(settings: Settings, files: DrawingFiles) -> Extractor:
    client = GeminiClient(
        settings.gemini_api_key.get_secret_value(), settings.gemini_model, settings.gemini_timeout_s
    )
    return GeminiRoomExtractor(files, GeminiRoomReader(client, settings.gemini_cache_dir))


def decisions_reader(settings: Settings) -> G1MainReader:
    """Gemini Decisions' count reader. The count swap and the answer confidence share its cache
    (DECISIONS_CACHE_DIR), so each page is paid for once."""
    key = settings.gemini_api_key.get_secret_value()
    client = DecisionsClient(key, settings.decisions_timeout_s)
    return G1MainReader(client, settings.decisions_cache_dir)


def _checked(name: TablesName, inner: SecondCounter, files: DrawingFiles) -> SecondCounter:
    """TABLES=pdf also counts the doors of a PDF set twice: its door schedule, its plans' tags."""
    match name:
        case "off":
            return inner
        case "pdf":
            return ScheduleTagCounter(inner, files)


def second_counter_of(names: Mapping[str, str], route: Route | None) -> str:
    """The second counter that measured a drawing of `route`, by name (`names`: readers()): the
    IFC one measures a model (the bim route) and passes every other file on to the PDF counter
    (_second_counter)."""
    name = names["second_counter"]
    return "pdf" if name == "ifc" and route != "bim" else name


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


def _policy(path: str) -> frozenset[tuple[str, str]]:
    return load_policy(Path(path)) if path else frozenset()


def _prior(name: AnswerPriorName) -> AnswerPrior:
    match name:
        case "none":
            return NoPrior()
        case "dev":
            return TablePrior(DEV_PRIOR)
