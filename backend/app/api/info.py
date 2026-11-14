"""GET /api/info: which reader each port uses and the upload limits, so the screen can say what it
runs on and refuse a file before sending it, and the building-code rule packs the country picker
offers. Names only: no keys, endpoints or local paths."""

from typing import Literal

from fastapi import APIRouter
from pydantic import Field

from app.adapters.archive.unpack import MAX_ENTRIES, MAX_FILE, MAX_TOTAL
from app.api.ask import QUESTION_CHARS
from app.api.checks import RulePacksDep, RulePackView, pack_views
from app.api.deps import SettingsDep
from app.api.projects import MAX_UPLOAD
from app.api.views import View
from app.composition import readers, spend_guard, uses_keys
from app.settings import Settings

router = APIRouter(prefix="/api")

MB = 2**20


class Limits(View):
    upload_mb: int
    file_mb: int
    unpacked_mb: int
    files: int
    question_chars: int


class Info(View):
    no_keys: bool  # no reader needs an API key or a model server
    readers: dict[str, str]
    limits: Limits
    # The building-code packs GET /api/drawings/{id}/checks?pack= takes (decision 0009)
    rule_packs: list[RulePackView] = Field(default_factory=list[RulePackView])
    # GEMINI_BUDGET_USD / GEMINI_BUDGET_USD_PER_HOUR: budget_exhausted while Gemini calls are
    # refused; left out when no budget is set
    gemini: Literal["ok", "budget_exhausted"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


@router.get("/info")
def info(settings: SettingsDep, packs: RulePacksDep = ()) -> Info:
    return Info(
        no_keys=not uses_keys(settings),
        readers=readers(settings),
        limits=Limits(
            upload_mb=MAX_UPLOAD // MB,
            file_mb=MAX_FILE // MB,
            unpacked_mb=MAX_TOTAL // MB,
            files=MAX_ENTRIES,
            question_chars=QUESTION_CHARS,
        ),
        rule_packs=pack_views(packs),
        gemini=_gemini(settings),
    )


def _gemini(settings: Settings) -> Literal["ok", "budget_exhausted"] | None:
    guard = spend_guard(settings)
    if not guard.limited:
        return None
    return "budget_exhausted" if guard.exhausted() else "ok"
