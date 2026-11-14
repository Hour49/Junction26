"""`review_answer` ("are you sure?", phase 2 item 3): the chat's latest ask_drawings answer as
the pipeline judged it, whole: per drawing its value, confidence level and why, the check's
reason, and the marks the readers dispute with their ev ids. Earlier turns' tool results reach
the model cut short, so the agent could not answer a doubt from them."""

from collections.abc import Mapping
from typing import Any

REVIEW_ANSWER = "review_answer"
DISPUTED = 8  # disputed marks listed per drawing; disputed_count says how many there are
NOTHING = "there is no answer in this chat to review yet: ask a question about the drawings first"

REVIEW_ANSWER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": REVIEW_ANSWER,
        "description": (
            "The chat's latest ask_drawings answer as the drawings' readers judged it: per "
            "drawing its value, confidence level and why, the check's reason and the marks the "
            "readers dispute (ev ids you can cite or show with show_on_plan). Call it when the "
            "user doubts an answer (are you sure, really, double-check, why) instead of asking "
            "again."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def review_of(found: Mapping[str, Any], names: Mapping[str, str]) -> dict[str, Any]:
    """The review of one ask_drawings result as minted (its places carry ev ids)."""
    drawings: list[dict[str, Any]] = []
    parts: list[Any] = found.get("parts") or []
    for part in parts:
        if not isinstance(part, dict):
            continue
        given: dict[str, Any] = part  # pyright: ignore[reportUnknownVariableType]
        name = names.get(str(given.get("drawing_id"))) or given.get("name")
        answer: dict[str, Any] = given.get("answer") or {}
        refusal: Any = answer.get("refusal")
        if refusal or answer.get("answer") is None:
            text: Any = refusal.get("text") if isinstance(refusal, dict) else refusal  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            drawings.append({"drawing": name, "refused": text or "no answer"})
            continue
        level: dict[str, Any] = answer.get("level") or {}
        check: dict[str, Any] = answer.get("check") or {}
        listed: list[Any] = check.get("disputed") or []
        disputed: list[dict[str, Any]] = [d for d in listed if isinstance(d, dict)]
        shown = [{"ev": d.get("ev"), "why": d.get("why")} for d in disputed[:DISPUTED]]
        drawing = {
            "drawing": name,
            "answer": answer["answer"],
            "unit": answer.get("unit"),
            "level": level.get("level"),
            "level_text": level.get("text"),
            "explanation": answer.get("explanation"),
            "check": check.get("reason"),
            "disputed": [{k: v for k, v in d.items() if v is not None} for d in shown],
            "disputed_count": len(disputed),
        }
        drawings.append({k: v for k, v in drawing.items() if v is not None})
    return {"status": "ok", "question": found.get("question"), "drawings": drawings}
