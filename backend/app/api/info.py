"""GET /api/info: which reader each port uses and the upload limits, so the screen can say what it
runs on and refuse a file before sending it. Names only: no keys, endpoints or local paths."""

from fastapi import APIRouter

from app.adapters.archive.unpack import MAX_ENTRIES, MAX_FILE, MAX_TOTAL
from app.api.ask import QUESTION_CHARS
from app.api.deps import SettingsDep
from app.api.projects import MAX_UPLOAD
from app.api.views import View
from app.composition import readers, uses_keys

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


@router.get("/info")
def info(settings: SettingsDep) -> Info:
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
    )
