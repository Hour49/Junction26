"""A step's tool calls run at the same time (bounded), and the turn reads exactly as if they had
run one after the other: steps, evidence ids, tool messages and events in call order
(pi-spike borrow, orchestrator 2026-11-14 20:44)."""

import json
import threading
from typing import Any

from test_agent_loop import ASKED, Model, Tools, call, final, step, turn

from app.core.agent.model import Caps

Json = dict[str, Any]
MARK = {"id": "m9", "page": 2, "box": [0.5, 0.5, 0.6, 0.6]}
OTHER = {"parts": [{"drawing_id": "fedcba9876543210", "name": "other.pdf",
                    "answer": {"answer": 3, "marks": [MARK]}}]}  # fmt: skip


class Together(Tools):
    """Tools whose calls each wait until `n` of them are running: they finish only when run at
    the same time (a sequential loop breaks the barrier)."""

    def __init__(self, n: int, **results: Any) -> None:
        super().__init__(**results)
        self.barrier = threading.Barrier(n, timeout=5)
        self.lock = threading.Lock()

    def run(self, name: str, arguments: str) -> str:
        self.barrier.wait()
        with self.lock:
            return super().run(name, arguments)


def test_the_calls_of_one_step_run_at_the_same_time_in_call_order() -> None:
    model = Model(
        step(call("ask_drawings", 1, question="bathroom"), call("get_takeoff", 2, drawing_id="x")),
        final(text="The bathroom is 7.56 m² [ev_1]; 3 [ev_2].", evidence_ids=["ev_1", "ev_2"]),
    )
    got: list[tuple[str, Json]] = []
    tools = Together(2, ask_drawings=ASKED, get_takeoff=OTHER)
    done = turn(model, tools, emit=lambda kind, data: got.append((kind, data)))
    assert done.kind == "answer"
    assert [s.tool for s in done.steps] == ["ask_drawings", "get_takeoff"]
    assert [(e.id, e.label) for e in done.evidence] == [("ev_1", "Bagno 1.01"), ("ev_2", "m9")]
    replies = [m for m in model.sent[1] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in replies] == ["c1", "c2"]
    order = [(kind, data["n"]) for kind, data in got if kind in ("tool_call", "tool_result")]
    assert order == [("tool_call", 1), ("tool_call", 2), ("tool_result", 1), ("tool_result", 2)]


def test_proposals_run_one_at_a_time() -> None:
    """Plan proposals number themselves in the chat: never two at once."""
    seen: list[str] = []

    class Alone(Tools):
        running = 0

        def run(self, name: str, arguments: str) -> str:
            Alone.running += 1
            seen.append(f"{name}:{Alone.running}")
            out = super().run(name, arguments)
            Alone.running -= 1
            return out

    model = Model(
        step(
            call("propose_remove_wall", 1, wall_id="W1"),
            call("propose_remove_wall", 2, wall_id="W2"),
        ),
        final(kind="dont_know", text="No."),
    )
    turn(model, Alone(propose_remove_wall={"status": "refused", "reason": "no"}))
    assert seen == ["propose_remove_wall:1", "propose_remove_wall:1"]


def test_parallel_one_runs_the_calls_one_after_the_other() -> None:
    model = Model(
        step(call("ask_drawings", 1, question="a"), call("ask_drawings", 2, question="b")),
        final(kind="dont_know", text="No."),
    )
    tools = Tools(ask_drawings=ASKED)
    turn(model, tools, caps=Caps(parallel=1))
    assert [json.loads(args)["question"] for _, args in tools.ran] == ["a", "b"]


def test_a_call_made_a_third_time_in_one_step_is_not_run() -> None:
    """Review 330 S1: the third identical call ends the turn, as one after the other."""
    same = [call("ask_drawings", n, question="same") for n in range(1, 4)]
    tools = Tools(ask_drawings=ASKED)
    done = turn(Model(step(*same), final(kind="dont_know", text="No.")), tools)
    assert len(tools.ran) == 2
    assert done.kind == "dont_know" and "repeating" in done.text


def test_at_most_parallel_calls_run_at_once() -> None:
    """Review 330 S2: 6 calls, cap 4: the first 4 meet at a barrier, so 4 run at once; they then
    wait a moment for a fifth, which over the cap would be running beside them."""

    class Peak(Together):
        def __init__(self, **results: Any) -> None:
            super().__init__(4, **results)
            self.now = self.most = 0
            self.fifth = threading.Event()

        def run(self, name: str, arguments: str) -> str:
            with self.lock:
                self.now += 1
                self.most = max(self.most, self.now)
            if json.loads(arguments)["question"] in "1234":
                self.barrier.wait()
                self.fifth.wait(0.2)
            else:
                self.fifth.set()
            with self.lock:
                self.now -= 1
                return Tools.run(self, name, arguments)

    calls = [call("ask_drawings", n, question=str(n)) for n in range(1, 7)]
    tools = Peak(ask_drawings=ASKED)
    turn(Model(step(*calls), final(kind="dont_know", text="No.")), tools,
         caps=Caps(calls_per_step=6, parallel=4))  # fmt: skip
    assert tools.most == 4 and len(tools.ran) == 6
