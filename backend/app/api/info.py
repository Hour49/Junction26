"""GET /api/info: which reader each port uses and the upload limits, so the screen can say what it
runs on and refuse a file before sending it, the building-code rule packs the country picker
offers, and the commit the backend was started from. Names only: no keys, endpoints or local
paths."""

from typing import Literal

from fastapi import APIRouter
from pydantic import Field

from app.adapters.archive.unpack import MAX_ENTRIES, MAX_FILE, MAX_TOTAL
from app.api.ask import QUESTION_CHARS
from app.api.checks import RulePacksDep, RulePackView, pack_views
from app.api.deps import SettingsDep
from app.api.projects import MAX_UPLOAD
from app.api.views import View
from app.composition import chat_model, readers, spend_guard, uses_keys
from app.settings import Settings

router = APIRouter(prefix="/api")

MB = 2**20


class Limits(View):
    upload_mb: int
    file_mb: int
    unpacked_mb: int
    files: int
    question_chars: int


class ChatInfo(View):
    """The project chat agent (decision 0013): CHAT_MODEL, and whether a turn can run now."""

    model: Literal["gemini", "rules", "off"]
    available: bool
    reason: str | None  # why not available; None when it is
    # POST /api/projects/{id}/chat/stream exists: the client streams a turn's steps only when true
    stream: bool = True


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
    # APP_COMMIT: the git commit the backend was started from (tools/qa-env.sh sets it); null
    # when the env doesn't say
    commit: str | None = None
    chat: ChatInfo | None = None


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
        commit=settings.app_commit or None,
        chat=_chat(settings),
    )


def _gemini(settings: Settings) -> Literal["ok", "budget_exhausted"] | None:
    guard = spend_guard(settings)
    if not guard.limited:
        return None
    return "budget_exhausted" if guard.exhausted() else "ok"


def _chat(settings: Settings) -> ChatInfo:
    paid = settings.chat_model != "rules"  # the rules planner is free: no budget stops it
    reason = chat_model(settings)[1] or (spend_guard(settings).exhausted() if paid else None)
    return ChatInfo(model=settings.chat_model, available=reason is None, reason=reason)
