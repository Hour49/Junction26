"""What the agent loop needs from outside (decision 0013, spec AC-8). The spend guard is
app/core/spend.py's `SpendGuard`."""

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.plan_edit.model import Selection

Json = dict[str, Any]


class ChatModelError(Exception):
    """The model gave no usable reply; the message is safe to show (no key, no body)."""


@dataclass(frozen=True)
class Reply:
    message: Json  # the assistant message exactly as the provider sent it, kept verbatim
    usd: float  # what the call cost


class ChatModel(Protocol):
    name: str  # what the turn reports as `model`: "gemini", "rules"

    def complete(self, messages: list[Json], tools: list[Json]) -> Reply:
        """One model step in the OpenAI chat-completions shape. Raises ChatModelError."""
        ...


class Toolbox(Protocol):
    """The tools of one project and turn. `run` never raises: a bad call is {"error": ...}."""

    @property
    def tools(self) -> list[Json]: ...

    def run(self, name: str, arguments: str) -> str: ...

    def describe(self, selection: Selection) -> str:
        """The one line the model reads for a selection (AC-12), from geometry."""
        ...
