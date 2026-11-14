"""The questions asked in a project: one JSON line per ask in `<projects_dir>/api/questions/
<project id>.jsonl`, written by POST /api/ask when it names a project, read back newest first
(docs/API.md "Projects and ingest")."""

import json
import threading
from pathlib import Path

from app.api.views import View
from app.core.answering.model import Unit

_lock = threading.Lock()
LISTED = 200  # the most recent questions a listing returns


class AskedQuestion(View):
    question: str
    answer: int | float | str | None  # the value shown; None on a refusal
    unit: Unit | None
    drawing_id: str | None  # None: asked on the whole project (POST /api/projects/{id}/ask)
    at: str  # ISO 8601, UTC
    refused: bool


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
    path = _file(root, project_id)
    with _lock:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
    found = [AskedQuestion(**json.loads(line)) for line in text.splitlines() if line]
    return found[::-1][:LISTED]
