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
# A doubt about the last answer (item 3): answered from its review, not by asking again
SURE = re.compile(
    r"\b(are you sure|you sure|double[- ]?check|how (sure|certain|confident))\b|really\?"
)
ROOM = re.compile(r"\broom\b")
# A word for a room, as Room.type names it
ROOM_WORDS = {
    "bathroom": "bathroom", "bath": "bathroom", "washroom": "bathroom", "shower": "bathroom",
    "toilet": "wc", "wc": "wc", "bedroom": "bedroom", "kitchen": "kitchen", "living": "living",
    "lounge": "living", "hall": "hall", "hallway": "hall", "corridor": "hall", "entrance": "hall",
    "storage": "storage", "closet": "storage", "sauna": "sauna", "balcony": "balcony",
}  # fmt: skip
ROOM_WORD = re.compile(r"\b(" + "|".join(ROOM_WORDS) + r")s?\b")
LOAD = (
    "These drawings do not say which walls carry load. A structural drawing, a building model "
    "that marks load-bearing walls, or a structural engineer would settle it."
)
OTHER_AREAS = " I used the first area you drew, not the second: ask again for that one."
TRY_THESE = re.compile(r"\s*Try one of these instead\.?")  # the card labels its own options
ONE_ROOM = "area:room|name="  # a suggestion about one room, by its printed name
TRIED = 3  # drawings tried for an editable plan before giving up


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
    # a drawn area, or a sideways drag described as "a line ..., not an area" (QA robust-10):
    # propose_room gives the true reason for that one
    regions = [line.split(":")[0] for line in turn.selections if REGION.search(line)]
    if regions and ROOM.search(words) and "propose_room" in offered:
        found = turn.result("propose_room")
        if found is None:
            return "propose_room", {"selection_id": regions[0], "name": _room_name(words)}
        return _edit(found, [], OTHER_AREAS if len(regions) > 1 else "")  # edits-5
    if EDIT.search(words) and "list_walls" in offered:
        return _remove_wall(turn, words)
    if LAW.search(words):
        return _law(turn, offered)
    if SURE.search(words) and "review_answer" in offered:
        return _sure(turn)
    found = turn.result("ask_drawings")
    if found is None:
        return "ask_drawings", {"question": turn.message[:500]}
    return _answer(found)


def _sure(turn: _Turn) -> tuple[str, Json]:
    """ "Are you sure?": the last answer's level, why, and its disputed marks, cited."""
    found = turn.result("review_answer")
    if found is None:
        return "review_answer", {}
    drawings: list[Json] = [d for d in found.get("drawings") or [] if isinstance(d, dict)]
    answered = [d for d in drawings if "answer" in d]
    if found.get("status") != "ok" or not answered:
        why = found.get("reason") or "the last answer had no number to check"
        return _final("dont_know", f"I can't check that: {why}.")
    first = answered[0]
    unit = first.get("unit")
    value = f"{first['answer']}{f' {unit}' if unit and unit != 'count' else ''}"
    level = first.get("level_text") or f"Confidence: {first.get('level') or 'not given'}."
    disputed: list[Json] = [d for d in first.get("disputed") or [] if isinstance(d, dict)]
    cited = [str(d["ev"]) for d in disputed[:4] if d.get("ev")]
    count = first.get("disputed_count") or 0
    if count:
        noun = "mark is" if count == 1 else "marks are"
        doubt = f" {count} of its {noun} disputed by the other readers: " + " ".join(
            f"[{ev}]" for ev in cited
        )
    else:
        doubt = " No other reader disputes its marks."
    return _final("answer", f"Not for certain. {first['drawing']}: {value}. {level}{doubt}", cited)


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
    if isinstance(drawings, list) and len(walls_of) < min(TRIED, len(drawings)):  # pyright: ignore[reportUnknownArgumentType]
        drawing = drawings[len(walls_of)]
        return "list_walls", {"drawing_id": drawing["drawing_id"], "page": 1}
    reason = next((f.get("reason") or f.get("error") for _, f in walls_of), None)
    return _final("dont_know", f"I can't edit this plan: {reason or 'there is no plan to edit'}.")


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
            at = re.search(rf"(?<![\w.]){re.escape(name)}(?![\w]|\.\d)", words) if name else None
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
    # cites each answering drawing's first mark
    evidence = [marks[0]["ev"] for p in answering[:12] if (marks := [
        m for m in p["answer"].get("marks", []) if isinstance(m, dict) and "ev" in m])]  # fmt: skip
    cites = "".join(f"[{ev}]" for ev in evidence)
    them = "drawings answer" if len(answering) > 1 else "drawing answers"
    return _final("answer", f"The {them} this below{' ' + cites if cites else ''}.", evidence)
