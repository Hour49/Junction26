"""The `final_answer` tool and its validator (spec AC-4, AC-14): an answer reaches the user only
when every evidence id, number and proposal in it came from this turn's tool results."""

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import Field

from app.core.agent.model import Option, TurnKind
from app.core.model import Frozen

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Ids and citations hold digits that are not claims: ev_3, [2], sel_1, W4, R3, p1
_IDS = re.compile(r"\[\d+\]|\b[A-Za-z]+_?\d+\b")
FAILED = frozenset({"error", "refused", "cannot_edit", "unknown"})


class FinalAnswer(Frozen):
    kind: TurnKind
    text: str = Field(min_length=1, max_length=1200)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=12)
    options: tuple[Option, ...] | None = Field(default=None, max_length=4)
    proposal_id: str | None = Field(default=None, max_length=16)


def _final_answer_tool() -> dict[str, Any]:
    schema = FinalAnswer.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": "final_answer",
            "description": (
                "End the turn with the answer to the user. kind: answer (backed by tool results), "
                "dont_know (the tools do not say; text says why and what would settle it), "
                "conflict (sources disagree: show both), needs_input (ambiguous: 2-4 options), "
                "edit (a plan tool's proposal, named by proposal_id). options: chips the user may "
                "send next, on any kind (e.g. questions the drawings can answer, on dont_know). "
                "Cite places as [ev_<k>] in text and list them in evidence_ids."
            ),
            "parameters": schema,
        },
    }


FINAL_ANSWER_TOOL = _final_answer_tool()


def failed(result: Any) -> bool:
    """A tool result that is an error or says it could not answer."""
    if not isinstance(result, dict):
        return False
    found: dict[str, Any] = result  # pyright: ignore[reportUnknownVariableType]
    return "error" in found or found.get("status") in FAILED


def problems(
    answer: FinalAnswer,
    minted: set[str],
    proposals: set[str],
    sources: list[str],
    all_failed: bool,
) -> list[str]:
    """What is wrong with `answer`: each a sentence the model reads; [] when it may go out.
    `sources`: this turn's tool results and the user's message, as text."""
    out: list[str] = []
    unknown = [ev for ev in [*answer.evidence_ids, *re.findall(r"ev_\d+", answer.text)]
               if ev not in minted]  # fmt: skip
    if unknown:
        out.append(f"evidence ids no tool returned in this turn: {', '.join(unknown)}")
    known = numbers(sources)
    unbacked = [n for n in NUMBER.findall(_IDS.sub(" ", answer.text)) if not backed(n, known)]
    if unbacked:
        out.append(f"numbers no tool result of this turn gives: {', '.join(unbacked)}")
    if answer.kind == "edit" and answer.proposal_id not in proposals:
        out.append(f"kind edit needs a proposal_id a plan tool returned in this turn, "
                   f"not {answer.proposal_id!r}")  # fmt: skip
    if answer.kind == "needs_input" and not 2 <= len(answer.options or ()) <= 4:
        out.append("kind needs_input needs 2 to 4 options")
    if answer.kind == "answer" and all_failed:
        out.append("kind answer, but every tool result of this turn failed or said unknown")
    return out


def numbers(sources: list[str]) -> set[Decimal]:
    return {
        Decimal(found.replace(",", ".")) for source in sources for found in NUMBER.findall(source)
    }


def backed(number: str, known: set[Decimal]) -> bool:
    """Whether some known number, rounded to `number`'s decimals, equals it."""
    want = Decimal(number.replace(",", "."))
    step = Decimal(1).scaleb(int(want.as_tuple().exponent))
    return want in known or any(found.quantize(step, ROUND_HALF_UP) == want for found in known)
