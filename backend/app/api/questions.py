"""The questions asked in a project: one JSON line per ask in `<projects_dir>/api/questions/
<project id>.jsonl`, written by POST /api/ask when it names a project and by POST /api/projects/
{id}/ask (one line per drawing), read back newest first (docs/API.md "Projects and ingest")."""

import json
import threading
from pathlib import Path

from pydantic import Field

from app.api.views import View
from app.core.answering.model import Unit
from app.core.review.model import RefusalCode

_lock = threading.Lock()
LISTED = 200  # the most recent questions a listing returns


class AskedQuestion(View):
    question: str
    answer: int | float | str | None  # the value shown; None on a refusal
    unit: Unit | None
    drawing_id: str
    at: str  # ISO 8601, UTC
    refused: bool
    # The id of the question asked on the whole project (POST /api/projects/{id}/ask), the same on
    # each of its lines; absent on a POST /api/ask line
    project_ask: str | None = Field(default=None, exclude_if=lambda value: value is None)
    # Why it got no number (Refusal.code); absent when answered, and on lines written before
    # the field existed (2026-11-14), which didn't keep it
    refusal: RefusalCode | None = Field(default=None, exclude_if=lambda value: value is None)


class ProjectQuestions(View):
    project_id: str
    questions: list[AskedQuestion]  # newest first, the last LISTED


def _file(root: Path, project_id: str) -> Path:
    return root / "api" / "questions" / f"{project_id}.jsonl"


def record(root: Path, project_id: str, asked: AskedQuestion) -> None:
    path = _file(root, project_id)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as lines:
            lines.write(asked.model_dump_json() + "\n")


def listed(root: Path, project_id: str) -> list[AskedQuestion]:
    return asked(root, project_id)[::-1][:LISTED]


def log_size(root: Path, project_id: str) -> int:
    """The project's question log in bytes (0 before the first ask): it is only appended to, so
    a new ask always changes it."""
    path = _file(root, project_id)
    with _lock:
        return path.stat().st_size if path.is_file() else 0


def asked(root: Path, project_id: str) -> list[AskedQuestion]:
    """Every question kept for the project, oldest first."""
    path = _file(root, project_id)
    with _lock:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return [AskedQuestion(**json.loads(line)) for line in text.splitlines() if line]
