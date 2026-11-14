"""The evidence index as tools for the chat agent (decision 0012, contract v1.1; format of board
#220: OpenAI function calling, as the law tools). `EVIDENCE_TOOLS` is the specs list the
agent loop joins with the other tools; `run_evidence_tool` answers one call as JSON text and never
raises, so a bad call comes back as {"error": "..."} the model can act on. `index` is one
project's evidence (composition's `evidence_index(project_id)`): the model never names a project."""

import json
import logging
from typing import Annotated, Any, cast

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.adapters.evidence.project import ProjectEvidence

logger = logging.getLogger(__name__)
K_DEFAULT, K_MIN, K_MAX = 5, 1, 20

EVIDENCE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_evidence",
            "description": (
                "Search this project's files that are not floor plans (photos, elevations, "
                "sections, site plans, maps, text pages) by what they show and by the words "
                "printed on them. Returns up to k files, best first, each with its best-matching "
                "passage. Hits are the closest files, not proof that the thing exists: read the "
                "snippet, and call get_evidence before stating a fact from a file. Floor plan "
                "facts (counts, areas, rooms) are not in here."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "What to look for, as keywords or a short question. Write it in "
                            "English (the files are described in English), and keep names, "
                            "drawing numbers and dates exactly as printed, in their own language."
                        ),
                    },
                    "k": {
                        "type": "integer",
                        "description": "How many files to return, 1 to 20. Default 5.",
                    },
                    "include_unrelated": {
                        "type": "boolean",
                        "description": (
                            "Also search files judged unrelated to this project. Default false."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_evidence",
            "description": (
                "The full passage of one search hit and the whole description of its file: what "
                "it shows, every word printed on it, what kind of sheet it is and whether it "
                "belongs to the project."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": (
                            "A hit id from search_evidence (f7-detail-2), or a file id (f7) for "
                            "the file as a whole."
                        ),
                    }
                },
                "required": ["id"],
            },
        },
    },
]


class SearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    k: Annotated[int, Field(ge=K_MIN, le=K_MAX)] = K_DEFAULT
    include_unrelated: bool = False


class GetArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


def _json(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def _error(message: str) -> str:
    return _json({"error": message})


def _invalid(name: str, error: ValidationError) -> str:
    """The first problem with the arguments, as one sentence the model can act on."""
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"]) or "arguments"
    return _error(f"Fix the arguments of {name}: {where}: {first['msg']}.")


def run_evidence_tool(index: ProjectEvidence, name: str, arguments: str | dict[str, Any]) -> str:
    """One tool call's answer as JSON text; `arguments` as JSON text or already parsed. Never
    raises."""
    try:
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except ValueError:
                return _error("The arguments are not valid JSON: send a JSON object.")
        if not isinstance(arguments, dict):
            return _error("The arguments must be a JSON object.")
        found = cast(dict[str, Any], arguments)
        if name == "search_evidence":
            try:
                search = SearchArguments.model_validate(found)
            except ValidationError as error:
                return _invalid(name, error)
            hits = index.search(search.query, search.k, search.include_unrelated)
            return _json(hits.model_dump(mode="json"))
        if name == "get_evidence":
            try:
                asked = GetArguments.model_validate(found).id
            except ValidationError as error:
                return _invalid(name, error)
            detail = index.get(asked)
            if detail is None:
                return _error(
                    f"No evidence {asked!r} in this project: use an id from search_evidence."
                )
            return _json(detail.model_dump(mode="json"))
        known = ", ".join(tool["function"]["name"] for tool in EVIDENCE_TOOLS)
        return _error(f"There is no tool {name!r}: use one of {known}.")
    except Exception:  # the agent must get an answer, whatever went wrong
        logger.exception("evidence tool %s failed", name)
        return _error("internal error")


def evidence_prompt(index: ProjectEvidence) -> str:
    """A paragraph for the agent's system prompt: what the project's evidence index holds (at
    most 6,000 characters, as the law tools' prompt)."""
    return index.prompt()
