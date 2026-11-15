"""The no-keys planner (spec AC-11) on scripted tool results: its next call from the turn so far."""

import json
from typing import Any

from app.adapters.chat_rules import LOAD, NO_PACK, OTHER_AREAS, RulesChatModel
from app.core.agent.loop import NUDGE, UNBACKED

DRAWING = "0123456789abcdef"
TOOLS = [{"type": "function", "function": {"name": n}}
         for n in ("list_drawings", "ask_drawings", "list_walls", "propose_remove_wall",
                   "propose_room", "final_answer")]  # fmt: skip
WALLS = {
    "status": "ok", "drawing_id": DRAWING, "page": 1,
    "walls": [
        {"id": "W1", "ev": "ev_1",
         "rooms": [{"id": "r1", "label": "Bagno 1.01"}, {"id": "r2", "label": "Stanza 1.02"}]},
        {"id": "W2", "ev": "ev_2",
         "rooms": [{"id": "r1", "label": "Bagno 1.01"}, {"id": "r3", "label": "Bagno 1.03"}]},
    ],
    "rooms": [{"id": "r1", "label": "Bagno 1.01", "type": "bathroom"},
              {"id": "r2", "label": "Stanza 1.02", "type": "bedroom"},
              {"id": "r3", "label": "Bagno 1.03", "type": "bathroom"}],
}  # fmt: skip


def history(message: str, *done: tuple[str, dict[str, Any], Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": "..."},
                                 {"role": "user", "content": message}]  # fmt: skip
    for n, (name, args, result) in enumerate(done):
        call = {"id": f"c{n}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}}  # fmt: skip
        out.append({"role": "assistant", "tool_calls": [call]})
        out.append({"role": "tool", "tool_call_id": f"c{n}", "content": json.dumps(result)})
    return out


def plan(message: str, *done: tuple[str, dict[str, Any], Any]) -> tuple[str, dict[str, Any]]:
    reply = RulesChatModel().complete(history(message, *done), TOOLS)
    assert reply.usd == 0
    [call] = reply.message["tool_calls"]
    return call["function"]["name"], json.loads(call["function"]["arguments"])


def test_ac11_a_question_asks_the_drawings_then_answers_from_them() -> None:
    assert plan("How many doors?") == ("ask_drawings", {"question": "How many doors?"})
    asked = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf", "answer": {
        "answer": 2, "unit": "count", "quantity": {"noun": "doors"},
        "marks": [{"ev": "ev_1"}, {"ev": "ev_2"}]}}]}  # fmt: skip
    name, args = plan("How many doors?", ("ask_drawings", {}, asked))
    assert name == "final_answer"
    assert args == {"kind": "answer", "text": "The drawing answers this below [ev_1].",
                    "evidence_ids": ["ev_1"]}  # fmt: skip
    model = {"drawing_id": DRAWING, "name": "b.ifc", "answer": {"answer": 2, "marks": []}}
    asked["parts"].append(model)
    _, args = plan("How many doors?", ("ask_drawings", {}, asked))
    assert args["text"] == "The drawings answer this below [ev_1]."


def test_ac11_all_refused_is_dont_know_with_the_reason() -> None:
    asked = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf",
                        "answer": {"answer": None, "refusal": {"text": "No scale."}}}]}  # fmt: skip
    _, args = plan("How big?", ("ask_drawings", {}, asked))
    assert (args["kind"], args["text"]) == (
        "dont_know",
        "No scale.",
    )  # answers-7: no "I don't know:"
    assert "options" not in args


def test_generic_suggestions_are_not_options_for_another_refusal() -> None:
    can = [{"quantity": "door", "label": "door count", "question": "How many doors are there?"}]
    refusal = {"code": "not-in-drawing", "can_answer": can, "text": "No fire rating is drawn."}
    asked = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf",
                        "answer": {"answer": None, "refusal": refusal}}]}  # fmt: skip
    _, args = plan("What is the fire rating?", ("ask_drawings", {}, asked))
    assert args["kind"] == "dont_know" and "options" not in args


def test_ac11_several_rooms_of_the_type_asked_about_ask_which() -> None:
    rooms = [
        {
            "quantity": f"area:room|name={n}",
            "label": f"area of room (name {n})",
            "question": f"What is the net floor area of room {n}?",
        }
        for n in ("1.01", "1.09")
    ]
    refusal = {
        "code": "not-in-drawing",
        "can_answer": rooms,
        "text": "2 rooms on this drawing are of the type bathroom. Ask about one of them.",
    }
    asked = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf",
                        "answer": {"answer": None, "refusal": refusal}}]}  # fmt: skip
    _, args = plan("How big is the bathroom?", ("ask_drawings", {}, asked))
    assert (args["kind"], args["text"]) == ("needs_input", refusal["text"])
    assert args["options"] == [
        {"label": "Room 1.01", "message": "What is the net floor area of room 1.01?"},
        {"label": "Room 1.09", "message": "What is the net floor area of room 1.09?"},
    ]


def test_ac11_a_refusal_carries_its_suggestions_as_options() -> None:
    can = [{"quantity": "door", "label": "door count", "question": "How many doors are there?"}]
    refusal = {
        "code": "unsupported-question",
        "can_answer": can * 5,
        "text": "This question isn't one I can turn into a count. Try one of these instead.",
    }
    asked = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf",
                        "answer": {"answer": None, "refusal": refusal}}]}  # fmt: skip
    _, args = plan("How many parking spaces are there?", ("ask_drawings", {}, asked))
    # answers-7: the card heads it "I don't know" and labels the options itself
    assert (args["kind"], args["text"]) == (
        "dont_know",
        "This question isn't one I can turn into a count.",
    )
    assert args["options"] == [{"label": "door count", "message": "How many doors are there?"}] * 4


def test_ac11_load_bearing_is_dont_know() -> None:
    assert plan("Is that wall load-bearing?")[1]["text"] == LOAD


def test_ac11_remove_a_wall_between_two_named_rooms() -> None:
    message = "Remove the wall between the bathroom and the bedroom"
    assert plan(message)[0] == "list_drawings"
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    assert plan(message, drawings) == ("list_walls", {"drawing_id": DRAWING, "page": 1})
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, WALLS)
    proposed = ("propose_remove_wall", {"drawing_id": DRAWING, "page": 1, "wall_id": "W1"})
    assert plan(message, drawings, walls) == proposed
    proposal = {"status": "ok", "proposal": {
        "proposal_id": "p1", "removed": [{"label": "Wall W1"}], "unknowns": ["Load: unknown."],
        "rooms": [{"label": "Bagno 1.01 + Stanza 1.02", "area_before_m2": 20.66,
                   "area_after_m2": 21.0}]}}  # fmt: skip
    name, args = plan(message, drawings, walls, (*proposed, proposal))
    assert name == "final_answer" and args["kind"] == "edit" and args["proposal_id"] == "p1"
    assert args["evidence_ids"] == ["ev_1"] and "20.66 → 21.0 m²" in args["text"]


def test_ac11_rooms_named_by_label_or_number() -> None:
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, WALLS)
    for message in ("Remove the wall between Bagno 1.01 and Stanza 1.02",
                    "Remove the wall between 1.01 and 1.02", "Knock down the wall to the Stanza",
                    "Remove the wall between Bagno 1.01 and Bagno 1.03"):  # fmt: skip
        name, args = plan(message, drawings, walls)
        assert name == "propose_remove_wall", (message, args)
        assert args["wall_id"] == ("W2" if "1.03" in message else "W1")


def test_a_bare_room_number_is_not_read_inside_a_hyphenated_one() -> None:
    """DigitalHub ground floor (2026-11-15): "Küche 1-3" and "Fluchtflur West 1-20" named by
    their labels picked "Schacht West 1 301", whose number "1" matched the "1" of "1-3"."""
    walls = {
        "status": "ok", "drawing_id": DRAWING, "page": 1,
        "walls": [
            {"id": "W16", "rooms": [{"id": "r1", "label": "Treppenhaus West - EG 1-19"},
                                    {"id": "r2", "label": "Schacht West 1 301"}]},
            {"id": "W17", "rooms": [{"id": "r4", "label": "Fluchtflur West 1-20"},
                                    {"id": "r20", "label": "Küche 1-3"}]},
        ],
        "rooms": [{"id": "r1", "label": "Treppenhaus West - EG 1-19", "type": "other"},
                  {"id": "r2", "label": "Schacht West 1 301", "type": "shaft"},
                  {"id": "r4", "label": "Fluchtflur West 1-20", "type": "hall"},
                  {"id": "r20", "label": "Küche 1-3", "type": "kitchen"}],
    }  # fmt: skip
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    listed = ("list_walls", {"drawing_id": DRAWING, "page": 1}, walls)
    for message in ("Remove the wall between Küche 1-3 and Fluchtflur West 1-20",
                    "Remove the wall between 1-3 and 1-20"):  # fmt: skip
        assert plan(message, drawings, listed) == (
            "propose_remove_wall",
            {"drawing_id": DRAWING, "page": 1, "wall_id": "W17"},
        ), message
    assert plan("Remove the wall between Schacht West 1 and 1-19", drawings, listed)[1][
        "wall_id"] == "W16"  # fmt: skip


def test_a_bare_room_number_is_not_read_at_the_end_of_a_hyphenated_one() -> None:
    """DigitalHub ground floor: "Gruppenbüro 3 1-6" ends in "6", the number of "Gruppenbüro 6
    1-10", so the planner looked for a wall between the two offices instead of W3."""
    walls = {
        "status": "ok", "drawing_id": DRAWING, "page": 1,
        "walls": [
            {"id": "W2", "rooms": [{"id": "r2", "label": "Gruppenbüro 2 1-5"},
                                   {"id": "r3", "label": "Gruppenbüro 3 1-6"}]},
            {"id": "W3", "rooms": [{"id": "r3", "label": "Gruppenbüro 3 1-6"},
                                   {"id": "r7", "label": "Open Workspace EG 1-7"}]},
            {"id": "W6", "rooms": [{"id": "r6", "label": "Gruppenbüro 6 1-10"},
                                   {"id": "r5", "label": "Gruppenbüro 5 1-9"}]},
        ],
        "rooms": [{"id": f"r{n}", "label": label, "type": "other"}
                  for n, label in ((2, "Gruppenbüro 2 1-5"), (3, "Gruppenbüro 3 1-6"),
                                   (5, "Gruppenbüro 5 1-9"), (6, "Gruppenbüro 6 1-10"),
                                   (7, "Open Workspace EG 1-7"))],
    }  # fmt: skip
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    listed = ("list_walls", {"drawing_id": DRAWING, "page": 1}, walls)
    message = "Remove the wall between Gruppenbüro 3 1-6 and Open Workspace EG 1-7"
    assert plan(message, drawings, listed) == (
        "propose_remove_wall",
        {"drawing_id": DRAWING, "page": 1, "wall_id": "W3"},
    )


def test_ac11_several_matching_walls_ask_which() -> None:
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, WALLS)
    name, args = plan("Make the bathroom larger", drawings, walls)
    assert name == "final_answer" and args["kind"] == "needs_input"
    assert [o["message"] for o in args["options"]] == [
        "Remove wall W1 between Bagno 1.01 and Stanza 1.02",
        "Remove wall W2 between Bagno 1.01 and Bagno 1.03",
    ]
    assert plan("Remove wall W2 between Bagno 1.01 and Bagno 1.03", drawings, walls)[1][
        "wall_id"] == "W2"  # fmt: skip


def test_ac11_a_scan_cannot_be_edited() -> None:
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    scan = {"status": "cannot_edit", "reason": "this plan is a scan: its walls are not geometry"}
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, scan)
    _, args = plan("Remove the wall", drawings, walls)
    assert args["kind"] == "dont_know"
    assert (
        args["text"] == "I can't edit this plan: this plan is a scan: its walls are not geometry."
    )


def test_ac11_a_region_and_a_room_proposes_a_room() -> None:
    message = "Put a storage room here\nsel_1: region on a.pdf page 1, about 2 x 1 m"
    assert plan(message) == ("propose_room", {"selection_id": "sel_1", "name": "Storage"})


def test_a_refused_final_answer_ends_in_dont_know() -> None:
    refused = ("final_answer", {"kind": "answer", "text": "9"}, {"error": "numbers"})
    assert plan("How many doors?", refused)[1] == {"kind": "dont_know", "text": UNBACKED,
                                                  "evidence_ids": []}  # fmt: skip


def test_the_nudge_is_not_the_users_message() -> None:
    messages = [*history("How many doors?"), {"role": "user", "content": NUDGE}]
    reply = RulesChatModel().complete(messages, TOOLS)
    assert reply.message["tool_calls"][0]["function"]["name"] == "ask_drawings"


def test_answers_4_a_cut_answer_list_is_read_not_indexed() -> None:
    part = {"drawing_id": DRAWING, "name": "a.pdf",
            "answer": {"answer": 7.5, "marks": [{"ev": "ev_1"}, "... 2 more"]}}  # fmt: skip
    asked = {"parts": [part, "... 3 more"]}  # loop._cut's shape of a long result
    name, args = plan("What is the net floor area of room 1.01?", ("ask_drawings", {}, asked))
    assert (name, args["kind"], args["evidence_ids"]) == ("final_answer", "answer", ["ev_1"])
    cut = {"text": "No.", "can_answer": ["... 1 more"]}
    refused = {"parts": [{"drawing_id": DRAWING, "name": "a.pdf",
                          "answer": {"answer": None, "refusal": cut}}, "... 1 more"]}  # fmt: skip
    assert plan("How tall?", ("ask_drawings", {}, refused))[1]["kind"] == "dont_know"


def clicked(message: str, *refs: str) -> str:
    lines = [f"sel_{n}: room {ref} Room {ref} (9.00 m²) on Drawn plan 1 page 1"
             for n, ref in enumerate(refs, start=1)]  # fmt: skip
    return "\n".join([message, *lines])


WALLS3 = {**WALLS, "walls": [*WALLS["walls"], {"id": "W3", "ev": "ev_3", "rooms": [
    {"id": "r2", "label": "Stanza 1.02"}, {"id": "r4", "label": "Corridoio 1.04"}]}]}  # fmt: skip


def test_edits_2_two_clicked_rooms_pick_the_one_wall_between_them() -> None:
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, WALLS3)
    name, args = plan(clicked("Remove the wall between these rooms", "r1", "r2"), drawings, walls)
    assert (name, args["wall_id"]) == ("propose_remove_wall", "W1")


def test_edits_3_a_clicked_bathroom_bigger_offers_its_inside_walls() -> None:
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, WALLS3)
    name, args = plan(clicked("Make this bathroom bigger", "r1"), drawings, walls)
    assert (name, args["kind"]) == ("final_answer", "needs_input")
    assert [o["label"][:7] for o in args["options"]] == ["Wall W1", "Wall W2"]  # not W3


def test_edits_5_a_second_drawn_area_is_said_unused() -> None:
    message = "\n".join(["Put a storage room here", "sel_1: region on a.pdf page 1, about 2 x 1 m",
                         "sel_2: region on a.pdf page 1, about 1 x 1 m"])  # fmt: skip
    assert plan(message)[1]["selection_id"] == "sel_1"
    proposal = {"status": "ok", "proposal": {"proposal_id": "p1", "rooms": [
        {"label": "Storage", "area_before_m2": 0.0, "area_after_m2": 2.0}]}}  # fmt: skip
    _, args = plan(message, ("propose_room", {"selection_id": "sel_1"}, proposal))
    assert args["kind"] == "edit" and args["text"].endswith(OTHER_AREAS)


LAW_TOOLS = [*TOOLS, {"type": "function", "function": {"name": "search_law"}}]


def law_plan(message: str, system: str, *done: tuple[str, dict[str, Any], Any]) -> Any:
    messages = history(message, *done)
    messages[0]["content"] = system
    [call] = RulesChatModel().complete(messages, LAW_TOOLS).message["tool_calls"]
    return call["function"]["name"], json.loads(call["function"]["arguments"])


def test_answers_6_a_law_question_searches_the_chosen_countrys_rules() -> None:
    system = "... Country chosen: Finland (pack fi)."
    question = "How big must a bedroom be?"
    assert law_plan(question, system) == ("search_law", {"pack": "fi", "query": question})
    hit = {"id": "c1", "ref": "§ 4", "title_en": "Decree on dwellings", "summary_en": "A room is "
           "at least 7 m².", "url": "https://example.org"}  # fmt: skip
    name, args = law_plan(question, system, ("search_law", {}, {"hits": [hit]}))
    assert (name, args["kind"]) == ("final_answer", "answer")
    assert (
        args["text"]
        == "The closest rules I found: § 4 of Decree on dwellings: A room is at least 7 m²."
    )
    _, none = law_plan(question, system, ("search_law", {}, {"hits": []}))
    assert none["kind"] == "dont_know" and none["text"].startswith("I found no rule for that")


def test_answers_6_without_a_country_a_law_question_asks_for_one() -> None:
    _, args = law_plan("What is the minimum size of a bedroom?", "...")
    assert (args["kind"], args["text"]) == ("dont_know", NO_PACK)


def test_answers_7_8_a_refusal_with_no_options_does_not_point_at_any() -> None:
    text = "This question isn't one I can turn into a count. Try one of these instead."
    refusal = {"code": "unsupported-question", "can_answer": [], "text": text}
    asked = {"parts": [{"drawing_id": DRAWING, "name": "s.png",
                        "answer": {"answer": None, "refusal": refusal}}]}  # fmt: skip
    _, args = plan("What is the ceiling height?", ("ask_drawings", {}, asked))
    assert args == {"kind": "dont_know", "evidence_ids": [],
                    "text": "This question isn't one I can turn into a count."}  # fmt: skip


def test_multi_a_named_wall_cut_from_the_list_is_proposed_by_its_id() -> None:
    """'Remove wall W36' on a 43-wall plan: W36 was cut from the list the model reads."""
    drawings = ("list_drawings", {}, [{"drawing_id": DRAWING}])
    cut = {**WALLS, "walls_more": 41}
    walls = ("list_walls", {"drawing_id": DRAWING, "page": 1}, cut)
    proposed = ("propose_remove_wall", {"drawing_id": DRAWING, "page": 1, "wall_id": "W36"})
    assert plan("Remove wall W36", drawings, walls) == proposed
    # a whole list without it: no such wall, as before
    assert plan("Remove wall W36", drawings, ("list_walls", walls[1], WALLS))[1]["kind"] == (
        "dont_know"
    )


def test_multi_an_edit_goes_to_the_sheet_the_message_names() -> None:
    other = "fedcba9876543210"
    listed = [
        {"drawing_id": DRAWING, "name": "ground_floor.pdf", "title": "Drawn plan 1"},
        {"drawing_id": other, "name": "first_floor.pdf", "title": "Drawn plan 2"},
    ]
    drawings = ("list_drawings", {}, listed)
    for message in (
        "Remove the wall between the bathroom and the bedroom on Drawn plan 2",
        "Remove wall W1 on first_floor",
        "Remove wall W1 on the first floor plan",
    ):
        assert plan(message, drawings) == ("list_walls", {"drawing_id": other, "page": 1}), message
    assert plan("Remove wall W1", drawings) == ("list_walls", {"drawing_id": DRAWING, "page": 1})
    # "Drawn plan 1" is not "Drawn plan 12"
    many = [*listed, {"drawing_id": "1" * 16, "name": "x.pdf", "title": "Drawn plan 12"}]
    found = plan("Remove wall W1 on Drawn plan 12", ("list_drawings", {}, many))
    assert found == ("list_walls", {"drawing_id": "1" * 16, "page": 1})


def test_multi_a_room_type_word_places_a_room_in_a_drawn_area() -> None:
    area = "\nsel_1: region on a.pdf page 1, about 2 x 1 m"
    assert plan("Put a toilet here" + area) == (
        "propose_room", {"selection_id": "sel_1", "name": "Toilet"})  # fmt: skip
    assert plan("Make this a kitchen" + area)[1]["name"] == "Kitchen"
    # a question about a drawn area is still a question
    assert plan("How big is the bathroom here?" + area)[0] == "ask_drawings"


def test_review_361_s1_the_longest_name_wins_and_a_tie_asks() -> None:
    other = "fedcba9876543210"
    listed = [{"drawing_id": DRAWING, "name": "plan.pdf", "title": "Drawn plan 1"},
              {"drawing_id": other, "name": "second.pdf", "title": "Drawn plan 2"}]  # fmt: skip
    found = plan("Remove wall W1 on Drawn plan 2", ("list_drawings", {}, listed))
    assert found == ("list_walls", {"drawing_id": other, "page": 1})
    floors = [
        {"drawing_id": DRAWING, "name": "floor.pdf"},
        {"drawing_id": other, "name": "floor_2.pdf"},
    ]
    assert plan("Remove wall W1 on floor 2", ("list_drawings", {}, floors)) == (
        "list_walls", {"drawing_id": other, "page": 1})  # fmt: skip
    twins = [{"drawing_id": DRAWING, "name": "a.pdf", "title": "Ground floor"},
             {"drawing_id": other, "name": "b.pdf", "title": "Ground floor"}]  # fmt: skip
    name, args = plan("Remove wall W1 on the ground floor", ("list_drawings", {}, twins))
    assert name == "final_answer" and args["kind"] == "needs_input" and len(args["options"]) == 2


def test_review_361_s2_a_question_about_a_drawn_area_places_no_room() -> None:
    area = "\nsel_1: region on a.pdf page 1, about 2 x 1 m"
    for message in ("Is this toilet new?", "Is this a good place for a kitchen?"):
        assert plan(message + area)[0] == "ask_drawings", message
    assert plan("Please place a kitchen here" + area)[0] == "propose_room"


def test_review_361_must_a_tie_offers_each_file_and_picking_one_edits_it() -> None:
    other = "fedcba9876543210"
    twins = [{"drawing_id": DRAWING, "name": "a.pdf", "title": "Ground floor"},
             {"drawing_id": other, "name": "b.pdf", "title": "Ground floor"}]  # fmt: skip
    _, args = plan("Remove wall W1 on the ground floor", ("list_drawings", {}, twins))
    labels = [o["label"] for o in args["options"]]
    assert labels == ["Ground floor (a.pdf)", "Ground floor (b.pdf)"]
    picked = args["options"][1]["message"]
    assert plan(picked, ("list_drawings", {}, twins)) == (
        "list_walls", {"drawing_id": other, "page": 1})  # fmt: skip


def test_which_drawing_has_the_largest_asks_each_drawing_then_names_the_top_one() -> None:
    """qa-a demo walk: the drawings answer one drawing at a time, so the comparison is asked as
    each drawing's total and the planner names the top one from the loop's `answered` list
    (every drawing that answered, though `parts` is cut for the window)."""
    message = "Which drawing has the largest floor area?"
    assert plan(message) == ("ask_drawings", {"question": "What is the total floor area?"})
    assert plan("Which plan has the most doors?")[1] == {"question": "How many doors?"}
    assert plan("Which sheet is the biggest?")[1] == {"question": "What is the total floor area?"}
    cut = {"drawing_id": DRAWING, "name": "a.pdf", "answer": {"answer": 52.27, "unit": "m2"}}
    asked = {"answered": [{"drawing": "a.pdf", "answer": 52.27, "unit": "m2", "ev": "ev_1"},
                          {"drawing": "b.pdf", "answer": 53.0, "unit": "m2", "ev": "ev_4"},
                          {"drawing": "c.pdf", "answer": 20.66, "unit": "m2", "ev": "ev_7"}],
             "parts": [cut], "parts_more": 3}  # fmt: skip
    assert plan(message, ("ask_drawings", {}, asked)) == ("final_answer", {
        "kind": "answer", "text": "b.pdf has the largest floor area: 53 m² [ev_4].",
        "evidence_ids": ["ev_4"]})  # fmt: skip
    _, args = plan("Which drawing has the smallest floor area?", ("ask_drawings", {}, asked))
    assert args["text"] == "c.pdf has the smallest floor area: 20.66 m² [ev_7]."
    doors = {"answered": [
        {"drawing": "a.pdf", "answer": 3, "unit": "count", "ev": "ev_1"},
        {"drawing": "b.pdf", "answer": 3, "unit": "count", "ev": "ev_5"}]}  # fmt: skip
    _, args = plan("Which plan has the most doors?", ("ask_drawings", {}, doors))
    assert args["text"] == "a.pdf and b.pdf have the most doors: 3 [ev_1][ev_5]."
    one = {"answered": doors["answered"][:1], "parts": []}
    _, args = plan("Which plan has the most doors?", ("ask_drawings", {}, one))
    assert (
        args["text"] == "a.pdf has the most doors: 3 [ev_1]. It is the only drawing that answers."
    )


def test_which_drawing_no_drawing_answers_is_the_refusal() -> None:
    refused = {"parts": [{
        "drawing_id": DRAWING, "name": "a.pdf",
        "answer": {"answer": None, "refusal": {"text": "No scale."}}}]}  # fmt: skip
    _, args = plan("Which drawing has the largest floor area?", ("ask_drawings", {}, refused))
    assert (args["kind"], args["text"]) == ("dont_know", "No scale.")


def test_which_drawing_has_the_largest_room_is_not_a_drawing_total() -> None:
    """A room word after 'largest' is a room question, not each drawing's total: asked as said."""
    message = "Which drawing has the largest kitchen?"
    assert plan(message) == ("ask_drawings", {"question": message})
