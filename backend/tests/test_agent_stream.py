"""The step stream (.agents/chat/contract.md C): the loop's events while a turn runs, and the
SSE framing of the stream route."""

import json
import queue
from typing import Any

from test_agent_loop import ASKED, Model, Tools, call, final, step, turn

from app.api.chat import PING, sse

Json = dict[str, Any]


def events(
    model: Model, tools: Tools | None = None, **more: Any
) -> tuple[list[tuple[str, Json]], Any]:
    got: list[tuple[str, Json]] = []
    done = turn(model, tools, emit=lambda kind, data: got.append((kind, data)), **more)
    return got, done


def test_a_turn_streams_its_steps_in_order_and_they_match_the_turn() -> None:
    model = Model(
        step(call("ask_drawings", question="how big is the bathroom")),
        final(text="The bathroom Bagno 1.01 is 7.56 m² [ev_1].", evidence_ids=["ev_1"]),
    )
    got, done = events(model)
    assert [kind for kind, _ in got] == [
        "turn", "thinking", "plan", "tool_call", "tool_result", "thinking", "checking"]  # fmt: skip
    assert got[0][1] == {"chat_id": done.chat_id, "turn": 1}
    assert got[1][1] == {"step": 1} and got[5][1] == {"step": 2}
    label = "Asked the drawings: how big is the bathroom"
    assert got[2][1] == {"step": 1, "calls": [{"n": 1, "tool": "ask_drawings", "label": label}]}
    assert got[3][1] == {"n": 1, "tool": "ask_drawings", "label": label}
    result = got[4][1]
    assert {k: v for k, v in result.items() if k != "summary"} == done.steps[0].model_dump()
    assert result["summary"] == "plan.pdf: 7.56 m2 (high)"  # server words, the tool's number
    assert got[6][1] == {"status": "ok", "reason": None}


def test_a_refused_answer_streams_a_retry_with_the_reason_in_plain_words() -> None:
    model = Model(
        step(call("ask_drawings", question="q")),
        final(text="It is 9.99 m²."),
        final(text="It is 7.56 m² [ev_1].", evidence_ids=["ev_1"], n=10),
    )
    got, _ = events(model)
    checks = [data for kind, data in got if kind == "checking"]
    assert checks == [
        {"status": "retry", "reason": "a number in the answer is not in the drawings' results"},
        {"status": "ok", "reason": None},
    ]


def test_show_on_plan_streams_the_view_as_it_happens() -> None:
    model = Model(
        step(call("ask_drawings", question="q")),
        step(call("show_on_plan", 2, evidence_ids=["ev_1"], caption="The bathroom")),
        final(text="Here."),
    )
    got, done = events(model)
    views = [data for kind, data in got if kind == "view"]
    assert views == [done.view.model_dump(mode="json")]
    [shown] = [
        data for kind, data in got if kind == "tool_result" and data["tool"] == "show_on_plan"
    ]
    assert shown["label"] == "Showed the bathroom on the plan"


def test_the_model_text_is_never_streamed() -> None:
    """Only server-written words: a reply's own content does not reach an event."""
    model = Model(
        step(call("ask_drawings", question="q"), content="I bet it is 99 m2"),
        final(text="It is 7.56 m² [ev_1].", evidence_ids=["ev_1"]),
    )
    got, _ = events(model)
    assert "99" not in json.dumps(got)


def test_a_failed_tool_streams_its_error_status() -> None:
    model = Model(step(call("get_takeoff", drawing_id="x")), final(kind="dont_know", text="No."))
    got, done = events(model, Tools(get_takeoff={"error": "no such drawing"}))
    [result] = [data for kind, data in got if kind == "tool_result"]
    assert result["status"] == "error" and result["summary"] == "no such drawing"
    assert done.steps[0].status == "error"


def test_sse_frames_events_pings_while_idle_and_ends_after_the_last_event() -> None:
    events_in: queue.Queue[tuple[str, Json] | None] = queue.Queue()
    frames = sse(events_in, ping_s=0.001)
    assert next(frames) == PING  # nothing yet
    events_in.put(("turn", {"chat_id": "c3f9a1b2c4d5", "turn": 1}))
    assert next(frames) == 'event: turn\ndata: {"chat_id":"c3f9a1b2c4d5","turn":1}\n\n'
    events_in.put(("answer", {"text": "é\nx"}))
    events_in.put(None)  # the turn is over
    assert next(frames) == 'event: answer\ndata: {"text":"é\\nx"}\n\n'
    assert list(frames) == []


_ = ASKED


def test_a_caption_is_streamed_only_once_checked() -> None:
    """The plan and tool_call of show_on_plan come before its caption is checked: plain words."""
    model = Model(
        step(call("ask_drawings", question="q")),
        step(call("show_on_plan", 2, evidence_ids=["ev_1"], caption="All 12 rooms on the plan")),
        final(text="Here."),
    )
    got, done = events(model)
    assert "12 rooms" not in json.dumps(got)
    calls = [data["label"] for kind, data in got if kind in ("tool_call", "tool_result")]
    assert calls[2:] == ["Showed places on the plan", "Showed 1 place on plan.pdf, page 1"]
    assert done.steps[-1].label == "Showed 1 place on plan.pdf, page 1"


def test_a_caption_that_names_the_plan_is_not_said_twice() -> None:
    model = Model(
        step(call("ask_drawings", question="q")),
        step(call("show_on_plan", 2, evidence_ids=["ev_1"], caption="The bathroom on the plan")),
        final(text="Here."),
    )
    _, done = events(model)
    assert done.steps[-1].label == "Showed the bathroom on the plan"
