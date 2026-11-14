"""Settings: the only module that reads env vars or `.env` (docs/ENGINEERING.md section 1).

`.env` is read from the current directory, so run from backend/. Every field is listed in
backend/.env.example, and tests/test_settings.py checks that the two match. Unknown keys in `.env`
are refused, so a typo fails at startup.

The adapter of each pipeline port is chosen here by name and built in app/composition.py. A new
adapter adds its name to the Literal of its port and a case in composition.py.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
QuestionParserName = Literal["hello", "templates"]  # templates: words to a takeoff query
AnswerPriorName = Literal["none", "dev"]  # dev: a refusal keeps the dev answers' best estimate
# pdf: the vector route also reads the ruled schedules printed on a drawn PDF sheet
TablesName = Literal["off", "pdf"]
# gemini: Google's API. eu: our open model on Verda (app/adapters/openvlm/)
ProviderName = Literal["gemini", "eu"]
# off, or priors: a raster sheet without a scale gets an estimated one (app/adapters/raster_scale/)
RasterScaleName = Literal["off", "priors"]
# furniture: a room keeps the type its reader gave. gold-labels: the printed label overrules it
# on four points, as the dataset's answers do (app/core/pipeline/room_policy.py)
RoomPolicyName = Literal["furniture", "gold-labels"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
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
    # How the raster route types the rooms its rooms source read, whichever source that is.
    # gold-labels is for a source that reads printed labels: it turns every unlabelled bedroom
    # into `other`
    room_policy: RoomPolicyName = "furniture"
    # The Gemini room reader of the raster route (app/adapters/raster_ocr/gemini.py), built only
    # when RASTER_COMPONENTS names it: its key (never logged), model, time limit per page, and
    # the folder its replies are cached in (gitignored)
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.5-flash"
    gemini_timeout_s: float = 60.0
    gemini_cache_dir: Path = Path("../data/cache/gemini-rooms")
    # Gemini Decisions count distributions (app/adapters/decisions/, same GEMINI_API_KEY). The
    # count swap is on when RASTER_COMPONENTS names decisions:<source>; the answer confidence when
    # DECISIONS_CONFIDENCE is true. Seconds per request, and the folder replies are cached in
    decisions_confidence: bool = False
    decisions_timeout_s: float = 30.0
    decisions_cache_dir: Path = Path("../data/cache/decisions")
    # The sheet-kind signal at ingest (app/adapters/decisions_kind/, same key, timeout and cache
    # folder): Gemini's photo-of-a-plan flag and P(floor plan) for each uploaded image or PDF
    decisions_kind: bool = False
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
