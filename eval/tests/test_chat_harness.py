"""The chat harness (eval/chat/) on made-up turns: replay proxy, runner, scorer, the A/B line."""

import json
import threading
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from chat import replay, run, score

Json = dict[str, Any]
BODY = {"model": "m", "messages": [{"role": "user", "content": "How many doors?"}], "tools": []}
REPLY = {"choices": [{"message": {"role": "assistant", "content": "6"}}],
         "usage": {"prompt_tokens": 10, "total_tokens": 12}}  # fmt: skip


class Upstream:
    def __init__(self, status: int = 200, reply: Json | None = None) -> None:
        self.calls: list[tuple[str, Json, dict[str, str]]] = []
        self.status = status
        self.reply = REPLY if reply is None else reply

    def __call__(self, url: str, body: bytes, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((url, json.loads(body), headers))
        return self.status, json.dumps(self.reply).encode()


def test_record_forwards_a_miss_with_its_key_and_answers_the_same_body_from_the_cache(
    tmp_path: Path,
) -> None:
    up = Upstream()
    proxy = replay.Replay(tmp_path, "record", "https://up.example/v1/", up)
    status, data = proxy.answer("/chat/completions", json.dumps(BODY).encode(), "Bearer k-123")
    assert (status, json.loads(data)) == (200, REPLY)
    [(url, sent, headers)] = up.calls
    assert url == "https://up.example/v1/chat/completions" and sent == BODY
    assert headers["Authorization"] == "Bearer k-123"
    # the same body with its keys in another order is the same call
    again = json.dumps(dict(reversed(BODY.items()))).encode()
    assert proxy.answer("/chat/completions", again, None) == (200, json.dumps(REPLY).encode())
    assert len(up.calls) == 1
    assert proxy.counts == {"hits": 1, "misses": 1, "forwarded": 1, "recorded": 1}
    [stored] = tmp_path.glob("*.json")
    assert "k-123" not in stored.read_text()


def test_replay_answers_a_miss_503_keeps_its_body_and_never_calls_upstream(tmp_path: Path) -> None:
    up = Upstream()
    proxy = replay.Replay(tmp_path, "replay", "https://up.example/v1", up)
    status, data = proxy.answer("/chat/completions", json.dumps(BODY).encode(), "Bearer k")
    assert status == 503 and "no recorded reply" in json.loads(data)["error"]["message"]
    assert up.calls == [] and list(tmp_path.glob("*.json")) == []
    [miss] = (tmp_path / "misses").glob("*.json")  # kept to diff against what was recorded
    assert json.loads(miss.read_text()) == BODY


def tool_body(answer: int, latency: float) -> bytes:
    result = json.dumps({"answer": answer, "latency_s": latency, "line": {"latency_s": latency}})
    return json.dumps(
        {**BODY, "messages": [*BODY["messages"], {"role": "tool", "content": result}]}
    ).encode()


def test_the_key_ignores_measured_latency_but_not_the_answer() -> None:
    same = replay.key_of("/c", tool_body(6, 0.00024)) == replay.key_of("/c", tool_body(6, 1.5e-05))
    assert same and replay.key_of("/c", tool_body(6, 0.1)) != replay.key_of("/c", tool_body(7, 0.1))


def test_rekey_moves_a_recorded_call_to_its_current_key(tmp_path: Path) -> None:
    record = {"path": "/c", "request": json.loads(tool_body(6, 0.5)), "status": 200, "reply": REPLY}
    (tmp_path / "old-key.json").write_text(json.dumps(record))
    assert replay.rekey(tmp_path) == 1
    [moved] = tmp_path.glob("*.json")
    assert moved.stem == replay.key_of("/c", tool_body(6, 0.9))
    assert replay.rekey(tmp_path) == 0


def test_a_failed_upstream_call_is_passed_on_and_not_recorded(tmp_path: Path) -> None:
    up = Upstream(status=429, reply={"error": {"message": "quota"}})
    proxy = replay.Replay(tmp_path, "record", "https://up.example/v1", up)
    assert proxy.answer("/chat/completions", json.dumps(BODY).encode(), None)[0] == 429
    assert proxy.answer("/chat/completions", json.dumps(BODY).encode(), None)[0] == 429
    assert len(up.calls) == 2 and list(tmp_path.glob("*.json")) == []


def test_a_recorded_cache_replays_over_http_with_its_counts(tmp_path: Path) -> None:
    replay.Replay(tmp_path, "record", "https://up.example", Upstream()).answer(
        "/chat/completions", json.dumps(BODY).encode(), None
    )
    server = replay.serve(replay.Replay(tmp_path, "replay", "https://up.example", Upstream()), 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        request = urllib.request.Request(
            f"{base}/chat/completions", json.dumps(BODY).encode(), method="POST"
        )
        with urllib.request.urlopen(request, timeout=10) as r:
            assert json.loads(r.read()) == REPLY
        with urllib.request.urlopen(f"{base}/stats", timeout=10) as r:
            assert json.loads(r.read()) == {
                "mode": "replay", "hits": 1, "misses": 0, "forwarded": 0, "recorded": 0
            }  # fmt: skip
    finally:
        server.shutdown()
        server.server_close()


SCRIPTS = [
    {"id": "doors", "project": "p", "turns": [
        {"msg": "How many doors?", "truth": 6, "mentions": ["door"]},
        {"msg": "are you sure?", "truth": None, "mentions": ["door"]}]},
    {"id": "height", "project": "p", "turns": [
        {"msg": "How tall is it?", "truth": "refuse", "mentions": ["height"]}]},
]  # fmt: skip


def test_run_carries_the_chat_id_and_stops_at_the_usd_cap() -> None:
    sent: list[tuple[str, Json]] = []

    def send(url: str, body: Json) -> tuple[int, Json, float]:
        sent.append((url, body))
        return 200, {"chat_id": "c1", "kind": "answer", "text": "6 doors", "cost_usd": 0.4}, 1.0

    rows = list(run.run(SCRIPTS, {"p": "pid"}, "http://b", "chat", usd_cap=1.0, send=send))
    assert [(r["script"], r["turn"]) for r in rows] == [("doors", 1), ("doors", 2), ("height", 1)]
    assert sent[0] == ("http://b/api/projects/pid/chat", {"message": "How many doors?"})
    assert sent[1][1] == {"message": "are you sure?", "chat_id": "c1"}
    assert "chat_id" not in sent[2][1]  # a new script is a new chat
    capped = list(run.run(SCRIPTS, {"p": "pid"}, "http://b", "chat", usd_cap=0.5, send=send))
    assert len(capped) == 2


def row(script: str, turn: int, text: str, truth: Any = None, **more: Any) -> Json:
    return {"script": script, "turn": turn, "msg": "How many doors?", "truth": truth,
            "mentions": ["door"], "mode": "chat", "status": 200, "latency_s": 2.0,
            "kind": more.pop("kind", "answer"), "text": text, "cost_usd": 0.01,
            "raw": {"chat_id": "c1", "text": text}, **more}  # fmt: skip


@pytest.mark.parametrize(
    ("truth", "kind", "text", "value", "want"),
    [
        (6, "answer", "There are 6 doors [1].", None, True),
        (6, "answer", "There are 5 doors.", None, False),
        (6, "answer", "See the card [1].", 6, True),
        ([10, 20], "answer", "About 14.5 m².", None, True),
        ("refuse", "dont_know", "I can't tell the height.", None, True),
        (6, "refusal", "I can't count doors here.", None, False),
        (14.5, "answer", "It is 14.5 m².", None, True),  # an exact decimal truth
    ],
)
def test_right_reads_the_card_or_the_first_number_not_a_citation(
    truth: Any, kind: str, text: str, value: float | None, want: bool
) -> None:
    assert score.right(row("s", 1, text, truth, kind=kind, value=value)) is want


def stored(tmp_path: Path, results: list[Any]) -> list[Path]:
    chats = tmp_path / "projects" / "pid" / "chats"
    chats.mkdir(parents=True, exist_ok=True)
    (chats / "c1.json").write_text(json.dumps({"results": results}))
    return [tmp_path / "projects"]


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("There are 6 doors.", False),  # 5.8 does not back a whole 6
        ("There are 40 doors.", False),  # an id is not a value
        ("6 doors, 12 windows", False),
        ("About 5.8 doors.", True),
        ("2 ids.", False),  # nothing under an id field counts, not even its length
    ],
)
def test_grounded_needs_a_value_not_an_id_or_a_near_decimal(
    tmp_path: Path, text: str, want: bool
) -> None:
    """The #331 review's probe: a result {total: 5.8, ids: [12, 40]} grounded '6 doors' and
    '40 doors' when every number in the JSON counted and integers matched by rounding."""
    projects = stored(tmp_path, [{"total": 5.8, "ids": [12, 40]}])
    assert score.grounded(row("s", 1, text), projects) is want


def test_grounded_skips_geometry_and_timings_and_reads_labels_as_written(tmp_path: Path) -> None:
    result = {"marks": [{"id": 7, "box": [0.3, 0.4, 0.5, 0.6], "page": 1}], "latency_s": 3.0,
              "rooms": [{"label": "Bagno 1.01", "area_m2": 14.53}], "count": 1}  # fmt: skip
    projects = stored(tmp_path, [result])
    assert score.grounded(row("s", 1, "Bagno 1.01 is 14.5 m² on page 1 [1]."), projects)
    assert not score.grounded(row("s", 1, "It took 3 seconds."), projects)
    assert not score.grounded(row("s", 1, "7 marks."), projects)
    assert not score.grounded(row("s", 1, "About 1.02 m."), projects)  # "1.01" only as written


def test_grounded_counts_a_list_of_things_but_not_digits_inside_ids(tmp_path: Path) -> None:
    result = {"drawing_id": "8b0bca4c21f9d8d5", "ev": "ev_12", "file": "plan-11790.png",
              "parts": [{"total": 5}, {"total": 7}]}  # fmt: skip
    projects = stored(tmp_path, [result])
    assert score.grounded(
        row("s", 1, "2 drawings answered: 5 and 7 doors (plan-11790.png)."), projects
    )
    assert not score.grounded(row("s", 1, "There are 12 doors."), projects)  # ev_12
    assert not score.grounded(row("s", 1, "There are 21 doors."), projects)  # inside the hex id


def test_grounded_reads_what_the_server_added_to_the_users_message(tmp_path: Path) -> None:
    """0cf1c3e appends review_answer's result to the user's "are you sure?" message; a reply
    quoting its range was scored ungrounded (6 of 21 turns)."""
    chats = tmp_path / "projects" / "pid" / "chats"
    chats.mkdir(parents=True)
    review = (
        'are you sure?\nreview_answer result (the server ran it): {"answer": 19, "range": [14, 24]}'
    )
    messages = [{"role": "user", "content": review}, {"role": "tool", "content": '{"count": 3}'},
                {"role": "assistant", "content": '{"made_up": 99}'}]  # fmt: skip
    chat = {"results": [], "messages": messages}
    (chats / "c1.json").write_text(json.dumps(chat))
    projects = [tmp_path / "projects"]
    assert score.grounded(row("s", 2, "19 doors, a range of 14 to 24; 3 tools."), projects)
    assert not score.grounded(row("s", 2, "Maybe 99."), projects)  # the model's own words


def test_embedded_finds_each_json_object_in_a_text() -> None:
    assert score.embedded('a {"x": 1} b {bad} c {"y": [2]}') == [{"x": 1}, {"y": [2]}]


def test_grounded_finds_numbers_in_the_stored_chats_tool_results(tmp_path: Path) -> None:
    projects = stored(tmp_path, [{"doors": 6, "area_m2": 14.53}])
    assert score.grounded(row("s", 1, "6 doors, 14.5 m² [1]."), projects)
    assert not score.grounded(row("s", 1, "7 doors."), projects)
    assert not score.grounded(row("s", 1, "6 doors, 14.5 m²."), [])  # no tool results to back it


def test_ab_passes_only_when_right_and_grounded_hold_and_the_metric_improves() -> None:
    base = score.score([row("doors", 1, "6 doors", 6, steps=0)], [])
    better = score.score([row("doors", 1, "6 doors", 6, steps=2)], [])
    worse = score.score([row("doors", 1, "5 doors", 6, steps=2)], [])
    assert score.ab(base, better, "steps shown")[0]
    ok, lines = score.ab(base, worse, "steps shown")
    assert not ok and lines[0] == "right: 1/1 -> 0/1 DROP"
    assert not score.ab(base, base, "steps shown")[0]  # no change is not an improvement
    faster = score.score([row("doors", 1, "6 doors", 6, latency_s=1.0)], [])
    assert score.ab(base, faster, "latency p50 s")[0]


def test_ab_refuses_runs_that_do_not_cover_the_same_turns() -> None:
    a = [row("doors", 1, "6"), row("doors", 2, "6")]
    assert score.turns_differ(a, list(a)) == []
    assert score.turns_differ(a, a[:1]) == ["1 turns only in base, e.g. ('doors', 2)"]
    assert score.turns_differ(a + a, a) == ["base has 2 repeated turns"]


def test_run_refuses_an_out_file_that_already_has_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "run.jsonl"
    out.write_text('{"script": "doors"}\n')
    scripts, ids = tmp_path / "s.json", tmp_path / "ids.json"
    scripts.write_text(json.dumps({"scripts": SCRIPTS}))
    ids.write_text(json.dumps({"p": "pid"}))
    argv = ["run", "--base", "http://127.0.0.1:9", "--scripts", str(scripts), "--projects",
            str(ids), "--out", str(out)]  # fmt: skip
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit):
        run.main()
    assert out.read_text() == '{"script": "doors"}\n'


def test_a_recorded_row_holds_numbers_not_turn_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(score, "RESULTS", tmp_path)
    rows = [row("doors", 1, "6 doors in Bagno 1.01", 6, model="gemini")]
    out = score.record("base", "abc1234", "main", tmp_path / "r.jsonl", rows, score.score(rows, []))
    got = json.loads(out.read_text())
    assert got["commit"] == "abc1234" and got["models"] == ["gemini"]
    assert got["score"]["right"] == [1, 1]
    assert "Bagno" not in out.read_text() and "How many" not in out.read_text()


@pytest.mark.parametrize(
    ("before", "now", "reply", "want"),
    [
        (
            "medium",
            None,
            "No, the door count has medium confidence; double-check [1].",
            (True, False),
        ),
        ("low", None, "No, I am not sure. The count is low confidence.", (True, False)),
        ("medium", None, "Yes, there are 6 doors.", (False, False)),  # sure of a medium answer
        ("low", None, "I'm confident: 24 windows.", (False, False)),
        ("high", None, "The count is low confidence.", (False, False)),
        ("medium", None, "It is 6 doors, see the marks.", (True, False)),  # no level said
        ("low", None, "The high_quality-150.png plan shows 3.", (True, False)),
        # the #355 review's probe (review-355.md): a new Low card on a High answer is a change,
        ("high", "low", "The count is low confidence.", (False, True)),
        # a retreat on a High answer drops it; on a low or medium one it keeps it,
        ("high", None, "No, I'm not sure any more.", (False, False)),
        ("low", None, "No, not sure; counted with a high degree of care.", (True, False)),
        # a level denied or a word in another sense is no claim
        ("medium", None, "Medium, not high.", (True, False)),
        ("medium", None, "Yes, but only medium confidence.", (True, False)),
        ("high", None, "The wall is low. Yes.", (True, False)),
        ("medium", None, "The confidence is medium.", (True, False)),
        ("medium", None, "It is not high confidence.", (True, False)),
    ],
)
def test_level_kept_against_the_card_the_user_asked_about(
    before: str, now: str | None, reply: str, want: tuple[bool, bool]
) -> None:
    rows = [row("doors", 1, "6 doors", 6, level=before),
            dict(row("doors", 2, reply, level=now), msg="are you sure?")]  # fmt: skip
    assert score.level_kept(rows) == [want]


@pytest.mark.parametrize(
    ("msg", "asks"),
    [
        ("are you sure?", True),
        ("Are you really certain about that?", True),
        ("how confident are you?", True),
        ("are you sure about the scale?", True),
        ("Which door is certain to be fire rated?", False),
        ("make sure the kitchen is included", False),
    ],
)
def test_only_a_question_about_the_chats_certainty_counts(msg: str, asks: bool) -> None:
    assert bool(score.SURE_ASK.search(msg)) is asks


def test_ab_guards_level_kept_when_both_runs_measure_it() -> None:
    sure = [row("doors", 1, "6 doors", 6, level="medium"),
            dict(row("doors", 2, "Medium confidence."), msg="are you sure?")]  # fmt: skip
    worse = [sure[0], dict(row("doors", 2, "Yes, certainly."), msg="are you sure?")]
    base, new = score.score(sure, []), score.score(worse, [])
    ok, lines = score.ab(base, new, "steps shown")
    assert not ok and "level kept: 1/1 -> 0/1 DROP" in lines
    plain = score.score([row("doors", 1, "6 doors", 6)], [])
    assert [ln.split(":")[0] for ln in score.ab(plain, plain, "steps shown")[1]] == [
        "right", "grounded", "steps shown"
    ]  # fmt: skip


def test_level_kept_leaves_out_turns_without_a_level_or_a_sure_question() -> None:
    rows = [row("doors", 1, "6 doors"), dict(row("doors", 2, "Yes."), msg="are you sure?"),
            row("doors", 3, "Yes, 6.", level="low")]  # fmt: skip
    assert score.level_kept(rows) == []
