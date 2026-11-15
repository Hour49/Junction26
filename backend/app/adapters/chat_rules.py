"""The no-keys chat model (CHAT_MODEL=rules, spec AC-11): a deterministic planner behind the same
port as Gemini. From this turn's user message, its selection lines and the tool results so far it
emits the next tool call; every sentence it ends with is built from those tool results, so the
validator passes it. It costs nothing and is the model of the e2e tests and the no-keys demo."""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.agent.loop import NUDGE, UNBACKED
from app.core.agent.ports import Reply
from app.core.agent.review import DOUBT, REVIEWED, pushed
from app.core.agent.rooms import name_words

Json = dict[str, Any]

EDIT = re.compile(
    r"\b(remove|break|knock(ed)? down|demolish|take out|merge|enlarge|larger|bigger|extend)\b"
)
STRUCTURE = re.compile(r"load[- ]?bearing|structural|carr(y|ies) (the )?load")
# A question about the building law (answers-6): what a rule asks, not what the drawing shows
LAW = re.compile(
    r"\b(laws?|legal|regulations?|rules?|codes?|permits?|allowed|minimum|maximum|must|"
    r"required|requirements?|clauses?)\b|§|say about"
)
PACK = re.compile(r"\(pack ([a-z]{2}(?:-[a-z]{2})?)\)")  # the chosen country, as the loop states it
NO_PACK = (
    "No country is chosen, so I can't look up its building rules. Pick a country above the chat "
    "and ask again."
)
ROOM = re.compile(r"\broom\b")
# "Where are they?" about the last answer (the "Show them on the plan" chip, contract F)
SHOW = re.compile(
    r"\b(show me where|where are they|show (them|it|me them) on the plan|mark them)\b"
)
# Placing a room by its type's word ("Put a toilet here") rather than the word room (multi)
PLACE = re.compile(  # at the start: "Is this a good place for a kitchen?" asks (review-361 S2)
    r"^\s*(please |can you |could you |let's |i want to )?"
    r"(put|place|add|make|create|draw|build|turn|convert|mark|insert)\b"
)
# A word for a room, as Room.type names it
ROOM_WORDS = {
    "bathroom": "bathroom", "bath": "bathroom", "washroom": "bathroom", "shower": "bathroom",
    "toilet": "wc", "wc": "wc", "bedroom": "bedroom", "kitchen": "kitchen", "living": "living",
    "lounge": "living", "hall": "hall", "hallway": "hall", "corridor": "hall", "entrance": "hall",
    "storage": "storage", "closet": "storage", "sauna": "sauna", "balcony": "balcony",
}  # fmt: skip
ROOM_WORD = re.compile(r"\b(" + "|".join(ROOM_WORDS) + r")s?\b")
# "Which drawing has the largest floor area?": the drawings answer one drawing at a time, so it is
# asked as each drawing's total and the top one is named from the loop's `answered` list
WHICH = re.compile(
    r"\bwhich\s+(?:drawing|plan|sheet|file)s?\b.*?\b(?P<word>largest|biggest|smallest|most|fewest"
    r"|least)\b(?P<what>[^?]*)"
)
BIGGER = {"largest": "largest", "biggest": "largest", "smallest": "smallest"}
NUMBER_OF = re.compile(r"^(?:total\s+)?(?:number|count|amount)\s+of\s+(?P<things>.+)$")
# an answer in feet is compared in metres (review-483); the unit said after the winning value
METRIC = {"ft2": ("m2", 0.09290304), "ft": ("m", 0.3048)}
SAID_UNIT = {"m2": " m²", "m": " m", "m3": " m³"}
LOAD = (
    "These drawings do not say which walls carry load. A structural drawing, a building model "
    "that marks load-bearing walls, or a structural engineer would settle it."
)
OTHER_AREAS = " I used the first area you drew, not the second: ask again for that one."
TRY_THESE = re.compile(r"\s*Try one of these instead\.?")  # the card labels its own options
ONE_ROOM = "area:room|name="  # a suggestion about one room, by its printed name
TRIED = 3  # drawings tried for an editable plan before giving up
# SV-26: services rules (decision 0017), used only when the services tools are offered
TERMINALS = {"radiator": "space_heater", "heater": "space_heater", "socket": "outlet",
             "outlet": "outlet", "air terminal": "air_terminal", "diffuser": "air_terminal",
             "boiler": "boiler"}  # fmt: skip
TERMINAL = re.compile(r"\b(" + "|".join(TERMINALS) + r")s?\b")
# a terminal is what is moved: at most two words after the verb ("move this diffuser", not
# "move the door next to the socket")
MOVE = re.compile(r"\b(move|relocate|shift)(\s+\w+){0,2}?\s+(" + "|".join(TERMINALS) + r")s?\b")
ASKS = (  # the network question a message asks, in ask_services' words
    # "what supplies are needed" asks for materials, not for the network
    (re.compile(r"\bwhat (feeds|supplies)\b(?!\s+(are|is|were|do|does|did|we|i|you)\b)"), "feeds"),
    (re.compile(r"\bwhat\b.*\bcuts? off\b"), "cut_off"),
    (re.compile(r"\bwhat (does|do)\b.*\bserve\b"), "terminals_served"),
)
ELEMENT, WALL = re.compile(r"\be\d{1,6}\b"), re.compile(r"\bsw\d{1,5}\b")
# "Which radiators are in the bedroom?", "How many sinks are there in Küche 1-3?": the room's
# services listed (QA #430); sinks and toilets only here, not as something moved
IN_ROOM_TERMINALS = {**TERMINALS, "sink": "sanitary_terminal", "washbasin": "sanitary_terminal",
                     "basin": "sanitary_terminal", "toilet": "sanitary_terminal"}  # fmt: skip
IN_ROOM_TERMINAL = re.compile(r"\b(" + "|".join(IN_ROOM_TERMINALS) + r")s?\b")
LISTING = re.compile(r"\b(how many|which|what|list|count|are there|is there)\b")
IN_ROOM = re.compile(  # the LAST "in <room>" at the end, before an "on level 2"
    r".*\b(?:in|inside)\s+(?:the\s+)?([^?!,]+?)(?:\s+(?:on|at)\s+.*)?[\s?!.]*$", re.I
)
NOT_A_ROOM = re.compile(  # "in total", "in the building model", "in all bathrooms", "on a floor"
    r"\b(total|all|every|each|building|model|project|house|file|floor|floors|storey|storeys|story"
    r"|stories|level|levels|basement|ground|attic|plan|drawing)\b",
    re.I,
)


@dataclass
class _Turn:
    message: str
    selections: list[str]
    pack: str | None = None
    done: list[tuple[str, Json, Any]] = field(default_factory=list[tuple[str, Json, Any]])

    def result(self, name: str, **args: Any) -> Any:
        """The result of the last call of `name` with these arguments (any, when none given)."""
        for called, given, found in reversed(self.done):
            if called == name and all(given.get(k) == v for k, v in args.items()):
                return found
        return None


class RulesChatModel:
    name = "rules"

    def complete(self, messages: list[Json], tools: list[Json]) -> Reply:
        offered = {tool["function"]["name"] for tool in tools}
        name, arguments = _next(_turn_of(messages), offered)
        call = {"id": f"call_{len(messages)}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)}}  # fmt: skip
        return Reply({"role": "assistant", "content": None, "tool_calls": [call]}, 0.0)


def _turn_of(messages: list[Json]) -> _Turn:
    start = max(
        at for at, m in enumerate(messages) if m.get("role") == "user" and m.get("content") != NUDGE
    )
    first, *rest = str(messages[start]["content"]).split("\n")
    turn = _Turn(first, [line for line in rest if line.startswith("sel_")])
    for line in rest:  # the review the loop ran for a doubt (DOUBT), as a tool result
        if line.startswith(REVIEWED):
            turn.done.append(("review_answer", {}, json.loads(line.removeprefix(REVIEWED))))
    for message in messages[: start + 1]:  # the system prompt or the turn's context line
        if message.get("role") in ("system", "user") and (
            found_pack := PACK.search(str(message.get("content") or ""))
        ):
            turn.pack = found_pack[1]
    calls: dict[str, tuple[str, Json]] = {}
    for message in messages[start + 1 :]:
        for call in message.get("tool_calls") or []:
            function = call["function"]
            calls[call["id"]] = (function["name"], json.loads(function.get("arguments") or "{}"))
        if message.get("role") == "tool" and message.get("tool_call_id") in calls:
            name, args = calls[message["tool_call_id"]]
            try:
                found: Any = json.loads(message["content"])
            except json.JSONDecodeError:
                found = {"error": "cut"}  # a result too long for the window: not ours to read
            turn.done.append((name, args, found))
    return turn


def _final(
    kind: str, text: str, evidence: list[str] | None = None, **more: Any
) -> tuple[str, Json]:
    cited = (evidence or [])[:12]
    return "final_answer", {"kind": kind, "text": text[:1200], "evidence_ids": cited, **more}


REGION = re.compile(r"^sel_\d+: (?:region\b|a line .*, not an area$)")


def _next(turn: _Turn, offered: set[str]) -> tuple[str, Json]:
    if turn.done and turn.done[-1][0] == "final_answer":  # the validator refused it
        return _final("dont_know", UNBACKED)
    words = turn.message.lower()
    if STRUCTURE.search(words):
        return _final("dont_know", LOAD)
    # before the plan rules ("move the radiator in this room"), but a wall edit, a law question
    # or a doubt keeps its own rule ("what is cut off if we remove the wall", review S2)
    other = (
        (EDIT.search(words) and "list_walls" in offered) or LAW.search(words) or DOUBT.search(words)
    )
    if "list_services" in offered and not other:
        if MOVE.search(words) and "propose_move_terminal" in offered:
            return _move_terminal(turn, words)
        op = next((op for pattern, op in ASKS if pattern.search(words)), None)
        if op is not None and "ask_services" in offered:
            return _ask_services(turn, words, op)
        kind = IN_ROOM_TERMINAL.search(words)
        room = IN_ROOM.search(turn.message.strip())
        if kind and room and LISTING.search(words) and not NOT_A_ROOM.search(room[1]):
            step = _in_room(turn, words, kind[1], room[1])
            if step is not None:  # None: no services model, so the drawings answer as before
                return step
    # a drawn area, or a sideways drag described as "a line ..., not an area" (QA robust-10):
    # propose_room gives the true reason for that one
    regions = [line.split(":")[0] for line in turn.selections if REGION.search(line)]
    placing = ROOM.search(words) or (ROOM_WORD.search(words) and PLACE.search(words))
    if regions and placing and "propose_room" in offered:
        found = turn.result("propose_room")
        if found is None:
            return "propose_room", {"selection_id": regions[0], "name": _room_name(words)}
        return _edit(found, [], OTHER_AREAS if len(regions) > 1 else "")  # edits-5
    if EDIT.search(words) and "list_walls" in offered:
        return _remove_wall(turn, words)
    if LAW.search(words):
        return _law(turn, offered)
    if DOUBT.search(words) and ("review_answer" in offered or turn.result("review_answer")):
        return _sure(turn)
    if SHOW.search(words) and "show_on_plan" in offered:
        return _show(turn)
    which = _which(words)
    found = turn.result("ask_drawings")
    if found is None:
        return "ask_drawings", {"question": which[0] if which else turn.message[:500]}
    if which and found.get("answered"):
        return _compared(found["answered"], which[1], which[2])
    words = name_words(turn.message)
    if "find_rooms" in offered and words and _refused_room(found):
        rooms = turn.result("find_rooms")
        if rooms is None:
            return "find_rooms", {"query": " ".join(words)}
        if (picked := _rooms(rooms)) is not None:
            return picked
    return _answer(found)


def _services(turn: _Turn, words: str, kind: str | None = None) -> tuple[str, Json] | Json:
    """This turn's first list_services that worked (narrowed by the terminal kind and the
    selection) and, when a kind narrows it, found one; or the next call to find the drawing with
    a services model: list_drawings, then list_services per drawing, a drawing a selection names
    first, then IFC files. Each IFC file is its own model, so an empty list of one goes on to the
    next: with a kind, every IFC file is asked (review-521: the heating model listed 4th was never
    asked under TRIED), else TRIED drawings; when all are empty, the first. `kind`: the one a
    room question counts (IN_ROOM_TERMINALS), else the terminal word's."""
    listed = [(a, f) for n, a, f in turn.done if n == "list_services" and "room_id" not in a]
    worked = [f for _, f in listed if isinstance(f, dict) and "error" not in f]
    word = TERMINAL.search(words)
    kind = kind or (TERMINALS[word[1]] if word else None)
    ok = next((f for f in worked if f.get("items") or not kind), None)
    if ok is not None:
        return ok
    drawings = turn.result("list_drawings")
    if drawings is None:
        return "list_drawings", {}
    if isinstance(drawings, dict):  # a cut list, as loop._for_model gives it
        drawings = drawings.get("items")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    found: list[Json] = [d for d in drawings or [] if isinstance(d, dict)]  # pyright: ignore[reportUnknownVariableType]

    def selected(d: Json) -> str | None:
        return next((line.split(":")[0] for line in turn.selections
                     if f" on {d.get('name')} page " in line), None)  # fmt: skip

    found.sort(key=lambda d: (selected(d) is None, d.get("kind") != "ifc"))
    models = sum(1 for d in found if d.get("kind") == "ifc") if kind else 0
    if len(listed) < min(max(TRIED, models), len(found)):
        drawing = found[len(listed)]
        args: Json = {"drawing_id": drawing["drawing_id"]}
        if kind:
            args["kind"] = kind
        if sel := selected(drawing):
            args["selection_id"] = sel
        return "list_services", args
    if worked:  # every model's list is empty
        return worked[0]
    if not any(d.get("kind") == "ifc" for d in found) and all("drawing_id" in a for a, _ in listed):
        # an IFC set aside at upload is in no drawing list: the project's only services model
        return "list_services", {"kind": kind} if kind else {}
    why = next((str(f.get("error")) for _, f in listed if isinstance(f, dict)), None)
    return _final("dont_know", f"I can't find the building's services: {why or 'no drawings'}.")


def _in_room(turn: _Turn, words: str, word: str, room: str) -> tuple[str, Json] | None:
    """The terminals of one kind in the room the message names, by its name or id
    (list_services' room_id); None when the project has no services model to list."""
    found = _services(turn, words, IN_ROOM_TERMINALS[word])
    if isinstance(found, tuple):
        return None if found[0] == "final_answer" else found
    if _beside(turn, found["drawing_id"]):  # #491 review: the drawings answer, as before
        return None
    listed = turn.result("list_services", room_id=room)
    if listed is None:
        kind = IN_ROOM_TERMINALS[word]
        return "list_services", {"drawing_id": found["drawing_id"], "room_id": room, "kind": kind}
    sanitary = word not in TERMINALS  # an architecture model counts sinks and toilets too
    if not isinstance(listed, dict) or "error" in listed:
        if sanitary and _other_ifc(turn, found["drawing_id"]):
            return None  # review-517: its room and fixtures are in the other model
        why = listed.get("error") if isinstance(listed, dict) else None
        return _final("dont_know", f"I can't tell: {why or 'the services list failed'}.")
    items: list[Json] = [i for i in listed.get("items") or [] if isinstance(i, dict)]
    count = len(items) + int(listed.get("more") or 0)
    if sanitary and not count and _other_ifc(turn, found["drawing_id"]):
        return None  # not "0 sinks": the services model holds none, the architecture model may
    name = (listed.get("room") or {}).get("name") or room
    cited = ", ".join(f"{i.get('label')} ({i['id']})" for i in items[:10])
    text = f"{count} {word}{'' if count == 1 else 's'} in {name}" + (
        f": {cited}." if cited else "."
    )
    return _final("answer", text, [str(i["ev"]) for i in items[:10] if i.get("ev")])


def _other_ifc(turn: _Turn, services: str) -> bool:
    """The project lists another IFC drawing besides the services model (an architecture model)."""
    drawings = turn.result("list_drawings")
    if isinstance(drawings, dict):  # a cut list, as loop._for_model gives it
        drawings = drawings.get("items")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    listed: list[Json] = [d for d in drawings or [] if isinstance(d, dict)]  # pyright: ignore[reportUnknownVariableType]
    return any(d.get("drawing_id") != services and d.get("kind") == "ifc" for d in listed)


def _beside(turn: _Turn, services: str) -> bool:
    """The project has a drawing besides the services model that is no IFC file (a plan, a
    picture): a question about a room then goes to the drawings; a project of IFC files only (or
    none listed, an IFC set aside) asks the services model about a room (#430 R3)."""
    drawings = turn.result("list_drawings")
    if isinstance(drawings, dict):  # a cut list, as loop._for_model gives it
        drawings = drawings.get("items")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    listed: list[Json] = [d for d in drawings or [] if isinstance(d, dict)]  # pyright: ignore[reportUnknownVariableType]
    return any(d.get("drawing_id") != services and d.get("kind") != "ifc" for d in listed)


def _picked(words: str, items: list[Json]) -> tuple[str | None, list[Json]]:
    """The element id the message names (kept even when the list was cut), else the listed
    terminals that match."""
    named = ELEMENT.search(words)
    if named:
        name = named[0].upper()
        return name, [i for i in items if i.get("id") == name]
    return None, items


def _move_terminal(turn: _Turn, words: str) -> tuple[str, Json]:
    found = _services(turn, words)
    if isinstance(found, tuple):
        return found
    drawing, word = found["drawing_id"], TERMINAL.search(words)[1]  # pyright: ignore[reportOptionalSubscript]
    named, items = _picked(words, [i for i in found.get("items") or [] if isinstance(i, dict)])
    if named is None and len(items) != 1:
        if not items:
            return _final("dont_know", f"I found no {word} in the services model to move.")
        options = [{"label": f"{i.get('label')} ({i['id']})"[:60],
                    "message": f"Move {word} {i['id']}"} for i in items[:4]]  # fmt: skip
        evs = [str(i["ev"]) for i in items[:4] if i.get("ev")]
        return _final("needs_input", f"Several {word}s match. Which one?", evs, options=options)
    wall = WALL.search(words)
    if named is not None and not items and wall is None:  # never "in no room": it is not listed
        cut = " (the list was cut: name its wall too)" if found.get("more") else ""
        return _final("dont_know", f"{named} is not in the services list of {word}s{cut}.")
    element = items[0] if items else {"id": named}
    move: Json = {"drawing_id": drawing, "element_id": element["id"]}
    if wall:
        walls = [wall[0].upper()]
    else:
        room = element.get("room")
        if room is None:
            return _final("dont_know", f"{element['id']} is in no room of the model: name a wall.")
        walled = turn.result("list_services", room_id=room)
        if walled is None:
            return "list_services", {"drawing_id": drawing, "room_id": room}
        sides = [w for w in walled.get("walls") or [] if element["id"] not in w.get("mounted", [])]
        walls = [w["id"] for w in sorted(sides, key=lambda w: -(w.get("free_m") or 0))]
    tried = [(a, f) for n, a, f in turn.done if n == "propose_move_terminal"]
    made = next((f for _, f in tried if f.get("status") == "ok"), None)
    if made is not None:
        cited = [str(element["ev"])] if element.get("ev") else []
        return _services_edit(made, tried[-1][0]["wall_id"], cited)
    left = [w for w in walls if w not in {a.get("wall_id") for a, _ in tried}]
    if left and len(tried) < TRIED:
        return "propose_move_terminal", {**move, "wall_id": left[0]}
    why = next((f.get("reason") or f.get("error") for _, f in reversed(tried)), None)
    return _final("dont_know", f"I can't move it: {why or 'its room has no other wall'}")


def _services_edit(found: Json, wall: str, evidence: list[str]) -> tuple[str, Json]:
    """The proposal in words from its short view: what moves where, the facts before → after
    and every check that fails."""
    proposal = found["proposal"]
    moved = [f"{m['label']} ({m['id']})" for m in proposal.get("moved") or []]
    text = f"Proposed: move {' and '.join(moved) or 'it'} to wall {wall}."
    for fact in (proposal.get("facts") or [])[:4]:
        about = ", ".join(str(fact[k]) for k in ("system", "size") if fact.get(k))
        text += f" {fact['what']}{f' ({about})' if about else ''}: {fact['before']} → "
        text += f"{fact['after']} {fact['unit']}."
    text += "".join(f" {c['text']}" for c in proposal.get("checks") or [] if not c.get("ok"))
    text += "".join(f" {unknown}" for unknown in proposal.get("unknowns") or [])
    return _final("edit", text, evidence, proposal_id=proposal["proposal_id"])


def _ask_services(turn: _Turn, words: str, op: str) -> tuple[str, Json]:
    found = _services(turn, words)
    if isinstance(found, tuple):
        return found
    named, items = _picked(words, [i for i in found.get("items") or [] if isinstance(i, dict)])
    if named is None and len(items) != 1:
        if not items:
            return _final("dont_know", "Which element? Name it by its id from the services list.")
        ask = {"feeds": "What feeds {}?", "cut_off": "What is cut off if {} closes?",
               "terminals_served": "What does {} serve?"}[op]  # fmt: skip
        options = [{"label": f"{i.get('label')} ({i['id']})"[:60], "message": ask.format(i["id"])}
                   for i in items[:4]]  # fmt: skip
        evs = [str(i["ev"]) for i in items[:4] if i.get("ev")]
        return _final("needs_input", "Which one do you mean?", evs, options=options)
    element = named or items[0]["id"]
    answer = turn.result("ask_services")
    if answer is None:
        return "ask_services", {"drawing_id": found["drawing_id"], "op": op, "element_id": element}
    if "error" in answer or answer.get("status") != "ok":
        why = answer.get("reason") or answer.get("error") or "the model does not say"
        return _final("dont_know", f"I can't tell: {why}.")
    elements: list[Json] = [e for e in answer.get("elements") or [] if isinstance(e, dict)]
    cited = ", ".join(f"{e['id']} [{e['ev']}]" if e.get("ev") else e["id"] for e in elements[:10])
    if op == "feeds":
        text = f"{element} is fed by {cited}."
    elif op == "terminals_served":
        text = f"{element} serves {answer['value']} terminals: {cited}."
    else:
        text = (f"Closing {element} cuts off {answer['value']} elements, "
                f"{answer.get('terminals', 0)} of them terminals: {cited}.")  # fmt: skip
    evs = [str(e["ev"]) for e in elements[:10] if e.get("ev")]
    return _final("answer", text, evs)


# the parser's words for a measure it found without a room or element (app/core/review/ask.py)
NO_SUBJECT = "not which room or element"


def _refused_room(found: Json) -> bool:
    """Whether every drawing refused the question as one it can't parse or whose room it lacks
    (item 6: the drawings may still print a room by that name)."""
    parts: list[Json] = [p for p in found.get("parts") or [] if isinstance(p, dict)]
    answers: list[Json] = [p.get("answer") or {} for p in parts]
    if not answers or any(a.get("answer") is not None for a in answers):
        return False
    refusals: list[Json] = [a.get("refusal") or {} for a in answers]
    return all(_no_subject(r) for r in refusals)


def _no_subject(refusal: Json) -> bool:
    """A refusal that could not tell which room the question means: the type is not on the
    drawing, or the parser found a measure without a room or element (its own words)."""
    code, text = refusal.get("code"), str(refusal.get("text") or "")
    return code == "not-in-drawing" or (code == "unsupported-question" and NO_SUBJECT in text)


def _rooms(found: Json) -> tuple[str, Json] | None:
    """The printed rooms find_rooms gave: one is shown, several are asked about; None: none."""
    rooms: list[Json] = [r for r in found.get("rooms") or [] if isinstance(r, dict) and "ev" in r]
    count = found.get("count") or 0
    if found.get("status") != "ok" or not rooms:
        return None
    if count == 1:
        room = rooms[0]
        text = f"The drawings can't measure that as asked, but {room['label']} is printed here"
        return _final("answer", f"{text} [{room['ev']}].", [room["ev"]])
    options = [{"label": str(r["label"])[:60], "message": f"Where is {r['label']}?"[:300]}
               for r in rooms[:4]]  # fmt: skip
    cites = " ".join(f"[{r['ev']}]" for r in rooms[:4])
    some = f"; here are {len(options)}" if count > len(options) else ""
    text = f"The drawings print {count} rooms with that name{some}: which one do you mean? {cites}"
    return _final("needs_input", text, [str(r["ev"]) for r in rooms[:4]], options=options)


def _show(turn: _Turn) -> tuple[str, Json]:
    """The latest answer's marks on the plan (show_on_plan answer: latest), its card with them."""
    shown = turn.result("show_on_plan")
    if shown is None:
        return "show_on_plan", {"answer": "latest", "caption": ""}
    if shown.get("status") != "ok":
        why = str(shown.get("error") or "there is nothing to show").removeprefix("show_on_plan: ")
        return _final("dont_know", f"I can't show that on the plan: {why}.")
    return _final("answer", "Here they are on the plan.")


def _sure(turn: _Turn) -> tuple[str, Json]:
    """ "Are you sure?": the reviewed question, then per drawing its value, level and disputed
    marks, cited. "Yes" only when every drawing is High and none of its marks is disputed."""
    found = turn.result("review_answer")
    if found is None:
        return "review_answer", {}
    drawings: list[Json] = [d for d in found.get("drawings") or [] if isinstance(d, dict)]
    answered = [d for d in drawings if "answer" in d]
    if found.get("status") == "ok" and drawings and not answered:  # a refusal: it stands
        why = " ".join(f"{d['drawing']}: {d['refused']}" for d in drawings if d.get("refused"))
        return _final("answer", f"Yes: the last answer was a refusal, and it stands. {why}")
    if found.get("status") != "ok" or not answered:
        why = found.get("reason") or "the last answer had no number to check"
        return _final("dont_know", f"I can't check that: {why}.")
    lines: list[str] = []
    cited: list[str] = []
    for drawing in answered:
        unit = drawing.get("unit")
        value = f"{drawing['answer']}{f' {unit}' if unit and unit != 'count' else ''}"
        level = drawing.get("level_text") or f"Confidence: {drawing.get('level') or 'not given'}."
        disputed: list[Json] = [d for d in drawing.get("disputed") or [] if isinstance(d, dict)]
        evs = [str(d["ev"]) for d in disputed if d.get("ev")][: max(0, 4 - len(cited))]
        cited += evs
        count = drawing.get("disputed_count") or 0
        if count:
            noun = "marks is" if count == 1 else "marks are"
            doubt = f" {count} of its {noun} disputed by the other readers"
            doubt += ": " + " ".join(f"[{ev}]" for ev in evs) if evs else "."
        else:
            doubt = " No other reader disputes its marks."
        lines.append(f"{drawing['drawing']}: {value}. {level}{doubt}")
    sure = all(d.get("level") == "high" and not d.get("disputed_count") for d in answered)
    question = found.get("question")
    about = f'About "{question}": ' if question else ""
    offered = pushed(turn.message)
    ranged = [d["range"] for d in answered if d.get("range")]
    if offered is not None and ranged:  # never "Yes" to a number the drawings do not show
        low, high = ranged[0]
        where = "within" if low <= offered <= high else "outside"
        said = f"{offered:g} is {where} what the drawings show ({low} to {high})."
        if where == "outside":
            said += " A person counting on the plan would settle it."
        return _final("answer", f"{about}" + " ".join(lines) + f" {said}", cited)
    lead = "Yes, as far as the checks go." if sure else "Not for certain."
    return _final("answer", f"{about}{lead} " + " ".join(lines), cited)


def _law(turn: _Turn, offered: set[str]) -> tuple[str, Json]:
    """A law question: search the chosen country's clauses; the closest ones, cited by ref."""
    if turn.pack is None:
        return _final("dont_know", NO_PACK)
    if "search_law" not in offered:
        return _final(
            "dont_know", "I can't look up the building rules here: no law files are loaded."
        )
    found = turn.result("search_law")
    if found is None:
        return "search_law", {"pack": turn.pack, "query": turn.message[:500]}
    hits: list[Json] = [h for h in found.get("hits") or [] if isinstance(h, dict)]
    if not hits:
        why = found.get("error") or "no clause of the chosen country's rules matches the question"
        return _final("dont_know", f"I found no rule for that: {why}.")
    lines = [f"{h['ref']} of {h['title_en']}: {h['summary_en']}" for h in hits[:2]]
    return _final("answer", "The closest rules I found: " + " Also ".join(lines))


def _room_name(words: str) -> str:
    found = ROOM_WORD.search(words)
    return found[1].capitalize() if found else "New room"


def _remove_wall(turn: _Turn, words: str) -> tuple[str, Json]:
    proposed = turn.result("propose_remove_wall")
    walls_of = [(args, found) for name, args, found in turn.done if name == "list_walls"]
    if proposed is not None:
        wall = proposed_wall(turn)
        return _edit(proposed, [wall["ev"]] if wall and "ev" in wall else [])
    # the latest: a list_walls between the named rooms after a cut list (chat-eval 2026-11-14)
    ok = next(
        ((args, found) for args, found in reversed(walls_of) if found.get("status") == "ok"), None
    )
    if ok is not None:
        return _pick_wall(turn, words, *ok)
    drawings = turn.result("list_drawings")
    if drawings is None:
        return "list_drawings", {}
    if isinstance(drawings, dict):  # a cut list, as loop._for_model gives it
        drawings = drawings.get("items")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if isinstance(drawings, list):
        everything: list[Any] = drawings  # pyright: ignore[reportUnknownVariableType]
        drawings, named = _sheet(words, everything)
        if named and len(drawings) > 1:  # several sheets share the name the message gives
            options = [{"label": f"{d.get('title') or d.get('name')} ({d.get('name')})"[:60],
                        "message": f"{turn.message} on {d.get('name')}"[:300]}
                       for d in drawings[:4]]  # fmt: skip
            return _final("needs_input", "Several drawings have that name. Which one?",
                          options=options)  # fmt: skip
    if isinstance(drawings, list) and len(walls_of) < min(TRIED, len(drawings)):  # pyright: ignore[reportUnknownArgumentType]
        drawing = drawings[len(walls_of)]
        return "list_walls", {"drawing_id": drawing["drawing_id"], "page": 1}
    reason = next((f.get("reason") or f.get("error") for _, f in walls_of), None)
    return _final("dont_know", f"I can't edit this plan: {reason or 'there is no plan to edit'}.")


def _sheet(words: str, drawings: list[Any]) -> tuple[list[Any], bool]:
    """The drawings the message names best, by plain name ("Drawn plan 2") or file name
    without its extension: the longest name it holds wins ("floor 2" over "floor", review-361
    S1); else all of them, in order (multi: an edit of a named sheet went to the first drawing
    with walls). Several left: they share the longest name, and the planner asks which."""

    def named(drawing: Any) -> tuple[bool, int]:
        """(the message holds its whole file name, the longest of its names it holds): a file
        name ("b.pdf") beats a title two drawings share (review-361)."""
        if not isinstance(drawing, dict):
            return (False, 0)
        given: Json = drawing  # pyright: ignore[reportUnknownVariableType]
        whole = str(given.get("name") or "").lower()
        file = re.sub(r"\.[a-z0-9]+$", "", whole)
        names = [str(given.get("title") or "").lower(), file, re.sub(r"[_-]+", " ", file)]
        longest = max(
            len(name)
            if len(name) > 3 and re.search(rf"(?<![\w.]){re.escape(name)}(?![\w]|\.\d)", words)
            else 0
            for name in names
        )
        exact = re.search(rf"(?<![\w.]){re.escape(whole)}(?!\w)", words) if whole else None
        return (exact is not None, longest)

    best = max((named(d) for d in drawings), default=(False, 0))
    if best == (False, 0):
        return drawings, False
    return [d for d in drawings if named(d) == best], True


def proposed_wall(turn: _Turn) -> Json | None:
    for name, args, _ in reversed(turn.done):
        if name == "propose_remove_wall":
            found = turn.result("list_walls", drawing_id=args.get("drawing_id"))
            walls = found.get("walls", []) if isinstance(found, dict) else []
            return next((w for w in walls if w.get("id") == args.get("wall_id")), None)
    return None


def _pick_wall(turn: _Turn, words: str, args: Json, found: Json) -> tuple[str, Json]:
    walls: list[Json] = found.get("walls") or []
    rooms: list[Json] = found.get("rooms") or []
    named = {m.upper() for m in re.findall(r"\bw\d+\b", words)}
    chosen = [w for w in walls if w["id"] in named]
    if len(named) == 1 and not chosen and found.get("walls_more"):
        # the wall the message names was cut from the list: propose it by its id (multi, W36)
        place = {"drawing_id": args["drawing_id"], "page": args["page"]}
        return "propose_remove_wall", {**place, "wall_id": next(iter(named))}
    if not chosen:
        # each clicked room is its own group (edits-2); a word naming a room already clicked
        # ("this bathroom") narrows that group instead of adding one (edits-3)
        clicked = [{m} for line in turn.selections for m in re.findall(r"room (\S+)", line)]
        groups: list[set[str]] = []
        for group in clicked + [g for _, g in sorted(_named(words, rooms), key=lambda f: f[0])]:
            same = next((at for at, kept in enumerate(groups) if kept & group), None)
            if same is None:
                groups.append(group)
            else:
                groups[same] &= group
        groups = [group for group in groups if group]
        chosen = [w for w in walls if _between({r["id"] for r in w.get("rooms", [])}, groups)]
        sides = [next(iter(group)) for group in groups[:2] if len(group) == 1]
        if not chosen and found.get("walls_more") and len(sides) == len(groups[:2]) > 0:
            # the list was cut: ask for the walls of the named rooms only
            pair = dict(zip(("room_a", "room_b"), sides, strict=False))
            return "list_walls", {"drawing_id": args["drawing_id"], "page": args["page"], **pair}
    if len(chosen) == 1:
        place = {"drawing_id": args["drawing_id"], "page": args["page"]}
        return "propose_remove_wall", {**place, "wall_id": chosen[0]["id"]}
    if not chosen:
        return _final("dont_know", "I found no inside wall between those rooms on this plan.")
    options = [
        {"label": f"Wall {w['id']}: {_sides(w, ' / ')}"[:60],
         "message": f"Remove wall {w['id']} between {_sides(w, ' and ')}"[:300]}
        for w in chosen[:4]
    ]  # fmt: skip
    if len(options) == 1:
        options.append({"label": "None of these", "message": "None of these walls"})
    evidence = [w["ev"] for w in chosen[:4] if "ev" in w]
    return _final("needs_input", "Several walls match. Which one do you mean?", evidence,
                  options=options)  # fmt: skip


def _named(words: str, rooms: list[Json]) -> list[tuple[int, set[str]]]:
    """The rooms the message names, where it names them: by a room word (their type), or by
    their printed label ("Bagno 1.01"), its number ("1.01") or its first word when no other
    room shares it ("Stanza")."""
    found = [(m.start(), {r["id"] for r in rooms if r.get("type") == ROOM_WORDS[m[1]]})
             for m in ROOM_WORD.finditer(words)]  # fmt: skip
    labels = [str(room.get("label") or "").lower() for room in rooms]
    firsts = [label.split(" ")[0] for label in labels]
    for room, label, first in zip(rooms, labels, firsts, strict=True):
        numbers = [w for w in label.split(" ") if any(c.isdigit() for c in w)]
        unique = [first] if len(first) > 2 and firsts.count(first) == 1 else []
        for name in [label, *numbers, *unique]:
            # "1" is not read inside "1-3" or "1.01": a room number ends where its digits do
            at = (
                re.search(rf"(?<![\w.])(?<!\d-){re.escape(name)}(?![\w]|[.-]\d)", words)
                if name
                else None
            )
            if at:
                found.append((at.start(), {room["id"]}))
                break
    return found


def _between(sides: set[str], groups: list[set[str]]) -> bool:
    """Whether a wall with rooms `sides` separates the named rooms: one of each of two groups,
    or, with one group, one of it."""
    if len(groups) >= 2:
        a, b = groups[0], groups[1]
        return any(x != y for x in sides & a for y in sides & b)
    return bool(groups) and bool(sides & groups[0])


def _sides(wall: Json, joint: str) -> str:
    return joint.join(str(r.get("label") or r.get("id")) for r in wall.get("rooms", []))


def _edit(found: Json, evidence: list[str], more: str = "") -> tuple[str, Json]:
    if found.get("status") != "ok":
        why = found.get("reason") or found.get("error") or "the plan tool refused it"
        return _final("dont_know", f"I can't make that edit: {why}.")
    proposal = found["proposal"]
    changes = [
        f"{room['label']}: {room['area_before_m2']} → {room['area_after_m2']} m²"
        for room in proposal.get("rooms", [])
    ]
    removed = [item["label"] for item in proposal.get("removed", [])]
    text = "Proposed: " + "; ".join(changes) + "."
    if removed:
        text += " Removed: " + "; ".join(removed) + "."
    text += "".join(f" {unknown}" for unknown in proposal.get("unknowns", [])) + more
    if services := (found.get("services") or {}).get("text"):  # SERVICES_FOLLOW=on
        text += f" {services}"
    law: Json = found.get("law") or {}
    for finding in law.get("findings") or []:  # LC-8: name each rule the change newly breaks
        if finding.get("change") == "newly_fails" and finding.get("ev"):
            text += f" {finding['subject']} would not meet: {finding['title']} [{finding['ev']}]."
    return _final("edit", text, evidence, proposal_id=proposal["proposal_id"])


def dont_know(why: str) -> str:
    """The reason alone: the card heads it "I don't know" and labels the options (answers-7)."""
    return TRY_THESE.sub("", why).strip()


def _option(suggestion: Json) -> Json:
    """A refusal's suggested question as a chip; a room by its name ("Room 1.01")."""
    quantity = str(suggestion["quantity"])
    label = f"Room {quantity[len(ONE_ROOM) :]}" if quantity.startswith(ONE_ROOM) else None
    return {"label": (label or suggestion["label"])[:60], "message": suggestion["question"][:300]}


def _which(words: str) -> tuple[str, str, bool] | None:
    """A question comparing the drawings: (each drawing's question, what the answer names, whether
    the largest/most wins), or None. A room word after a size word ("the largest kitchen") is a
    room question, asked as said; "most"/"fewest" need a thing to count."""
    found = WHICH.search(words)
    if found is None:
        return None
    word = found["word"]
    what = re.sub(r"^\s*(?:the\s+)?|\s+$", "", found["what"])
    top = word in ("largest", "biggest", "most")
    said = BIGGER.get(word, word)
    if number := NUMBER_OF.match(what):
        things = number["things"]
        return f"How many {things}?", f"the {said} number of {things}", top
    if "area" in what:
        what = re.sub(r"^total\s+", "", what)
        return f"What is the total {what}?", f"the {said} {what}", top
    if word in BIGGER:
        if ROOM_WORD.search(what):
            return None
        return "What is the total floor area?", f"the {said} floor area", top
    if not what:
        return None
    return f"How many {what}?", f"the {word} {what}", top


def _compared(answered: list[Json], named: str, top: bool) -> tuple[str, Json]:
    """The drawing (or tied drawings) with the largest or smallest answer, cited."""
    given = [_metric(a) for a in answered if isinstance(a.get("answer"), (int, float))]
    if not given:
        return _final("dont_know", "No drawing gives a number for it.")
    units = sorted({str(a.get("unit")) for a in given})
    if len(units) > 1:
        return _final("dont_know", f"The drawings answer in different units ({', '.join(units)}).")
    best = (max if top else min)(a["answer"] for a in given)
    winners = [a for a in given if a["answer"] == best]
    named_all = [str(a["drawing"]) for a in winners]
    names = (
        named_all[0] if len(named_all) == 1 else f"{', '.join(named_all[:-1])} and {named_all[-1]}"
    )
    verb = "have" if len(winners) > 1 else "has"
    unit = SAID_UNIT.get(str(winners[0].get("unit")), "")
    evidence = [str(a["ev"]) for a in winners if a.get("ev")]
    cites = "".join(f"[{ev}]" for ev in evidence)
    text = f"{names} {verb} {named}: {best:g}{unit}{' ' + cites if cites else ''}."
    if len(given) == 1:
        text += " It is the only drawing that answers."
    return _final("answer", text, evidence)


def _metric(answered: Json) -> Json:
    """An `answered` line in metres: ft² and ft converted, rounded as the card shows them."""
    unit = str(answered.get("unit"))
    if unit not in METRIC:
        return answered
    metric, factor = METRIC[unit]
    return {**answered, "answer": round(answered["answer"] * factor, 2), "unit": metric}


def _answer(found: Json) -> tuple[str, Json]:
    if "error" in found:
        return _final("dont_know", f"I could not ask the drawings: {found['error']}")
    # a long result is cut for the model: its lists end in a "... N more" string (answers-4)
    parts: list[Json] = [p for p in found.get("parts") or [] if isinstance(p, dict)]
    answering = [p for p in parts if (p.get("answer") or {}).get("answer") is not None]
    if not answering:
        refusal: Json = (parts[0]["answer"].get("refusal") if parts else None) or {}
        why = refusal.get("text") or found.get("why_no_total") or "no drawing answers it"
        suggested: list[Json] = [s for s in refusal.get("can_answer") or [] if isinstance(s, dict)]
        options = [_option(suggestion) for suggestion in suggested[:4]]
        rooms = [s["quantity"] for s in suggested if s["quantity"].startswith(ONE_ROOM)]
        if (
            refusal.get("code") == "not-in-drawing"
            and len(options) >= 2
            and len(rooms) == len(suggested)
        ):  # several rooms of the type asked about: which one
            return _final("needs_input", dont_know(why), options=options)
        # A refusal's suggestions follow up the question only when it could not be parsed at all;
        # otherwise they are the drawing's generic questions, not answers to this one
        related = refusal.get("code") == "unsupported-question"
        more: Json = {"options": options} if options and related else {}
        return _final("dont_know", dont_know(why), **more)
    # The turn carries the ask_drawings result, shown in full under the text: one sentence that
    # cites each answering drawing's first mark. `answered` (the loop's) lists every one; `parts`
    # may be cut for the window (#466)
    listed: list[Json] = [a for a in found.get("answered") or [] if isinstance(a, dict)]
    firsts = [marks[0]["ev"] for p in answering[:12] if (marks := [
        m for m in p["answer"].get("marks", []) if isinstance(m, dict) and "ev" in m])]  # fmt: skip
    evidence = [str(a["ev"]) for a in listed if a.get("ev")][:12] or firsts
    cites = "".join(f"[{ev}]" for ev in evidence)
    # No count of drawings in the sentence: the card under it lists every drawing's value, and
    # a sentence that says "the drawing" or "the drawings" is wrong for some turn (#430).
    return _final("answer", f"The answer is below{' ' + cites if cites else ''}.", evidence)
