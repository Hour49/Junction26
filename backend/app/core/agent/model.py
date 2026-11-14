"""The agent chat's data: a turn as the API returns it, the chat as it is stored (decision 0013)."""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import Field

from app.core.model import Frozen
from app.core.plan_edit.model import Proposal

TurnKind = Literal["answer", "dont_know", "conflict", "needs_input", "edit"]
Json = dict[str, Any]


class Level(Frozen):
    """An answer's confidence level as ask_drawings gives it (ADR 0011 'confidence levels')."""

    level: Literal["high", "medium", "low"]
    basis: str | None = None
    text: str | None = None


class ChatEvidence(Frozen):
    n: int  # its number in the turn's text, [n]
    id: str  # ev_<k>, minted by the server from a tool result
    drawing_id: str
    name: str | None  # the drawing's file name in the project
    page: int
    box: tuple[float, float, float, float]  # page fractions
    label: str | None
    sure: bool | None
    level: Level | None = None  # set when it comes from an ask_drawings answer part


class Step(Frozen):
    n: int
    tool: str
    label: str  # plain words, written by the server from the tool and its arguments
    status: Literal["ok", "error"]
    ms: float


class Option(Frozen):
    label: str = Field(min_length=1, max_length=60)
    message: str = Field(min_length=1, max_length=300)


class ChatTurn(Frozen):
    chat_id: str
    turn: int
    kind: TurnKind
    text: str
    evidence: tuple[ChatEvidence, ...] = ()
    edit: Proposal | None = None
    options: tuple[Option, ...] | None = None
    steps: tuple[Step, ...] = ()
    model: str
    cost_usd: float
    latency_s: float
    # The ask_drawings results (ProjectAnswer, as POST /api/projects/{id}/ask) the answer rests on
    answers: tuple[Json, ...] = ()


@dataclass(frozen=True)
class Caps:
    max_steps: int = 8
    calls_per_step: int = 4
    turn_usd: float = 0.10
    seconds: float = 60.0


@dataclass
class Chat:
    """One conversation as the chat store keeps it. `messages`: every message sent to or got from
    the model, assistant messages verbatim (Gemini's thought signatures); `starts[i]`: where turn
    i+1's messages begin; `results`: each tool call's full result (the model may see it cut)."""

    chat_id: str
    messages: list[Json] = field(default_factory=list[Json])
    starts: list[int] = field(default_factory=list[int])
    turns: list[ChatTurn] = field(default_factory=list[ChatTurn])
    proposals: dict[str, Proposal] = field(default_factory=dict[str, Proposal])
    results: list[Json] = field(default_factory=list[Json])
    minted: int = 0  # evidence ids given so far: ev ids run on through the chat
