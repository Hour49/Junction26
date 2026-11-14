"""One chat turn (spec AC-1..AC-7): model step → its tool calls → their results → next step, until
a valid `final_answer`, or a cap ends it as `dont_know` with the reason in plain words."""

import json
import re
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from app.core.agent.evidence import mint
from app.core.agent.model import Caps, Chat, ChatEvidence, ChatTurn, Json, Level, Step, TurnKind
from app.core.agent.ports import ChatModel, ChatModelError, Toolbox
from app.core.agent.prompt import SYSTEM
from app.core.agent.validate import FINAL_ANSWER_TOOL, FinalAnswer, failed, problems
from app.core.plan_edit.model import Proposal, Selection
from app.core.spend import SpendGuard

SEEN_TURNS = 6  # turns whose messages the model is sent (AC-23)
OLD_TOOL_CHARS = 1000  # a tool message of an earlier turn is cut to this
# What the model sees of a tool result (AC-13 says 4,000; one ask_drawings over 5 drawings is
# ~6,800 compact, so 8,000 keeps every drawing's answer); the full result stays in the chat
TOOL_CHARS = 8000
GEOMETRY = frozenset({"box", "polygon", "holes"})  # the model cites ev ids, never coordinates
NUDGE = "Answer with final_answer."
UNBACKED = "I could not back that answer with what the drawings say."

STOPS = {
    "steps": "I ran out of steps before I could answer.",
    "turn_usd": "This question reached the assistant's spending limit for one answer.",
    "seconds": "I ran out of time before I could answer.",
    "budget": "The assistant's budget for this hour is used up.",
    "repeat": "I kept repeating the same step without getting further, so I stopped.",
    "silent": "The assistant did not give an answer.",
}

# Step labels: plain words from the tool and its arguments; {drawing} is the drawing's name
LABELS = {
    "list_drawings": "Listed the project's drawings",
    "ask_drawings": "Asked the drawings: {question}",
    "get_takeoff": "Read the quantities of {drawing}",
    "list_conflicts": "Listed the project's conflicts",
    "list_issues": "Listed the project's issues",
    "run_checks": "Checked the drawings against rule pack {pack}",
    "get_plan_geometry": "Read the rooms and walls of {drawing}, page {page}",
    "list_walls": "Listed the walls of {drawing}, page {page}",
    "propose_remove_wall": "Proposed removing wall {wall_id}",
    "propose_room": "Proposed a room {name} in {selection_id}",
    "search_law": "Searched the law for: {query}",
    "get_clause": "Read clause {clause_id}",
    "search_evidence": "Searched the evidence for: {query}",
    "get_evidence": "Read evidence {evidence_id}",
}


class _EndedError(Exception):
    """The turn ends here with a dont_know saying why."""


def run_turn(
    chat: Chat,
    message: str,
    selection: Sequence[Selection],
    model: ChatModel,
    toolbox: Toolbox,
    caps: Caps,
    guard: SpendGuard,
    clock: Callable[[], float] = time.monotonic,
    names: Mapping[str, str] | None = None,
) -> ChatTurn:
    """Runs one turn and records it in `chat` (messages, turns, proposals, results).
    `names`: drawing id → the drawing's plain name ("Drawn plan 1"), for evidence and steps."""
    return _Run(chat, model, toolbox, caps, guard, clock, names or {}).turn(message, selection)


class _Run:
    def __init__(
        self,
        chat: Chat,
        model: ChatModel,
        toolbox: Toolbox,
        caps: Caps,
        guard: SpendGuard,
        clock: Callable[[], float],
        names: Mapping[str, str],
    ) -> None:
        self.chat, self.model, self.toolbox, self.caps = chat, model, toolbox, caps
        self.guard, self.clock, self.names = guard, clock, names
        self.tools = [*toolbox.tools, FINAL_ANSWER_TOOL]
        self.started = clock()
        self.ledger: dict[str, Json] = {}
        self.proposals: dict[str, Proposal] = {}
        self.sources: list[str] = []
        self.failures: list[bool] = []
        self.steps: list[Step] = []
        self.seen: Counter[tuple[str, str]] = Counter()
        self.cost = 0.0
        self.refused = 0

    def turn(self, message: str, selection: Sequence[Selection]) -> ChatTurn:
        chat = self.chat
        chat.starts.append(len(chat.messages))
        lines = [self.toolbox.describe(chosen) for chosen in selection]
        chat.messages.append({"role": "user", "content": "\n".join([message, *lines])})
        self.sources.append(message)
        try:
            answer = self._loop()
        except _EndedError as ended:
            answer = FinalAnswer(kind="dont_know", text=str(ended))
        chat.minted += len(self.ledger)
        chat.proposals.update(self.proposals)
        turn = self._turn_of(answer)
        chat.turns.append(turn)
        return turn

    def _loop(self) -> FinalAnswer:
        nudged = False
        for _ in range(self.caps.max_steps):
            self._check_caps()
            try:
                reply = self.model.complete(self._window(), self.tools)
            except ChatModelError as error:
                raise _EndedError(f"The assistant model did not answer ({error}).") from None
            self.guard.charge(reply.usd, "agent chat")
            self.cost += reply.usd
            self.chat.messages.append(reply.message)
            calls: list[Json] = reply.message.get("tool_calls") or []
            if not calls:
                if nudged:
                    raise _EndedError(STOPS["silent"])
                nudged = True
                self.chat.messages.append({"role": "user", "content": NUDGE})
                continue
            answer = self._calls(calls)
            if answer is not None:
                return answer
        raise _EndedError(STOPS["steps"])

    def _check_caps(self) -> None:
        if self.guard.exhausted():
            raise _EndedError(STOPS["budget"])
        if self.cost >= self.caps.turn_usd:
            raise _EndedError(STOPS["turn_usd"])
        if self.clock() - self.started >= self.caps.seconds:
            raise _EndedError(STOPS["seconds"])

    def _calls(self, calls: list[Json]) -> FinalAnswer | None:
        """Runs one step's tool calls in order; every call gets its tool message, even when the
        turn ends before it (the next request is refused otherwise)."""
        for at, call in enumerate(calls):
            function: Json = call.get("function") or {}
            name = str(function.get("name", ""))
            given: Any = function.get("arguments") or "{}"
            arguments = given if isinstance(given, str) else json.dumps(given)
            try:
                if at >= self.caps.calls_per_step:
                    cap = self.caps.calls_per_step
                    self._reply(call, _error(f"at most {cap} tool calls per step; call it again"))
                    continue
                if name == "final_answer":
                    answer = self._final(call, arguments)
                    if answer is not None:
                        self._skip(calls[at + 1 :])
                        return answer
                    continue
                self.seen[(name, arguments)] += 1
                if self.seen[(name, arguments)] >= 3:
                    raise _EndedError(STOPS["repeat"])
                self._tool(call, name, arguments)
            except _EndedError:
                self._skip(calls[at:])
                raise
        return None

    def _final(self, call: Json, arguments: str) -> FinalAnswer | None:
        """The answer when it passes the validator; else the model is told why once, and the
        second failure ends the turn."""
        try:
            answer = FinalAnswer.model_validate_json(arguments)
            wrong = problems(
                answer,
                set(self.ledger),
                set(self.proposals),
                self.sources,
                bool(self.failures) and all(self.failures),
            )
        except ValidationError as error:
            answer, wrong = None, [f"bad final_answer arguments: {error.errors()[0]['msg']}"]
        if not wrong:
            self._reply(call, json.dumps({"ok": True}))
            return answer
        self.refused += 1
        if self.refused >= 2:
            self._reply(call, _error("; ".join(wrong)))
            raise _EndedError(UNBACKED)
        self._reply(call, _error("final_answer refused: " + "; ".join(wrong) + ". Fix it."))
        return None

    def _tool(self, call: Json, name: str, arguments: str) -> None:
        start = self.clock()
        out = self.toolbox.run(name, arguments)
        ms = round((self.clock() - start) * 1000, 1)
        try:
            found: Any = json.loads(out)
        except json.JSONDecodeError:
            found = out
        mint(found, self.ledger, self.chat.minted + 1)
        proposal: Any = found.get("proposal") if isinstance(found, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(proposal, dict) and "proposal_id" in proposal:
            try:
                made = Proposal.model_validate(proposal)
                self.proposals[made.proposal_id] = made
            except ValidationError:
                pass  # not a proposal the server can show: final_answer cannot name it
        text = out if isinstance(found, str) else json.dumps(found, ensure_ascii=False)
        self.sources.append(text)
        self.failures.append(failed(found))
        self.chat.results.append({"tool": name, "arguments": arguments, "result": found})
        error = isinstance(found, dict) and "error" in found
        status = "error" if error else "ok"
        self.steps.append(Step(n=len(self.steps) + 1, tool=name, label=self._label(name, arguments),
                               status=status, ms=ms))  # fmt: skip
        self._reply(call, text if isinstance(found, str) else _for_model(found))

    def _reply(self, call: Json, content: str) -> None:
        self.chat.messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                   "content": content})  # fmt: skip

    def _skip(self, calls: list[Json]) -> None:
        for call in calls:
            self._reply(call, _error("not run: the turn ended"))

    def _window(self) -> list[Json]:
        """The system prompt and the last turns' messages; tool messages of earlier turns cut."""
        chat = self.chat
        first, current = chat.starts[-SEEN_TURNS:][0], chat.starts[-1]
        shown: list[Json] = [{"role": "system", "content": SYSTEM}]
        for at in range(first, len(chat.messages)):
            message = chat.messages[at]
            content = message.get("content")
            if at < current and message.get("role") == "tool" and isinstance(content, str):
                message = {**message, "content": content[:OLD_TOOL_CHARS]}
            shown.append(message)
        return shown

    def _label(self, name: str, arguments: str) -> str:
        try:
            args = json.loads(arguments)
            drawing = args.get("drawing_id", "")
            args["drawing"] = self.names.get(drawing) or f"drawing {drawing[:6]}"
            return LABELS[name].format_map(args)
        except (KeyError, ValueError, AttributeError, TypeError):
            return name

    def _turn_of(self, answer: FinalAnswer) -> ChatTurn:
        cited = list(dict.fromkeys([*answer.evidence_ids, *re.findall(r"ev_\d+", answer.text)]))
        number = {ev: n for n, ev in enumerate(cited, start=1)}
        text = re.sub(r"\[?(ev_\d+)\]?", lambda found: f"[{number[found[1]]}]", answer.text)
        kind: TurnKind = answer.kind
        return ChatTurn(
            chat_id=self.chat.chat_id,
            turn=len(self.chat.turns) + 1,
            kind=kind,
            text=text,
            evidence=tuple(self._evidence(n, ev) for ev, n in number.items()),
            edit=self.proposals.get(answer.proposal_id or "") if kind == "edit" else None,
            options=answer.options,
            steps=tuple(self.steps),
            model=self.model.name,
            cost_usd=round(self.cost, 6),
            latency_s=round(self.clock() - self.started, 3),
        )

    def _evidence(self, n: int, ev: str) -> ChatEvidence:
        found = self.ledger[ev]
        level = found["level"]
        return ChatEvidence(
            n=n,
            id=ev,
            drawing_id=found["drawing_id"],
            name=self.names.get(found["drawing_id"]) or found["name"],
            page=found["page"],
            box=found["box"],
            label=found["label"],
            sure=found["sure"],
            level=Level(**{key: level.get(key) for key in ("level", "basis", "text")})
            if level
            else None,
        )


def _for_model(found: Any) -> str:
    """A tool result as the model reads it: compact JSON without geometry or empty fields, its
    lists cut shorter until it fits TOOL_CHARS, else cut as text with a note."""
    slim = _slim(found)
    text = ""
    for keep in (0, 8, 4, 2, 1):
        text = json.dumps(_cut(slim, keep) if keep else slim, ensure_ascii=False,
                          separators=(",", ":"))  # fmt: skip
        if len(text) <= TOOL_CHARS:
            return text
    return text[:TOOL_CHARS] + '\n{"truncated": true}'


def _slim(found: Any) -> Any:
    if isinstance(found, list):
        return [_slim(item) for item in found]  # pyright: ignore[reportUnknownVariableType]
    if isinstance(found, dict):
        return {
            key: _slim(value)
            for key, value in found.items()  # pyright: ignore[reportUnknownVariableType]
            if key not in GEOMETRY and value not in (None, "", [], {})
        }
    return found


def _cut(found: Any, keep: int) -> Any:
    if isinstance(found, list):
        items: list[Any] = [_cut(item, keep) for item in found[:keep]]  # pyright: ignore[reportUnknownVariableType]
        more = len(found) - keep  # pyright: ignore[reportUnknownArgumentType]
        return [*items, f"... {more} more"] if more > 0 else items
    if isinstance(found, dict):
        return {key: _cut(value, keep) for key, value in found.items()}  # pyright: ignore[reportUnknownVariableType]
    return found


def _error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)
