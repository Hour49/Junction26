"""One chat turn (spec AC-1..AC-7): model step → its tool calls → their results → next step, until
a valid `final_answer`, or a cap ends it as `dont_know` with the reason in plain words."""

import contextlib
import json
import re
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from app.core.agent import law
from app.core.agent.evidence import mint
from app.core.agent.model import (
    Caps,
    Chat,
    ChatEvidence,
    ChatTurn,
    Json,
    Level,
    Step,
    TurnKind,
    View,
)
from app.core.agent.ports import ChatModel, ChatModelError, Toolbox
from app.core.agent.prompt import SYSTEM
from app.core.agent.validate import (
    FINAL_ANSWER_TOOL,
    TEXT_CHARS,
    FinalAnswer,
    failed,
    numbers,
    problems,
    shortened,
    unbacked,
)
from app.core.agent.view import (
    MARKS,
    SHOW_ON_PLAN,
    SHOW_ON_PLAN_TOOL,
    ShowArgs,
    bounds,
    pages,
    view_of,
)
from app.core.laws.model import ClauseView
from app.core.plan_edit.law_check import AiFinding, LawCheck, LawNote, validate_law_note
from app.core.plan_edit.model import Proposal, Selection
from app.core.spend import SpendGuard

ASK = "ask_drawings"  # its results are ProjectAnswers the turn returns with an answer built on them
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
    "budget": "The assistant's spending budget is used up.",
    "budget_hour": "The assistant's budget for this hour is used up.",
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
    "propose_room": "Proposed a room {name} in the drawn area",
    "search_law": "Searched the law for: {query}",
    "get_clause": "Read clause {clause_id}",
    "search_evidence": "Searched the evidence for: {query}",
    "get_evidence": "Read evidence {evidence_id}",
}
# A proposal the plan tool refused is no proposal (QA edits-6)
FAILED_LABELS = {
    "propose_remove_wall": "Could not remove wall {wall_id}",
    "propose_room": "Could not place a room {name} in the drawn area",
}
# The label when an argument it names is missing (QA rerun-edits-n2); a tool in neither: its name
PLAIN = {
    "list_drawings": "Listed the project's drawings",
    "ask_drawings": "Asked the drawings",
    "get_takeoff": "Read the quantities of a drawing",
    "list_conflicts": "Listed the project's conflicts",
    "list_issues": "Listed the project's issues",
    "run_checks": "Checked the drawings against a rule pack",
    "get_plan_geometry": "Read the rooms and walls of a drawing",
    "list_walls": "Listed the walls of a drawing",
    "propose_remove_wall": "Proposed removing a wall",
    "propose_room": "Proposed a room in the drawn area",
    "search_law": "Searched the law",
    "get_clause": "Read a law clause",
    "search_evidence": "Searched the evidence",
    "get_evidence": "Read a piece of evidence",
}
FAILED_PLAIN = {
    "propose_remove_wall": "Could not remove a wall",
    "propose_room": "Could not place a room in the drawn area",
}
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth")


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
    context: str = "",
) -> ChatTurn:
    """Runs one turn and records it in `chat` (messages, turns, proposals, results).
    `names`: drawing id → the drawing's plain name ("Drawn plan 1"), for evidence and steps.
    `context`: this turn's lines after the system prompt (the chosen country, its laws)."""
    run = _Run(chat, model, toolbox, caps, guard, clock, names or {})
    run.system = f"{SYSTEM}\n{context}" if context else SYSTEM
    return run.turn(message, selection)


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
        self.system = SYSTEM
        self.tools = [*toolbox.tools, SHOW_ON_PLAN_TOOL, FINAL_ANSWER_TOOL]
        self.started = clock()
        self.ledger: dict[str, Json] = {}  # this turn's places
        self.known: dict[str, Json] = dict(chat.evidence)  # earlier turns' places
        self.proposals: dict[str, Proposal] = {}
        self.sources: list[str] = []
        self.failures: list[bool] = []
        self.steps: list[Step] = []
        self.seen: Counter[tuple[str, str]] = Counter()
        self.cost = 0.0
        self.refused = 0
        self.asked: list[Json] = []  # this turn's ask_drawings results, as Chat.asked keeps them
        self.shown: tuple[list[str], str] | None = None  # show_on_plan's places and caption
        self.reattached: list[Json] = []  # earlier ask_drawings results show_on_plan showed
        self.laws: dict[str, Json] = {}  # proposal id -> its law check as the model read it (LC-8)
        self.clauses: dict[str, Json] = {}  # get_clause results of this turn, by clause id
        self.searched: set[str] = set()  # clause ids search_law returned this turn
        self.kept: dict[str, tuple[AiFinding, ...]] = {}  # proposal id -> notes the server kept

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
        chat.evidence.update(self.ledger)
        chat.asked.extend(self.asked)
        if turn.edit is not None:  # as shown, ev ids and kept law notes included (LC-10)
            chat.proposals[turn.edit.proposal_id] = turn.edit
        chat.turns.append(turn)
        return turn

    def _loop(self) -> FinalAnswer:
        nudged = False
        for _ in range(self.caps.max_steps):
            self._check_caps()
            try:
                reply = self.model.complete(self._window(), self.tools)
            except ChatModelError as error:
                self.guard.charge(error.usd, "agent chat")
                self.cost += error.usd
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
        if why := self.guard.exhausted():  # the total and the hourly limit read differently
            raise _EndedError(STOPS["budget_hour" if "hourly" in why else "budget"])
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
                if name == SHOW_ON_PLAN:
                    self._show(call, arguments)
                    continue
                self._tool(call, name, arguments)
            except _EndedError:
                self._skip(calls[at:])
                raise
        return None

    def _final(self, call: Json, arguments: str) -> FinalAnswer | None:
        """The answer when it passes the validator; else the model is told why once, and the
        second failure ends the turn."""
        long = _too_long(arguments)
        if long:  # cut by the server, so the retry's reason and a second failure are true
            arguments = json.dumps({**json.loads(arguments), "text": shortened(long)})
        try:
            answer = FinalAnswer.model_validate_json(arguments)
            wrong = problems(
                answer,
                set(self.ledger) | set(self.known),
                set(self.proposals),
                self.sources,
                bool(self.failures) and all(self.failures),
            )
        except ValidationError as error:
            answer, wrong = None, [f"bad final_answer arguments: {error.errors()[0]['msg']}"]
        soft, fixed = self._law(answer) if answer is not None else ([], None)
        if long:
            soft.insert(0, f"text too long ({len(long)} characters): shorten it to {TEXT_CHARS}")
        if not wrong and not soft:
            self._reply(call, json.dumps({"ok": True}))
            return answer
        self.refused += 1
        if self.refused >= 2:
            if wrong or fixed is None:
                self._reply(call, _error("; ".join(wrong)))
                raise _EndedError(UNBACKED)
            self._reply(call, json.dumps({"ok": True, "fixed_by_server": soft}))
            return fixed  # wording and law naming never end an edit as dont_know (LC-8)
        self._reply(call, _error("final_answer refused: " + "; ".join(wrong + soft) + ". Fix it."))
        return None

    def _law(self, answer: FinalAnswer) -> tuple[list[str], FinalAnswer]:
        """What the answer gets wrong about building rules (LC-8, LC-9b/c), each a sentence for
        the retry, and the answer as the server fixes it after the retry: banned sentences
        removed, failing rules the text does not name summed up in one appended sentence."""
        soft: list[str] = []
        text = answer.text
        if words := law.banned(text):
            soft.append(f"never write {', '.join(words)}: say 'would not meet' or 'meets'")
            text = law.without_banned(text)
        checked = self.laws.get(answer.proposal_id or "") if answer.kind == "edit" else None
        failing = law.newly_failing(checked)
        uncited = law.uncited(checked, answer.text)
        if uncited:
            evs = ", ".join(str(f.get("ev")) for f in uncited if f.get("ev"))
            soft.append(f"cite the rule(s) this change would newly not meet ({evs})")
        kept, dropped = self._notes(answer)
        soft += dropped
        breaking = [k for k in kept if k.verdict == "would_not_meet"]
        unnamed = [k.ref for k in breaking if k.ref not in answer.text]
        if unnamed:
            soft.append(
                f"name the clause(s) the change would not meet by ref: {'; '.join(unnamed)}"
            )
        self.kept[answer.proposal_id or ""] = tuple(kept)
        findings: list[Json] = (checked or {}).get("findings") or []
        fails = [f for f in findings if "fails" in str(f.get("change"))]
        if law.CLAIM.search(text) and not (fails or breaking):
            soft.append(
                "say 'would not meet' only for a law check finding or a kept law_note; "
                "nothing this turn backs it"
            )
            text = law.without_banned(text, law.CLAIM)
        if uncited or unnamed:
            name = str((checked or {}).get("pack_name") or "the chosen country's rules")
            text = law.appended(text, len(failing) + len(breaking), name)
        return soft, answer.model_copy(update={"text": text})

    def _notes(self, answer: FinalAnswer) -> tuple[list[AiFinding], list[str]]:
        """The answer's law_notes the server keeps (as AiFindings) and why each other was dropped
        (LC-9b, law-kb's validate_law_note)."""
        if not answer.law_notes:
            return [], []
        made = self.proposals.get(answer.proposal_id or "")
        law_check = made.law if made else None
        if answer.kind != "edit" or law_check is None:
            return [], ["law_notes go only with an edit whose proposal has a law check"]
        clauses = self._clause_views(law_check, {note.clause_id for note in answer.law_notes})
        values = [float(number) for number in numbers(self.sources)]
        kept: list[AiFinding] = []
        dropped: list[str] = []
        for note in answer.law_notes:
            given = LawNote.model_validate(note.model_dump())
            found = validate_law_note(given, law_check, clauses, values)
            if found is None:
                dropped.append(
                    f"law_note {note.clause_id} on {note.subject} dropped: its clause, limit, "
                    "value or verdict does not match this turn's tool results"
                )
            else:
                kept.append(found)
        return kept, dropped

    def _clause_views(self, law_check: LawCheck, cited: set[str]) -> dict[str, ClauseView]:
        """Every clause of this turn by id: the law check's related ones, get_clause results,
        and a search_law hit a note cites, fetched with get_clause (not a step)."""
        found: dict[str, ClauseView] = {c.id: c for c in law_check.related}
        for clause_id in cited & self.searched - set(self.clauses) - set(found):
            self._law_results("get_clause", self.toolbox.run("get_clause", json.dumps(
                {"clause_id": clause_id})))  # fmt: skip
        for clause_id, given in self.clauses.items():
            with contextlib.suppress(ValidationError):  # not a clause: no note stands on it
                found.setdefault(clause_id, ClauseView.model_validate(given))
        return found

    def _tool(self, call: Json, name: str, arguments: str) -> None:
        start = self.clock()
        out = self.toolbox.run(name, arguments)
        ms = round((self.clock() - start) * 1000, 1)
        try:
            found: Any = json.loads(out)
        except json.JSONDecodeError:
            found = out
        before = set(self.ledger)
        mint(found, self.ledger, self.chat.minted + 1)
        if name == ASK and isinstance(found, dict):  # kept as the route gives it, without ev ids
            given = json.loads(out)
            self.asked.append(_asked(found, set(self.ledger) - before, given))  # pyright: ignore[reportUnknownArgumentType]
        proposal: Any = found.get("proposal") if isinstance(found, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(proposal, dict) and "proposal_id" in proposal:
            made = self.toolbox.proposal(str(proposal["proposal_id"]))  # pyright: ignore[reportUnknownArgumentType]
            try:  # the plan tools' own, law included; else as the result gives it
                made = made or Proposal.model_validate(proposal)
                self.proposals[made.proposal_id] = made
            except ValidationError:
                pass  # not a proposal the server can show: final_answer cannot name it
            checked: Any = found.get("law")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if isinstance(checked, dict):
                self.laws[str(proposal["proposal_id"])] = checked  # pyright: ignore[reportUnknownArgumentType]
        self._law_results(name, out)
        text = out if isinstance(found, str) else json.dumps(found, ensure_ascii=False)
        self.sources.append(text)
        self.failures.append(failed(found))
        self.chat.results.append({"tool": name, "arguments": arguments, "result": found})
        bad = self.failures[-1]  # an error, or refused / cannot_edit / unknown (QA edits-6)
        label = (
            self._label(name, arguments, FAILED_LABELS, FAILED_PLAIN)
            if bad
            else self._label(name, arguments)
        )
        self.steps.append(Step(n=len(self.steps) + 1, tool=name, label=label,
                               status="error" if bad else "ok", ms=ms))  # fmt: skip
        self._reply(call, text if isinstance(found, str) else _for_model(found))

    def _show(self, call: Json, arguments: str) -> None:
        """show_on_plan (contract B): the places this turn shows, or the model is told why not."""
        start = self.clock()
        places = {**self.known, **self.ledger}
        try:
            args = ShowArgs.model_validate_json(arguments)
        except ValidationError as error:
            return self._show_failed(call, start, f"bad arguments: {error.errors()[0]['msg']}")
        ids, entry = list(args.evidence_ids), None
        if args.answer == "latest":
            if not (self.chat.asked or self.asked):
                return self._show_failed(call, start, "no ask_drawings answer in this chat yet")
            entry = [*self.chat.asked, *self.asked][-1]
            ids = list(entry["disputed" if args.marks == "disputed" else "marks"])
            if not ids:
                which = "disputed marks" if args.marks == "disputed" else "marks"
                return self._show_failed(call, start, f"the latest answer has no {which}")
        if not ids:
            return self._show_failed(call, start, "give evidence_ids or answer: latest")
        if unknown := [ev for ev in ids if ev not in places]:
            missing = ", ".join(unknown)
            return self._show_failed(call, start, f"no place in this chat has id {missing}")
        groups = pages(ids, places)
        if len(groups) > 1 and entry is None:
            listed = "; ".join(
                f"{self._name(drawing, places[evs[0]])} page {page}: {', '.join(evs)}"
                for (drawing, page), evs in groups.items()
            )
            return self._show_failed(call, start, f"show one page at a time: {listed}")
        (drawing, page), ids = max(groups.items(), key=lambda group: len(group[1]))
        ids = ids[:MARKS]
        name = self._name(drawing, places[ids[0]])
        given = re.sub(r"\s*\[?ev_\d+\]?", "", _plain_ids(args.caption)).strip()
        backing = [*self.sources, str(len(ids)), *(str(places[ev]["label"]) for ev in ids)]
        if entry is not None:
            backing.append(json.dumps(entry["answer"]))
            self.reattached.append(entry["answer"])
        if given and not unbacked(given, backing):
            caption, label = given, f"Showed {given} on the plan"
        else:  # the server's words: a caption with a number no tool gave is not shown
            caption = f"{len(ids)} {'place' if len(ids) == 1 else 'places'} on {name}, page {page}"
            label = f"Showed {caption}"
        self.shown = (ids, caption)
        others = [{"drawing": self._name(d, places[evs[0]]), "page": p, "places": len(evs)}
                  for (d, p), evs in groups.items() if (d, p) != (drawing, page)]  # fmt: skip
        result: Json = {"status": "ok", "shown": len(ids), "drawing": name, "page": page}
        if others:
            result["other_pages"] = others
        text = json.dumps(result, ensure_ascii=False)
        # what it showed backs the answer's numbers: a tool result, and the answer it shows
        self.sources.append(text)
        if entry is not None:
            self.sources.append(json.dumps(entry["answer"]))
        self._show_step(call, start, label, "ok", text)

    def _show_failed(self, call: Json, start: float, why: str) -> None:
        self._show_step(call, start, "Could not show that on the plan", "error",
                        _error(f"show_on_plan: {why}"))  # fmt: skip

    def _show_step(self, call: Json, start: float, label: str, status: str, reply: str) -> None:
        ms = round((self.clock() - start) * 1000, 1)
        self.steps.append(Step(n=len(self.steps) + 1, tool=SHOW_ON_PLAN, label=label,
                               status="ok" if status == "ok" else "error", ms=ms))  # fmt: skip
        self._reply(call, reply)

    def _name(self, drawing_id: str, place: Json) -> str:
        """A drawing's plain name ("Drawn plan 1"), else the name its place came with."""
        return self.names.get(drawing_id) or place.get("name") or f"drawing {drawing_id[:6]}"

    def _law_results(self, name: str, out: str) -> None:
        """The clauses this turn's law tools returned, as they returned them (LC-9b)."""
        try:
            found: Any = json.loads(out)
        except json.JSONDecodeError:
            return
        if name == "get_clause" and isinstance(found, dict) and "id" in found:
            self.clauses[str(found["id"])] = found  # pyright: ignore[reportUnknownArgumentType]
        if name == "search_law" and isinstance(found, dict):
            hits: list[Any] = found.get("hits") or []  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            found_ids: list[Any] = [hit.get("id") for hit in hits if isinstance(hit, dict)]  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            self.searched |= {str(found_id) for found_id in found_ids if found_id}

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
        shown: list[Json] = [{"role": "system", "content": self.system}]
        for at in range(first, len(chat.messages)):
            message = chat.messages[at]
            content = message.get("content")
            if at < current and message.get("role") == "tool" and isinstance(content, str):
                message = {**message, "content": content[:OLD_TOOL_CHARS]}
            shown.append(message)
        return shown

    def _label(
        self,
        name: str,
        arguments: str,
        labels: Mapping[str, str] = LABELS,
        plain: Mapping[str, str] = PLAIN,
    ) -> str:
        try:
            args = json.loads(arguments)
            if drawing := args.get("drawing_id"):
                args["drawing"] = self.names.get(drawing) or f"drawing {drawing[:6]}"
            return (labels.get(name) or LABELS[name]).format_map(args)
        except (KeyError, ValueError, AttributeError, TypeError):
            return plain.get(name) or PLAIN.get(name) or name.replace("_", " ").capitalize()

    def _turn_of(self, answer: FinalAnswer) -> ChatTurn:
        # The sources are the places the text cites, in its order; evidence_ids only when the
        # text cites none (AC-5)
        cited = list(dict.fromkeys(re.findall(r"ev_\d+", answer.text) or answer.evidence_ids))
        shown = self.shown[0] if self.shown else []
        # the places show_on_plan showed are sources too, numbered after the cited ones
        number = {ev: n for n, ev in enumerate(dict.fromkeys([*cited, *shown]), start=1)}
        text = re.sub(r"\[?(ev_\d+)\]?", lambda found: f"[{number[found[1]]}]", answer.text)
        for drawing_id, file in self._files():  # a drawing by its plain name, not its file
            text = text.replace(file, self.names.get(drawing_id) or file)
        text = _plain_ids(text)
        kind: TurnKind = answer.kind
        answers = self._answers(set(cited) | set(shown), kind)
        if kind == "answer" and any(_conflicted(given) for given in answers):
            kind = "conflict"  # the drawings' methods disagree: never a plain answer (QA answers-9)
        # an earlier answer show_on_plan showed comes back with the turn (its card), as it was
        answers += tuple(a for a in self.reattached if all(a is not b for b in answers))
        return ChatTurn(
            chat_id=self.chat.chat_id,
            turn=len(self.chat.turns) + 1,
            kind=kind,
            text=text,
            evidence=tuple(self._evidence(n, ev) for ev, n in number.items()),
            edit=self._edit(answer.proposal_id) if kind == "edit" else None,
            options=answer.options,
            steps=tuple(self.steps),
            model=self.model.name,
            cost_usd=round(self.cost, 6),
            latency_s=round(self.clock() - self.started, 3),
            answers=answers,
            view=self._view(kind, cited, number, answer.proposal_id),
        )

    def _view(
        self, kind: TurnKind, cited: list[str], number: Mapping[str, int], proposal_id: str | None
    ) -> View | None:
        """The plan the turn shows (contract A): show_on_plan's places; else an edit's page
        around the proposal; else the page of the first cited place with the cited places on it."""
        places = {**self.known, **self.ledger}
        if self.shown:
            ids, caption = self.shown
            first = places[ids[0]]
            place = (str(first["drawing_id"]), int(first["page"]))
            name = self._name(place[0], first)
            return view_of(place, ids, places, number, name, caption, "show_on_plan")
        made = self.proposals.get(proposal_id or "") if kind == "edit" else None
        if made is not None:
            place = (made.drawing_id, made.page)
            items = (*made.removed, *made.added, *made.rooms)
            around = [bounds(item.polygon) for item in items if len(item.polygon) > 0]
            ids = pages(cited, places).get(place, [])
            if not ids and not around:
                return None
            name = self.names.get(made.drawing_id)
            return view_of(place, ids, places, number, name, None, "evidence", around)
        if not cited:
            return None
        first = places[cited[0]]
        place = (str(first["drawing_id"]), int(first["page"]))
        ids = pages(cited, places)[place]
        return view_of(place, ids, places, number, self._name(place[0], first), None, "evidence")

    def _edit(self, proposal_id: str | None) -> Proposal | None:
        """The proposal the answer names, its law check with each finding's ev id (as minted on
        the tool result, same order) and the AI findings the server kept."""
        made = self.proposals.get(proposal_id or "")
        if made is None or made.law is None:
            return made
        shown: list[Json] = self.laws.get(made.proposal_id, {}).get("findings") or []
        evs = [given.get("ev") for given in shown] + [None] * len(made.law.findings)
        findings = tuple(
            finding.model_copy(update={"ev": ev})
            for finding, ev in zip(made.law.findings, evs, strict=False)
        )
        kept = (*made.law.ai_findings, *self.kept.get(made.proposal_id, ()))
        law_check = made.law.model_copy(update={"findings": findings, "ai_findings": kept})
        return made.model_copy(update={"law": law_check})

    def _files(self) -> set[tuple[str, str]]:
        """(drawing id, file name) of every drawing this turn's results named."""
        parts: list[Json] = []
        for entry in self.asked:
            parts += entry["answer"].get("parts") or []
        named = {(str(p.get("drawing_id")), str(p.get("name"))) for p in parts if p.get("name")}
        return named | {(f["drawing_id"], f["name"]) for f in self.ledger.values() if f["name"]}

    def _answers(self, cited: set[str], kind: TurnKind) -> tuple[Json, ...]:
        """The ask_drawings results the answer rests on: those whose places it cites; when it
        cites none, every one for an answer and those in which a drawing refused for a dont_know
        or needs_input."""
        if cited:  # earlier turns' answers too: a follow-up may cite their places (item 1)
            every = [*self.chat.asked, *self.asked]
            return tuple(e["answer"] for e in every if set(e["evs"]) & cited)
        if kind == "answer":
            return tuple(e["answer"] for e in self.asked)
        if kind in ("dont_know", "needs_input"):
            return tuple(e["answer"] for e in self.asked if _refused(e["answer"]))
        return ()

    def _evidence(self, n: int, ev: str) -> ChatEvidence:
        found = self.ledger.get(ev) or self.known[ev]
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


def _asked(found: Json, evs: set[str], given: Json) -> Json:
    """An ask_drawings result as Chat.asked keeps it. `found`: the result with its ev ids minted;
    `evs`: those ids; `given`: the result as the route gave it."""
    marks: list[str] = []
    disputed: list[str] = []
    parts: list[Json] = found.get("parts") or []
    for part in parts:
        answer: Json = part.get("answer") or {}
        quantity: Json = answer.get("quantity") or {}
        check: Json = answer.get("check") or {}
        marks += _evs(answer.get("marks") or quantity.get("marks"))
        disputed += _evs(check.get("disputed"))
    ordered = sorted(evs, key=lambda ev: int(ev.removeprefix("ev_")))
    return {"answer": given, "evs": ordered, "marks": marks, "disputed": disputed}


def _evs(items: Any) -> list[str]:
    """The ev ids of a list of objects, in order."""
    out: list[str] = []
    for item in items if isinstance(items, list) else []:  # pyright: ignore[reportUnknownVariableType]
        ev: Any = item.get("ev") if isinstance(item, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(ev, str):
            out.append(ev)
    return out


def _refused(asked: Json) -> bool:
    """Whether a drawing refused in an ask_drawings result."""
    parts: list[Json] = asked.get("parts") or []
    answers: list[Json] = [part.get("answer") or {} for part in parts]
    return any(answer.get("refusal") for answer in answers)


def _plain_ids(text: str) -> str:
    """`text` without selection and proposal ids (QA rerun-edits-n1): "(sel_2)" goes, "sel_2"
    reads "the second area you drew", "proposal p1" / "p1" reads "the proposal"."""
    text = re.sub(r"\s*\((?:sel_\d+|p\d+)\)", "", text)
    text = re.sub(r"\bsel_(\d+)\b", lambda found: _area(int(found[1])), text)
    return re.sub(r"\b(?:(?:the|this) )?(?:proposal )?p\d+\b", "the proposal", text)


def _area(n: int) -> str:
    return f"the {ORDINALS[n - 1]} area you drew" if 1 <= n <= len(ORDINALS) else "an area you drew"


def _conflicted(asked: Json) -> bool:
    """Whether a drawing's quantity in an ask_drawings result is a conflict."""
    parts: list[Json] = asked.get("parts") or []
    answers: list[Json] = [part.get("answer") or {} for part in parts]
    quantities: list[Json] = [answer.get("quantity") or {} for answer in answers]
    return any(quantity.get("status") == "conflict" for quantity in quantities)


def _too_long(arguments: str) -> str | None:
    """final_answer's text when it is over TEXT_CHARS, else None."""
    try:
        given: Any = json.loads(arguments)
    except json.JSONDecodeError:
        return None
    text: Any = given.get("text") if isinstance(given, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return text if isinstance(text, str) and len(text) > TEXT_CHARS else None


def _for_model(found: Any) -> str:
    """A tool result as the model reads it: compact JSON without geometry or empty fields. Until
    it fits TOOL_CHARS the longest list is halved, keeping its first items as they are; how many
    were cut goes beside it as `<key>_more` (a cut top-level list becomes {items, items_more}).
    Still too long: cut as text with a note."""
    slim = _slim(found)
    keeps: dict[tuple[Any, ...], int] = {}
    text = _compact(_cut(slim, keeps))
    while len(text) > TOOL_CHARS:
        longest = _longest(slim, keeps)
        if longest is None:
            return text[:TOOL_CHARS] + '\n{"truncated": true}'
        path, kept = longest
        keeps[path] = kept // 2
        text = _compact(_cut(slim, keeps))
    return text


def _compact(found: Any) -> str:
    return json.dumps(found, ensure_ascii=False, separators=(",", ":"))


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


def _cut(found: Any, keeps: Mapping[tuple[Any, ...], int], path: tuple[Any, ...] = ()) -> Any:
    """`found` with the list at each path in `keeps` cut to its first `keeps[path]` items."""
    if isinstance(found, list):
        items: list[Any] = found  # pyright: ignore[reportUnknownVariableType]
        kept = [_cut(item, keeps, (*path, at)) for at, item in enumerate(items[: keeps.get(path)])]
        if path or len(kept) == len(items):
            return kept
        return {"items": kept, "items_more": len(items) - len(kept)}
    if isinstance(found, dict):
        out: Json = {}
        for key, value in found.items():  # pyright: ignore[reportUnknownVariableType]
            out[key] = cut = _cut(value, keeps, (*path, key))  # pyright: ignore[reportUnknownArgumentType]
            if isinstance(value, list) and len(cut) < len(value):  # pyright: ignore[reportUnknownArgumentType]
                out[f"{key}_more"] = len(value) - len(cut)  # pyright: ignore[reportUnknownArgumentType]
        return out
    return found


def _longest(
    found: Any, keeps: Mapping[tuple[Any, ...], int], path: tuple[Any, ...] = ()
) -> tuple[tuple[Any, ...], int] | None:
    """The path and kept length of the list of more than one kept item that is longest as JSON
    once cut, or None when every list is down to one item."""
    best: tuple[int, tuple[Any, ...], int] | None = None
    stack: list[tuple[Any, tuple[Any, ...]]] = [(found, path)]
    while stack:
        here, at = stack.pop()
        if isinstance(here, list):
            items: list[Any] = here[: keeps.get(at)]  # pyright: ignore[reportUnknownVariableType]
            size = len(_compact(_cut(here, keeps, at)))
            if len(items) > 1 and (best is None or size > best[0]):
                best = (size, at, len(items))
            stack += [(item, (*at, n)) for n, item in enumerate(items)]
        elif isinstance(here, dict):
            stack += [(value, (*at, key)) for key, value in here.items()]  # pyright: ignore[reportUnknownVariableType]
    return None if best is None else (best[1], best[2])


def _error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)
