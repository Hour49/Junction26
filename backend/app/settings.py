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
# on: a sheet whose detector found no door takes the door estimate from Carbon's door boxes
ScaleCarbonDoorsName = Literal["off", "on"]
# off, or carbon: a raster sheet's printed scale and counts, read by the Carbon reader, replace
# its estimated scale and check its counts (app/adapters/printed_scale/)
RasterPrintedScaleName = Literal["off", "carbon"]
RasterTilesName = Literal["off", "auto"]  # auto: big sheets read tile by tile by the detector
# raster: a drawn PDF the vector reader has no sheet style for goes to the raster route
VectorFallbackName = Literal["off", "raster"]
# furniture: a room keeps the type its reader gave. gold-labels: the printed label overrules it
# on four points, as the dataset's answers do (app/core/pipeline/room_policy.py)
RoomPolicyName = Literal["furniture", "gold-labels"]
# The project chat's model (decision 0013). gemini: Gemini's OpenAI-compatible endpoint
# (AGENT_*, GEMINI_API_KEY). rules: a deterministic planner, no key. off: no agent chat
ChatModelName = Literal["gemini", "rules", "off"]
# The Carbon reader of raster drawings (app/adapters/carbon/). off; all: every raster drawing;
# advanced: the drawings the sheet-kind step (SHEET_KIND=carbon) called advanced
# large: on raster images over 4,000 px on their long side (from the file's header), and on smaller
# raster pages where the shipped reader found fewer than 3 elements, Carbon counts the things drawn
# and the shipped reader the rooms
CarbonReaderName = Literal["off", "advanced", "all", "large"]
# The Carbon check of the levels (CARBON_LEVELS): off; demote: Carbon reads every raster drawing
# beside its reader, and a Medium answer it counts differently becomes Low; ladder: the same, and a
# Medium answer it counts the same becomes High (two readers agree; still not certified)
CarbonLevelsName = Literal["off", "demote", "ladder"]
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
    # on: a raster sheet RASTER_SCALE=priors left without a scale because the detector found no
    # door takes the estimate from the Carbon reader's door boxes (CARBON_READER=large reads them),
    # its source saying so; its door width is not fitted on Carbon's boxes yet
    # (app/adapters/raster_scale/carbon_doors.py)
    scale_carbon_doors: ScaleCarbonDoorsName = "off"
    # carbon: the printed scale (a bar, or a ratio at a resolution the file states) replaces the
    # estimate, kept as a conflict value, and printed counts are checked against the read ones.
    # Off by default; carbon asks gemini-4-carbon (GEMINI_API_KEY, the spend guard, cached in
    # CARBON_CACHE_DIR: the page reply is the Carbon reader's): about 0.015 USD a sheet
    raster_printed_scale: RasterPrintedScaleName = "off"
    # auto: a raster page whose long side is over 4000 px is read by every detector source of
    # RASTER_COMPONENTS and DOUBLE_CHECK_READERS on overlapping 2048 px tiles, merged across the
    # seams (app/adapters/raster_detector/tiles.py); its plans still come from the whole page.
    # Photo arms are not tiled. off: every page is letterboxed whole (a door on a 14k px sheet
    # is then a few px)
    raster_tiles: RasterTilesName = "off"
    # raster: a drawn PDF whose page 1 matches no sheet style the vector reader has reading rules
    # for (a Revit or AutoCAD plot: app/adapters/vector_pdf/unruled.py) is read on the raster
    # route, as the image of its page like a scan (app/adapters/scan_images.py). Ingest flags it,
    # so none of its answers is certified. off: it stays on the vector route and reads nothing
    vector_fallback: VectorFallbackName = "off"
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
    # CARBON_LEVELS=demote (brief r8 BG; integ's pre-registered rule, .agents/exp/integ.md): the
    # Carbon reader (same key, timeout, cache and spend guard) reads every raster drawing beside
    # its reader, never counted; CHECK_POLICY's Medium answer whose question Carbon answers with
    # another value becomes Low. Needs EXTRACTOR_RASTER=composite. ladder (brief r8 BQ, Bogdan
    # 19:4x "make them high"): the same read, and a Medium answer it answers alike becomes High
    carbon_levels: CarbonLevelsName = "off"
    carbon_timeout_s: float = 120.0
    carbon_cache_dir: Path = Path("../data/cache/carbon-reader")
    # EU open models (app/adapters/openvlm/): our vLLM server on Verda (Finland), reached by an SSH
    # tunnel. Each Gemini step picks its provider; "eu" sends it to this server instead (no
    # fallback to Gemini on an error). URL, key (never logged), model, seconds per request
    eu_vlm_base_url: str = "http://127.0.0.1:18431/v1"
    eu_vlm_api_key: SecretStr = SecretStr("")
    eu_vlm_model: str = "Qwen/Qwen3.8-27B-FP8"
    eu_vlm_timeout_s: float = 300.0
    # Room outlines for raster plans: a rooms reader's boxes become the free space inside the drawn
    # walls (app/adapters/raster_ocr/room_outlines.py). Off: rooms keep their box.
    room_outlines: bool = True
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
    # An IFC model's fact sheet (app/adapters/ifc_model/facts_source.py) answers what the takeoff
    # does not (app/core/answering/facts.py): off until measured. IFC_FACTS_CACHE: a folder that
    # keeps each sheet as JSON across runs; "" keeps them in memory only
    ifc_facts: bool = False
    ifc_facts_cache: str = ""
    # A scanned services or structural plan (triage's Sheet.discipline) read into a fact sheet at
    # ingest by local readers, no model call (app/adapters/discipline_pictures/lane.py; spec
    # discipline-pictures.md): "template" = OCR legend + template symbols + mask runs. Off: ingest
    # is unchanged. The sheets are kept in the cache folder by the page file's content
    discipline_pictures: Literal["off", "template"] = "off"
    discipline_pictures_cache_dir: Path = Path("../data/cache/discipline-pictures")
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
    # Stored services models (decision 0017), <sha256>.services.v1.b<builder>.json.gz (a newer
    # builder rebuilds them); `python -m app.cli services build` writes them, GET
    # .../services/{storey}.png draws them (gitignored)
    services_cache_dir: Path = Path("../data/cache/services")
    # The 3D view of IFC files (GET .../files/{file_id}/model.glb, FileStatus.model_3d): off, the
    # route is 404 and no payload changes. Each conversion runs alone in a subprocess under this
    # memory budget and time limit; over either, the model is too_big
    model_3d: bool = False
    # 1500 MB: the largest publishable model (DigitalHub plumbing) peaks at 1.27 GB, inside the
    # live app's 4 GB; the time limit is CPU seconds (56 s for that one), so a busy machine does
    # not make a model too_big
    model_3d_memory_mb: int = Field(default=1500, ge=1)
    model_3d_timeout_s: float = Field(default=120, gt=0)
    # The synthetic demo archive (backend/scripts/make_sample_archive.py writes it); for /sample
    sample_archive: Path = Path("../data/samples/sample-project.zip")
    # Where a drawing's licence credit is looked up by content (app/adapters/credits.py): the
    # Stoa dataset (its data/<source>/LICENSE.md) and the Commons demo photos (manifest.jsonl)
    credit_dataset: Path = Path("../data/stoa/full/junction-dataset")
    credit_photos: Path = Path("../data/stoa/exp/photo/real/commons")
    # none: images are read as uploaded (EXIF turned upright); a rectifier undoes a photo's
    # perspective first (app/core/ingest/ports.py Rectifier)
    rectifier: RectifierName = "none"
    # Drawing groups read at once at ingest (app/core/ingest/groups.py): a cold upload mostly
    # waits on Carbon and Gemini, so reading groups side by side is what makes it fast (fail-5's
    # 6 cold images: 253 s -> 79 s at 4). Groups that share a source (a building's sheets and its
    # model) are read one after another. 1 (one by one, as before) until the host's memory is
    # checked: at 4 that upload swapped 10.3 GB past a 10 GB cap, against 5.0 GB at 1
    ingest_groups_in_flight: int = Field(default=1, ge=1)
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
    # The project chat agent (decision 0013, app/core/agent/): its model, and for gemini the
    # model id, endpoint and USD per million tokens in and out (no published price yet: a high
    # placeholder, so the spend guard stops early); the most one turn may spend and its steps.
    # Every call is charged to the Gemini spend guard
    chat_model: ChatModelName = "rules"
    agent_model: str = "gemini-4-hydrogen"
    agent_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    agent_price_in_per_m: float = Field(default=1.50, ge=0)
    agent_price_out_per_m: float = Field(default=9.00, ge=0)
    # Prompt tokens Gemini read from its cache (usage.prompt_tokens_details.cached_tokens), USD
    # per million. Google lists the cache read at 0.075/M; 0.375 is a deliberate overestimate,
    # so the spend guard stops early rather than late
    agent_price_cached_per_m: float = Field(default=0.375, ge=0)
    agent_turn_usd: float = Field(default=0.10, gt=0)
    agent_max_steps: int = Field(default=8, ge=1, le=20)
    # How much the model thinks per step, sent as reasoning_effort; "default" sends none (the
    # model's own). The pi spike got the same 10 answers at about 1/4 of the cost with thinking
    # off; chat-eval confirms on its set before the demo changes it (.agents/exp/pi-spike.md).
    # No "minimal": the chat model answers it with a 400
    agent_thinking: Literal["default", "none", "low", "medium", "high"] = "low"
    # on: every plan edit the chat proposes is followed through the project's service models
    # (plumbing, ventilation, heating, electrical IFC files), decision 0016, and a project with
    # an IFC file is offered the services tools (decision 0017). Reading a model takes about
    # 0.2 GB of memory that is not given back
    services_follow: Literal["off", "on"] = "off"
    # The VLM sheet-kind step (.agents/exp/vlm-kind.md, app/adapters/triage/sheet_kind.py): carbon
    # asks gemini-4-carbon (GEMINI_API_KEY) what each image a triage classifier would have read
    # is; a sheet it calls no floor plan, with a non-plan kind, at confidence >= the cut is set
    # aside. A doubtful one is read; with a non-plan kind (in either SHEET_KIND_SET_ASIDE mode) it
    # is flagged, so its answers are never certified and are Low, until a person has it read as a
    # floor plan. Replies cached in the folder by file content. Off until its gate passes
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
