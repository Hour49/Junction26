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
    ],
)
def test_right_reads_the_card_or_the_first_number_not_a_citation(
    truth: Any, kind: str, text: str, value: float | None, want: bool
) -> None:
    assert score.right(row("s", 1, text, truth, kind=kind, value=value)) is want


def test_grounded_finds_numbers_in_the_stored_chats_tool_results(tmp_path: Path) -> None:
    chats = tmp_path / "projects" / "pid" / "chats"
    chats.mkdir(parents=True)
    (chats / "c1.json").write_text(json.dumps({"results": [{"doors": 6, "area_m2": 14.53}]}))
    projects = [tmp_path / "projects"]
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
