"""`review_answer` ("are you sure?", phase 2 item 3): the chat's latest ask_drawings answer as
the pipeline judged it, whole: per drawing its value, confidence level and why, the check's
reason, and the marks the readers dispute with their ev ids. Earlier turns' tool results reach
the model cut short, so the agent could not answer a doubt from them."""

import re
from collections.abc import Mapping
from typing import Any

REVIEW_ANSWER = "review_answer"
DISPUTED = 8  # disputed marks listed per drawing; disputed_count says how many there are
NOTHING = "there is no answer in this chat to review yet: ask a question about the drawings first"
MARKS = 12  # the answer's own places listed per drawing (to cite); marks_count says how many
# A doubt about the last answer: "are you sure", "really?", "I count 30. Could it be 30?". The
# loop reviews the answer before the model's first step (one model call, not two: chat-eval
# #339), and the rules planner answers from that review
DOUBT = re.compile(
    r"\b(are you (sure|certain)|you sure|double[- ]?check|how (sure|certain|confident))\b|really\?"
    # a pushed number, and only that (review-339b M2: "Could it be 2 storeys high?" is a question)
    r"|\bcould it (be|have) (about |around )?\d+\s*[^\W\d]{0,12}\s*\?*\s*$"
    r"|^\s*i count \d+\s*[^\W\d]{0,12}\s*[.!]?\s*$"
    r"|\bis (that|it) (right|correct)\s*\?*\s*$"
)
# the number a doubt offers: "I count 30. Could it be 30?" -> 30
PUSHED = re.compile(r"\b(?:could it (?:be|have)|i count)\s+(?:about |around )?(\d+(?:[.,]\d+)?)")
REVIEWED = "review_answer result (the server ran it for this doubt): "

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
        quantity: dict[str, Any] = answer.get("quantity") or {}
        marks = _evs(answer.get("marks") or quantity.get("marks"))
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
            "marks": marks[:MARKS],
            "marks_count": len(marks),
            # what the drawings support: the count give or take its disputed marks (a count only)
            "range": _range(answer.get("answer"), answer.get("unit"), len(disputed)),
            "check": check.get("reason"),
            "disputed": [{k: v for k, v in d.items() if v is not None} for d in shown],
            "disputed_count": len(disputed),
            # Tudor's smoke: two flats' review read as "the plans disagree" (it was inside one)
            "where": _where(name, len(disputed)),
        }
        drawings.append({k: v for k, v in drawing.items() if v is not None})
    return {"status": "ok", "question": found.get("question"), "drawings": drawings}


def _evs(items: Any) -> list[str]:
    """The ev ids of a minted list of places."""
    out: list[str] = []
    for item in items if isinstance(items, list) else []:  # pyright: ignore[reportUnknownVariableType]
        ev: Any = item.get("ev") if isinstance(item, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(ev, str):
            out.append(ev)
    return out


def _where(name: Any, disputed: int) -> str | None:
    if not disputed:
        return None
    return (
        f"inside {name}: its own readers disagree on {disputed} of its marks; other drawings "
        "are separate plans, not part of this disagreement"
    )


def _range(value: Any, unit: Any, disputed: int) -> list[int] | None:
    if unit not in (None, "count") or not isinstance(value, int) or isinstance(value, bool):
        return None
    return [max(0, value - disputed), value + disputed]


def pushed(message: str) -> float | None:
    """The number a doubt offers ("could it be 30?"), None when it offers none."""
    found = PUSHED.findall(message.lower())
    return float(found[-1].replace(",", ".")) if found else None


def outside(number: float, drawings: list[dict[str, Any]]) -> list[list[int]] | None:
    """The ranges of the reviewed drawings when `number` lies outside every one; None when it
    lies inside one or no drawing has a range."""
    ranges: list[list[int]] = [d["range"] for d in drawings if d.get("range")]
    if not ranges or any(low <= number <= high for low, high in ranges):
        return None
    return ranges
