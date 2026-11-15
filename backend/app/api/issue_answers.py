"""A person's answers to a project's issues: one JSON object per project in `<projects_dir>/api/
issue_answers/<project id>.json`, issue id -> answer, written by POST /api/projects/{id}/issues/
{issue_id}/answer and read with the issues (docs/API.md "Projects and ingest"). Kept apart from
ingest's project, like the question log, so it survives a reload and a restart."""

import json
import os
import threading
from pathlib import Path

from pydantic import Field

from app.api.views import View

_lock = threading.Lock()


class IssueAnswer(View):
    text: str = Field(min_length=1, max_length=500)
    by: str = Field(min_length=1, max_length=100)
    at: str  # ISO 8601, UTC


def _file(root: Path, project_id: str) -> Path:
    return root / "api" / "issue_answers" / f"{project_id}.json"


def answers(root: Path, project_id: str) -> dict[str, IssueAnswer]:
    """Every answer kept for the project, by issue id ({} before the first)."""
    path = _file(root, project_id)
    with _lock:
        text = path.read_text(encoding="utf-8") if path.is_file() else "{}"
    return {issue: IssueAnswer(**found) for issue, found in json.loads(text).items()}


def save(root: Path, project_id: str, issue_id: str, answer: IssueAnswer | None) -> None:
    """Keep `answer` for the issue, replacing any earlier one; None takes it back."""
    path = _file(root, project_id)
    with _lock:
        text = path.read_text(encoding="utf-8") if path.is_file() else "{}"
        kept = json.loads(text)
        if answer is None:
            kept.pop(issue_id, None)
        else:
            kept[issue_id] = answer.model_dump()
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".json.part")
        partial.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
        os.replace(partial, path)  # a reader never sees half a file


def _skips_file(root: Path, project_id: str) -> Path:
    return root / "api" / "issue_skips" / f"{project_id}.json"


def skipped(root: Path, project_id: str) -> frozenset[str]:
    """The issue ids a person skipped in the chat (decision 0018): never asked about again."""
    path = _skips_file(root, project_id)
    with _lock:
        text = path.read_text(encoding="utf-8") if path.is_file() else "[]"
    return frozenset(json.loads(text))


def skip(root: Path, project_id: str, issue_id: str) -> None:
    """Keep `issue_id` as skipped, with the project, across chats and restarts."""
    path = _skips_file(root, project_id)
    with _lock:
        text = path.read_text(encoding="utf-8") if path.is_file() else "[]"
        kept = sorted({*json.loads(text), issue_id})
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".json.part")
        partial.write_text(json.dumps(kept), encoding="utf-8")
        os.replace(partial, path)
