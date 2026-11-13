"""Settings: the only module that reads env vars or `.env` (docs/ENGINEERING.md section 1).

`.env` is read from the current directory, so run from backend/. Every field is listed in
backend/.env.example, and tests/test_settings.py checks that the two match. Unknown keys in `.env`
are refused, so a typo fails at startup.

The adapter of each pipeline port is chosen here by name and built in app/composition.py. A new
adapter adds its name to the Literal of its port and a case in composition.py.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# pdf: the vector route's reader of drawn PDFs. ifc: the model route's reader of a plan sheet
# with its IFC building model, which also makes ingest look for that model next to the sheet
ExtractorName = Literal["hello", "pdf", "ifc"]
# pdf: a drawn PDF sheet's own second readings. ifc: those, and what a sheet's model lists
SecondCounterName = Literal["hello", "pdf", "ifc"]
QuestionParserName = Literal["hello", "templates"]  # templates: words to a takeoff query
AnswerPriorName = Literal["none", "dev"]  # dev: a refusal keeps the dev answers' best estimate


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    extractor_bim: ExtractorName = "ifc"
    extractor_cad: ExtractorName = "hello"
    extractor_vector: ExtractorName = "pdf"
    extractor_raster: ExtractorName = "hello"
    second_counter: SecondCounterName = "ifc"
    question_parser: QuestionParserName = "templates"
    answer_prior: AnswerPriorName = "none"
