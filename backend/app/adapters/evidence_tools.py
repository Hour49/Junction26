"""The evidence index as tools for the chat agent (contract v1, .agents/exp/rag-evidence.md
section 1; format of board #220: OpenAI function calling). `EVIDENCE_TOOLS` is the specs list the
agent loop joins with the other tools; `run_evidence_tool` answers one call as JSON text and never
raises, so a bad call comes back as {"error": "..."} the model can act on. `index` is one
project's evidence (composition's `evidence_index(project_id)`): the model never names a project."""

import json
import logging
from typing import Any, cast

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
                            "What to look for, as a question or keywords, in any language (the "
                            "files are described in English; printed text is in the file's own "
                            "language)."
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


def _json(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def _error(message: str) -> str:
    return _json({"error": message})


def run_evidence_tool(index: ProjectEvidence, name: str, arguments_json: str) -> str:
    """One tool call's answer as JSON text. Never raises."""
    try:
        try:
            arguments = json.loads(arguments_json or "{}")
        except (TypeError, ValueError):
            return _error("The arguments are not valid JSON: send a JSON object.")
        if not isinstance(arguments, dict):
            return _error("The arguments must be a JSON object.")
        found = cast(dict[str, Any], arguments)
        if name == "search_evidence":
            return _search(index, found)
        if name == "get_evidence":
            return _get(index, found)
        known = ", ".join(tool["function"]["name"] for tool in EVIDENCE_TOOLS)
        return _error(f"There is no tool {name!r}: use one of {known}.")
    except Exception:  # the agent must get an answer, whatever went wrong
        logger.exception("evidence tool %s failed", name)
        return _error("internal error")


def _search(index: ProjectEvidence, arguments: dict[str, Any]) -> str:
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        return _error("search_evidence needs a non-empty 'query' string.")
    k = arguments.get("k", K_DEFAULT)
    if not isinstance(k, int) or isinstance(k, bool):
        k = K_DEFAULT
    unrelated = arguments.get("include_unrelated", False) is True
    found = index.search(query.strip(), min(K_MAX, max(K_MIN, k)), unrelated)
    return _json(found.model_dump(mode="json"))


def _get(index: ProjectEvidence, arguments: dict[str, Any]) -> str:
    asked = arguments.get("id")
    if not isinstance(asked, str) or not asked.strip():
        return _error("get_evidence needs an 'id' string from a search_evidence hit.")
    found = index.get(asked)
    if found is None:
        return _error(f"No evidence {asked!r} in this project: use an id from search_evidence.")
    return _json(found.model_dump(mode="json"))


def evidence_prompt(index: ProjectEvidence) -> str:
    """A paragraph for the agent's system prompt: what the project's evidence index holds."""
    return index.prompt()
