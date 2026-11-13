"""Settings: the only module that reads env vars or `.env` (docs/ENGINEERING.md section 1).

`.env` is read from the current directory, so run from backend/. Every field is listed in
backend/.env.example, and tests/test_settings.py checks that the two match. Unknown keys in `.env`
are refused, so a typo fails at startup.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
