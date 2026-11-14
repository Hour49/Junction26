"""Settings: the only module that reads env vars or `.env` (docs/ENGINEERING.md section 1).

`.env` is read from the current directory, so run from backend/. Every field is listed in
backend/.env.example, and tests/test_settings.py checks that the two match. Unknown keys in `.env`
are refused, so a typo fails at startup.

The adapter of each pipeline port is chosen here by name and built in app/composition.py. A new
adapter adds its name to the Literal of its port and a case in composition.py.
"""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# pdf: the vector route's reader of drawn PDFs. ifc: the model route's reader of a plan sheet
# with its IFC building model, which also makes ingest look for that model next to the sheet
ExtractorName = Literal["hello", "pdf", "ifc"]
# composite: the raster route's reader built from the component readers RASTER_COMPONENTS names
RasterExtractorName = Literal["hello", "composite"]
# pdf: a drawn PDF sheet's own second readings. ifc: those, and what a sheet's model lists
SecondCounterName = Literal["hello", "pdf", "ifc"]
# r3: the paper border (R1c), else UVDoc unless the plan fills the photo (app/adapters/rectifier)
RectifierName = Literal["none", "r3"]  # the photo rectifier of ingest's normalise stage
# File triage (decision 0010, app/adapters/triage). off: ingest as before triage existed.
# rules: the content probe's kind, no model (sets aside what ingest sets aside today).
# siglip: fixed register heads on a SigLIP2 embedding, CPU (data/models/triage/siglip2-512-v2/);
# with DECISIONS_KIND, a plan when either it or the sheet-kind signal says so.
TriageClassifierName = Literal["off", "rules", "siglip"]
SheetKindName = Literal["off", "carbon"]
# gemini: gemini-3.5-flash fills the description form and its long text, GEMINI_API_KEY's
# key and time limit, replies cached in TRIAGE_DESCRIBER_CACHE_DIR (app/adapters/triage/).
# carbon: the same with gemini-4-carbon at thinking low (rag's pilot), 4 / 20 USD per M tokens;
# it needs GEMINI_TIMEOUT_S of 45 s or more
TriageDescriberName = Literal["off", "gemini", "carbon"]
# rules: the class alone, no model (not a drawing -> unrelated, another drawing -> related)
TriageJudgeName = Literal["off", "rules"]
# What the evidence index holds (decision 0012). set_aside: the images triage set aside and
# described. all_non_plan: also every other file and PDF page that is not a floor plan (a picture
# asked the sheet-kind model, then described; a text document by its own text; others by name)
EvidenceScopeName = Literal["set_aside", "all_non_plan"]
# RESOLVER: a model picks a value for a conflict no rule decides,
# or checks an answer CHECK_POLICY does not certify; never a person's word. off: as before.
# carbon: Google Carbon (the adapter is not built yet: startup refuses it until it is).
ResolverName = Literal["off", "carbon"]
QuestionParserName = Literal["hello", "templates"]  # templates: words to a takeoff query
AnswerPriorName = Literal["none", "dev"]  # dev: a refusal keeps the dev answers' best estimate
# pdf: the vector route also reads the ruled schedules printed on a drawn PDF sheet
TablesName = Literal["off", "pdf"]
# gemini: Google's API. eu: our open model on Verda (app/adapters/openvlm/)
ProviderName = Literal["gemini", "eu"]
# off, or priors: a raster sheet without a scale gets an estimated one (app/adapters/raster_scale/)
RasterScaleName = Literal["off", "priors"]
RasterTilesName = Literal["off", "auto"]  # auto: big sheets read tile by tile by the detector
# furniture: a room keeps the type its reader gave. gold-labels: the printed label overrules it
# on four points, as the dataset's answers do (app/core/pipeline/room_policy.py)
RoomPolicyName = Literal["furniture", "gold-labels"]
# The Carbon reader of raster drawings (app/adapters/carbon/). off; all: every raster drawing;
# advanced: the drawings the sheet-kind step (SHEET_KIND=carbon) called advanced
CarbonReaderName = Literal["off", "advanced", "all"]
# Dollars, zero or more; an empty value (`GEMINI_BUDGET_USD=`) is unset: no limit
Usd = Annotated[
    Annotated[float, Field(ge=0)] | None,
    BeforeValidator(lambda value: None if value == "" else value),
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # The git commit this backend was started from, as GET /api/info `commit` shows it, so a
    # smoke test can tell which build it talks to (tools/qa-env.sh sets the exported commit).
    # Unset: null. Never read from git at request time
    app_commit: str | None = None
    extractor_bim: ExtractorName = "ifc"
    extractor_cad: ExtractorName = "hello"
    extractor_vector: ExtractorName = "pdf"
    extractor_raster: RasterExtractorName = "hello"
    tables: TablesName = "pdf"
    # part=source pairs for EXTRACTOR_RASTER=composite (app/adapters/raster/__init__.py)
    raster_components: str = ""
    # The same for the files ingest identified as camera photos of a plan (photo_plan), e.g. a
    # detector trained on phone photos; empty: photos are read like every other raster
    # (app/adapters/raster/photo.py)
    raster_photo_components: str = ""
    # priors: the raster route estimates a missing scale from its detected doors (none detected:
    # no estimate) and gives each room its outline area at it, both `estimated`
    # (app/adapters/raster_scale/)
    raster_scale: RasterScaleName = "off"
    # auto: a raster page whose long side is over 4000 px is read by every detector source of
    # RASTER_COMPONENTS and DOUBLE_CHECK_READERS on overlapping 2048 px tiles, merged across the
    # seams (app/adapters/raster_detector/tiles.py); its plans still come from the whole page.
    # Photo arms are not tiled. off: every page is letterboxed whole (a door on a 14k px sheet
    # is then a few px)
    raster_tiles: RasterTilesName = "off"
    # How the raster route types the rooms its rooms source read, whichever source that is.
    # gold-labels is for a source that reads printed labels: it turns every unlabelled bedroom
    # into `other`
    room_policy: RoomPolicyName = "furniture"
    # More readers of each raster sheet, <name>=<source> pairs with RASTER_COMPONENTS' sources,
    # e.g. l1=detector:C-yolo26l,m1=detector:C-yolo26m. What each saw is kept with the drawing and
    # never counted: an answer uses it to say where the readers disagree with it
    # (app/core/pipeline/disputed_marks.py). Empty: none
    double_check_readers: str = ""
    # The Gemini room reader of the raster route (app/adapters/raster_ocr/gemini.py), built only
    # when RASTER_COMPONENTS names it: its key (never logged), model, time limit per page, and
    # the folder its replies are cached in (gitignored)
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.5-flash"
    gemini_timeout_s: float = 60.0
    gemini_cache_dir: Path = Path("../data/cache/gemini-rooms")
    # The Gemini spend guard (app/core/spend.py): the dollars every Gemini call of this process
    # (room reader, Decisions, sheet-kind signal, describer, answer confidence) may spend in total,
    # and in any hour. Past either, the Gemini steps answer as when Gemini fails (the answer stays
    # unknown, the note says why; cached replies still serve) and GET /api/info says
    # `gemini: budget_exhausted`. Unset: no limit. 0: no Gemini call at all (the kill switch)
    gemini_budget_usd: Usd = None
    gemini_budget_usd_per_hour: Usd = None
    # Gemini Decisions count distributions (app/adapters/decisions/, same GEMINI_API_KEY). The
    # count swap is on when RASTER_COMPONENTS names decisions:<source>; the answer confidence when
    # DECISIONS_CONFIDENCE is true. Seconds per request, and the folder replies are cached in
    decisions_confidence: bool = False
    decisions_timeout_s: float = 30.0
    decisions_cache_dir: Path = Path("../data/cache/decisions")
    # The sheet-kind signal at ingest (app/adapters/decisions_kind/, same key, timeout and cache
    # folder): Gemini's photo-of-a-plan flag and P(floor plan) for each uploaded image or PDF
    decisions_kind: bool = False
    # The Carbon reader (app/adapters/carbon/; brief r8 AS-2, .agents/exp/carbon-reader.md):
    # gemini-4-carbon reads page 1 of a raster drawing whole and in full-resolution tiles, with
    # GEMINI_API_KEY and the spend guard (charged at 4/20 USD per million tokens). CARBON_READER
    # routes raster drawings to it alone instead of RASTER_COMPONENTS' reader (needs
    # EXTRACTOR_RASTER=composite); ingest flags each such drawing, so none of its answers is
    # certified. As a source it is `carbon` in RASTER_COMPONENTS or DOUBLE_CHECK_READERS.
    # Seconds per call, and the folder replies are cached in (gitignored)
    carbon_reader: CarbonReaderName = "off"
    carbon_timeout_s: float = 120.0
    carbon_cache_dir: Path = Path("../data/cache/carbon-reader")
    # EU open models (app/adapters/openvlm/): our vLLM server on Verda (Finland), reached by an SSH
    # tunnel. Each Gemini step picks its provider; "eu" sends it to this server instead (no
    # fallback to Gemini on an error). URL, key (never logged), model, seconds per request
    eu_vlm_base_url: str = "http://127.0.0.1:18431/v1"
    eu_vlm_api_key: SecretStr = SecretStr("")
    eu_vlm_model: str = "Qwen/Qwen3.8-27B-FP8"
    eu_vlm_timeout_s: float = 300.0
    rooms_provider: ProviderName = "gemini"  # the room reader (sources gemini, regionrooms)
    decisions_provider: ProviderName = "gemini"  # G1main counts: swap and answer confidence
    kind_provider: ProviderName = "gemini"  # the sheet-kind signal (DECISIONS_KIND)
    # The detector served on Verda (app/adapters/raster_remote/, source `verda`), built only when
    # RASTER_COMPONENTS names it: endpoint URL, inference key (never logged), requests open at once
    verda_reader_url: str = ""
    verda_inference_api_key: SecretStr = SecretStr("")
    verda_reader_max_in_flight: int = Field(default=4, ge=1)
    # The region arm (app/adapters/raster_region/, source `region:<detector arm>`), built only when
    # RASTER_COMPONENTS names it: the annotated-flat segmenter's folder ("" reads the whole page)
    region_model_dir: str = "../data/models/region/R1-unet34"
    # The local count arbiter T1 (app/adapters/count_arbiter/, source `arbiter-t1:<arm>`), built
    # only when RASTER_COMPONENTS names it: its model, prior and L1 page-count model
    arbiter_model_dir: Path = Path("../data/models/arbiter/T1")
    second_counter: SecondCounterName = "ifc"
    question_parser: QuestionParserName = "templates"
    answer_prior: AnswerPriorName = "none"
    # golden's policy.json (answer_policy_v1): the families answered from the prior even when
    # the drawing gives a value (app/adapters/answer_policy.py); "" none
    answer_policy: str = ""
    # golden's gate.json (gate_policy_v1): per family, the confidence at or above which an answer
    # is marked sure (app/adapters/gate_policy.py); needs DECISIONS_CONFIDENCE; "" none
    gate_policy: str = ""
    # golden's check policy (check_policy_v1): the answers certified as they are; every other
    # takeoff answer asks for a double-check (app/core/review/check.py); "" off
    check_policy: str = ""
    # RESOLVER (ResolverName above): off, or the model that checks conflicts and uncertain answers
    resolver: ResolverName = "off"
    resolver_model: str = "gemini-4-carbon"  # RESOLVER=carbon's model (GEMINI_API_KEY)
    resolver_timeout_s: float = 30.0  # POST /api/ask waits for it inline
    resolver_cache_dir: Path = Path("../data/cache/resolver")  # replies by request, paid once
    # local-dec's local gate models (local_gate_v1, comma separated): a check policy family whose
    # threshold is on one of their signals is scored by it (app/core/review/check.py); read only
    # with CHECK_POLICY set; "" none
    local_gates: str = ""
    # Uploaded projects, drawing models and review edits (gitignored); relative to backend/
    projects_dir: Path = Path("../data/projects")
    # The synthetic demo archive (backend/scripts/make_sample_archive.py writes it); for /sample
    sample_archive: Path = Path("../data/samples/sample-project.zip")
    # Where a drawing's licence credit is looked up by content (app/adapters/credits.py): the
    # Stoa dataset (its data/<source>/LICENSE.md) and the Commons demo photos (manifest.jsonl)
    credit_dataset: Path = Path("../data/stoa/full/junction-dataset")
    credit_photos: Path = Path("../data/stoa/exp/photo/real/commons")
    # none: images are read as uploaded (EXIF turned upright); a rectifier undoes a photo's
    # perspective first (app/core/ingest/ports.py Rectifier)
    rectifier: RectifierName = "none"
    # The building-code rule packs, one JSON file per pack (decision 0009); by default the ones
    # shipped in app/rules. A pack that does not validate (a rule without its clause) stops start
    rule_packs_dir: Path = Path(__file__).parent / "rules"
    # The building-law knowledge base, <pack>/<law id>.json (decision 0014); the AI searches it.
    # A law file that does not validate stops start, naming the file
    laws_dir: Path = Path(__file__).parent / "laws"
    # File triage (decision 0010): is each uploaded image a floor plan; a non-plan is kept, set
    # aside, described and judged against the project. The describer and judge run only with a
    # classifier on (TRIAGE_CLASSIFIER, or SHEET_KIND below).
    triage_classifier: TriageClassifierName = "off"
    triage_describer: TriageDescriberName = "off"
    triage_describer_cache_dir: Path = Path("../data/cache/triage-describer")
    triage_judge: TriageJudgeName = "off"
    # The VLM sheet-kind step (.agents/exp/vlm-kind.md, app/adapters/triage/sheet_kind.py): carbon
    # asks gemini-4-carbon (GEMINI_API_KEY) what each image a triage classifier would have read
    # is; a sheet it calls no floor plan, with a non-plan kind, at confidence >= the cut is set
    # aside, a doubtful one is read and its answers say so. Replies cached in the folder by file
    # content. Off until its gate passes
    sheet_kind: SheetKindName = "off"
    sheet_kind_cache_dir: Path = Path("../data/cache/sheet-kind")
    # 0.9: the lowest cut that set aside none of checked-200's 75 plans (0.8 set aside 1; gate
    # run, .agents/exp/vlm-kind.md section 3)
    sheet_kind_cut: float = Field(default=0.9, ge=0, le=1)
    # false: warn only (Bogdan, 2026-11-14 18:1x: Carbon names sheet kinds as a warning; its
    # set-aside gate failed, 7 of 227 plans): a sheet it would set aside is read and flagged with
    # the kind it looks like, so its answers are never certified and are Low (orchestrator)
    sheet_kind_set_aside: bool = True
    # The evidence index's embedder (decision 0012, app/adapters/evidence/embedder.py): the model
    # folder's manifest. No file there (or ""): the index searches with BM25 alone
    evidence_embedder_manifest: Path = Path("../data/models/rag/manifest.json")
    evidence_scope: EvidenceScopeName = "set_aside"
