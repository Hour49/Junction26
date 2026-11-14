"""The building-law tools a model calls (decision 0011), in the OpenAI function-calling shape that
app/adapters/openvlm/client.py sends (`body["tools"] = TOOLS`), and the short table of contents a
system prompt carries instead of the laws themselves.

`run_tool` never raises on what the model sent: a bad call is `{"error": ...}`, so it can retry.
"""

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import NotFoundError
from app.core.laws.model import PACKS, TOPICS, Topic
from app.core.laws.search import LawIndex

PROMPT_CHARS = 6000  # ~1.5k tokens at ~4 characters a token
TITLE_CHARS = 90

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_law",
            "description": (
                "Search the building law of one country pack (fi: Finland; ch-zh: Swiss "
                "federal law and the Canton of Zürich) for the clauses that answer a question. "
                "Search before you state any legal rule or limit; never cite a rule from memory. "
                "Returns the best clauses with their id, ref, law title, one-sentence summary and "
                "url. Read a clause with get_clause before quoting it, and cite its ref and url."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pack": {"type": "string", "enum": list(PACKS)},
                    "query": {
                        "type": "string",
                        "description": (
                            "Words to search for, in English or the law's language, e.g. "
                            "'minimum bedroom area' or 'Fluchtweg Breite'."
                        ),
                    },
                    "topic": {
                        "type": "string",
                        "enum": list(TOPICS),
                        "description": "Only clauses of this topic (optional).",
                    },
                },
                "required": ["pack", "query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_clause",
            "description": (
                "Read one clause found by search_law: its verbatim text in the original language, "
                "our unofficial English translation, its limits, and its law's number, title and "
                "url. Quote `text`, say a translation is unofficial, and cite `ref` and `url`."
            ),
            "parameters": {
                "type": "object",
                "properties": {"clause_id": {"type": "string"}},
                "required": ["clause_id"],
                "additionalProperties": False,
            },
        },
    },
]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Search(_Args):
    pack: str
    query: str = Field(min_length=1, max_length=500)
    topic: Topic | None = None


class _Clause(_Args):
    clause_id: str


def run_tool(index: LawIndex, name: str, arguments: str | dict[str, Any]) -> str:
    """One tool call's result as JSON text; `arguments` as the model sent them (JSON text)."""
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
        if name == "search_law":
            search = _Search.model_validate(args)
            hits = index.search(search.pack, search.query, search.topic)
            result: Any = {"hits": [hit.model_dump() for hit in hits]}
        elif name == "get_clause":
            result = index.clause(_Clause.model_validate(args).clause_id).model_dump()
        else:
            result = {"error": f"no tool {name!r}; the tools are search_law and get_clause"}
    except (json.JSONDecodeError, ValidationError, NotFoundError) as error:
        result = {"error": str(error)}
    return json.dumps(result, ensure_ascii=False)


def law_prompt(index: LawIndex, pack: str) -> str:
    """What a system prompt says about the law: how to reach it, and one line per law of the pack,
    within PROMPT_CHARS (past it the last laws are left out, with a line saying how many)."""
    head = (
        f"Building law of pack {pack} is available through tools, not in this prompt. Call "
        f"search_law(pack='{pack}', query=...) before stating any rule, get_clause(clause_id) "
        "before quoting one, and cite the clause's ref and url. Translations are ours, "
        "unofficial. The laws:"
    )
    lines = [head]
    entries = index.toc(pack)
    for at, entry in enumerate(entries):
        title = entry.title_en
        if len(title) > TITLE_CHARS:
            title = title[: TITLE_CHARS - 1].rstrip() + "…"
        line = f"- {entry.law_id} ({entry.number}): {title} [{', '.join(entry.topics)}]"
        rest = len(entries) - at
        if sum(len(kept) + 1 for kept in lines) + len(line) + 60 > PROMPT_CHARS:
            lines.append(f"- … {rest} more laws: find them with search_law.")
            break
        lines.append(line)
    if not entries:
        lines.append("- none yet.")
    return "\n".join(lines)
