"""Offline tests for tools/board's message format. Run: uv run --no-project --with pytest pytest -q tools"""
import importlib.machinery
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

_path = str(Path(__file__).with_name("board"))
_spec = importlib.util.spec_from_loader("board", importlib.machinery.SourceFileLoader("board", _path))
board = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(board)


def test_render_parse_roundtrip():
    text = board.render("bogdan", ["tudor", "bea"], "request", "Please review PR #3.\n\nThanks", "c42")
    head, body = board.parse(text, "Bogzx")
    assert head == {"from": "bogdan", "to": ["tudor", "bea"], "type": "request", "ref": "c42"}
    assert body == "Please review PR #3.\n\nThanks"


def test_comment_without_header_is_human_to_all():
    head, body = board.parse("lgtm, ship it", "madabotos")
    assert head == {"from": "madabotos", "to": ["all"], "type": "human", "ref": None}
    assert body == "lgtm, ship it"


def test_crlf_from_web_editor_still_parses():
    text = board.render("a", ["all"], "status", "x").replace("\n", "\r\n")
    assert board.parse(text, "gh")[0]["from"] == "a"


def test_broken_header_json_falls_back_to_human():
    head, _ = board.parse('<!-- board:v1 {"from": nope} -->\nhi', "gh")
    assert head["type"] == "human"


def test_for_me_filters_own_and_others():
    assert board.for_me({"from": "a", "to": ["all"]}, "b")
    assert board.for_me({"from": "a", "to": ["b", "c"]}, "b")
    assert not board.for_me({"from": "a", "to": ["c"]}, "b")
    assert not board.for_me({"from": "b", "to": ["all"]}, "b")  # own message


def test_mentions_ignore_code_and_emails():
    assert board.mentions("ping @Bogzx please") == ["@Bogzx"]
    assert board.mentions("see `@types/node` and bob@example.com") == []
    assert board.mentions("```\n@decorator\n```") == []


def test_notify_writes_mentions_and_header():
    text = board.render("Bogzx", ["all"], "blocker", "Need the API key decision.", notify=["madabotos"])
    head, body = board.parse(text, "Bogzx")
    assert head["notify"] == ["madabotos"]
    assert "cc @madabotos: needs human attention" in text
    assert body == "Need the API key decision."
    assert board.mentions(body) == []  # the cc line is not part of the body


def test_notify_reaches_that_persons_orchestrator_even_if_not_addressed():
    assert board.for_me({"from": "a", "to": ["c"], "notify": ["b"]}, "b")


def test_canonical_fixes_case_and_rejects_outsiders():
    team = ["Bogzx", "madabotos"]
    assert board.canonical(["bogzx", "MADABOTOS"], team, "--to") == ["Bogzx", "madabotos"]
    with pytest.raises(SystemExit, match="--notify torvalds: unknown"):
        board.canonical(["torvalds"], team, "--notify")


def test_split_names_strips_spaces_and_at():
    assert board.split_names("a, @b ,,") == ["a", "b"]


def _msg(mid, text, created="2026-11-03T12:00:00Z", reactions=None, state="open",
         updated=None, author="gh"):
    return {"id": mid, "thread": 1, "title": None, "author": author, "created": created,
            "updated": updated or created, "text": text, "url": "u",
            "reactions": reactions or {}, "state": state}


def test_pending_tracks_ack_and_done():
    at = datetime(2026, 11, 3, 12, 45, tzinfo=timezone.utc)
    r = board.render
    msgs = [
        _msg("c1", r("a", ["b"], "request", "unacked")),
        {**_msg("c2", r("a", ["b"], "request", "eyes")), "reactors": [("eyes", "B")]},
        {**_msg("c3", r("a", ["b"], "blocker", "rocket")), "reactors": [("rocket", "B")]},
        _msg("c4", r("a", ["b"], "question", "answered")),
        _msg("c5", r("b", ["a"], "answer", "here", "c4")),
        _msg("c6", r("a", ["b"], "request", "replied-ack")),
        _msg("c7", r("b", ["a"], "ack", "on it", "c6")),
        _msg("c8", r("a", ["b"], "status", "not a request")),
        _msg("c9", r("a", ["b"], "request", "closed thread"), state="closed"),
    ]
    got = {m["id"]: (acked, age) for m, _, acked, age in board.pending(msgs, at)}
    assert got == {"c1": (False, 45), "c2": (True, 45), "c6": (True, 45)}


# ---------- review fixes, 2026-11-03 (the first seven are the reviewer's reproductions) ----------

def _feed(monkeypatch, msgs, calls=None):
    def fetch(since):
        if calls is not None:
            calls.append(since)
        return [m for m in msgs if board.ts(m["updated"]) >= since]
    monkeypatch.setattr(board, "fetch", fetch)


def test_read_all_returns_everything_even_if_seen(monkeypatch):
    _feed(monkeypatch, [_msg("c1", board.render("a", ["all"], "status", "x"))])
    st = {}
    assert len(board.unread("b", st, everything=True)) == 1
    assert len(board.unread("b", st, everything=True)) == 1


def test_to_matches_login_case_insensitively():
    assert board.for_me({"from": "a", "to": ["bogzx"]}, "Bogzx")


@pytest.mark.parametrize("head", ['{"from": "x", "to": "all"}',
                                  '{"from": "x", "to": ["all"], "notify": "Bogzx"}',
                                  '{"from": "x", "to": [1, null]}', '["not", "an", "object"]',
                                  '{"to": ["all"]}', '{"from": "x", "ref": 5, "type": 7}'])
def test_malformed_header_shape_does_not_crash_reader(head):
    h, _ = board.parse(f"<!-- board:v1 {head} -->\nhi", "gh")
    board.for_me(h, "Bogzx")
    assert isinstance(h["to"], list) and isinstance(h["type"], str)


def test_title_mention_is_caught():
    with pytest.raises(SystemExit):
        board.check_body(board.mention_text("@Bogzx look", "fix it"), False)


def test_senders_own_follow_up_or_reaction_is_not_an_ack():
    at = datetime(2026, 11, 3, 13, 0, tzinfo=timezone.utc)
    m = [{**_msg("c1", board.render("a", ["b"], "request", "please"), author="A-gh"),
          "reactors": [("eyes", "a-GH"), ("rocket", "A-gh")]},
         _msg("c2", board.render("a", ["b"], "fyi", "more detail", "c1"), author="A-gh"),
         _msg("c3", board.render("A", ["b"], "done", "did it myself", "c1"), author="A-gh")]
    assert [x[2] for x in board.pending(m, at)] == [False]


def test_cursor_uses_server_time_not_local_clock(monkeypatch):
    monkeypatch.setattr(board, "now", lambda: datetime(2030, 1, 1, tzinfo=timezone.utc))
    calls = []
    _feed(monkeypatch, [_msg("c1", board.render("a", ["all"], "status", "x"),
                             created="2026-11-03T12:00:00Z")], calls)
    st = {}
    board.unread("b", st)
    board.unread("b", st)
    assert calls[-1] == datetime(2026, 11, 3, 11, 58, tzinfo=timezone.utc)  # newest - overlap


def test_first_run_marks_history_read_then_delivers_new(monkeypatch):
    msgs = [_msg("c1", board.render("a", ["all"], "status", "old"))]
    _feed(monkeypatch, msgs)
    st = {}
    assert board.unread("b", st) == [] and st["first_run_marked"] == 1
    msgs.append(_msg("c2", board.render("a", ["b"], "request", "new"),
                     created="2026-11-03T12:05:00Z"))
    assert [m["id"] for m in board.unread("b", st)] == ["c2"]
    assert board.unread("b", st) == []


def test_first_run_on_empty_board_then_first_message_is_delivered(monkeypatch):
    msgs = []
    _feed(monkeypatch, msgs)
    st = {}
    assert board.unread("b", st) == []
    msgs.append(_msg("c1", board.render("a", ["all"], "status", "hi")))
    assert [m["id"] for m in board.unread("b", st)] == ["c1"]


def test_old_comment_edited_later_is_not_delivered_again(monkeypatch):
    msgs = [_msg("c1", board.render("a", ["all"], "status", "x"))]
    _feed(monkeypatch, msgs)
    st = {"init": True, "cursor": "2026-11-03T12:30:00+00:00", "seen": []}  # seen list lost
    msgs[0]["updated"] = "2026-11-03T13:00:00Z"
    assert board.unread("b", st) == []


def test_human_comment_goes_to_the_people_it_mentions():
    head, _ = board.parse("@madabotos can you check the schema?", "Bogzx")
    assert head["to"] == ["madabotos"] and head["type"] == "human"
    assert not board.for_me(head, "Cucuteanu-Tudor-912")
    assert board.parse("lgtm", "Bogzx")[0]["to"] == ["all"]


def test_wait_retries_gh_errors_then_delivers(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BOARD_STATE", str(tmp_path))
    monkeypatch.setenv("BOARD_ME", "b")
    monkeypatch.setattr(board, "team", list)
    monkeypatch.setattr(board.time, "sleep", lambda s: None)
    results = iter([[], board.GhError("HTTP 504"), [{"id": "c1"}]])

    def unread(who, state, anyone=False):
        r = next(results)
        if isinstance(r, Exception):
            raise r
        state["init"] = True
        return [{**_msg("c1", board.render("a", ["b"], "request", "hi")),
                 "head": {"from": "a", "to": ["b"], "type": "request", "ref": None},
                 "body": "hi"}] if r else []
    monkeypatch.setattr(board, "unread", unread)
    board.main(["wait", "--interval", "1"])
    out = capsys.readouterr()
    assert "HTTP 504; retrying" in out.err and "[request]" in out.out


def test_wait_gives_up_after_continuous_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("BOARD_STATE", str(tmp_path))
    monkeypatch.setenv("BOARD_ME", "b")
    clock = [0.0]
    monkeypatch.setattr(board.time, "time", lambda: clock[0])
    monkeypatch.setattr(board.time, "sleep", lambda s: clock.__setitem__(0, clock[0] + s))

    def broken(*a, **k):
        raise board.GhError("HTTP 503")
    monkeypatch.setattr(board, "unread", broken)
    with pytest.raises(SystemExit, match="unreachable for 1800s"):
        board.main(["wait", "--interval", "60"])
