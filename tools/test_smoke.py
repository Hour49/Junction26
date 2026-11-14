"""tools/smoke.py: the pure checks, and a whole run against a fake env on a local port."""

import json
import threading
import urllib.parse
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest
import smoke

ANSWER = {
    "answer": 2,
    "unit": "count",
    "confidence": {"signal": "g1main", "score": 0.9, "calibrated": False},
    "check": None,
    "marks": [{"id": "e1"}, {"id": "e2"}],
    "refusal": None,
    "cost_usd": 0.0,
    "line": {"sure": False},
}
REFUSAL = {
    "answer": None,
    "refusal": {"code": "unsupported-question", "text": "no"},
    "cost_usd": 0.0,
}


def project(state: str = "done", cost: float = 0.0, file_state: str = "ready") -> dict:
    return {
        "id": "p1",
        "state": state,
        "cost_usd": cost,
        "files": [
            {
                "id": "f1",
                "path": "plans/a.pdf",
                "state": file_state,
                "reason": "",
                "cost_usd": cost,
            },
            {"id": "f2", "path": "x.dwg", "state": "set_aside", "reason": "a DWG is not read"},
        ],
        "drawings": [{"drawing_id": "d1", "file": "plans/a.pdf", "route": "vector"}],
    }


def trace(cost: float = 0.0, failure: str | None = None) -> dict:
    return {
        "files": [
            {
                "file": {"id": "f1"},
                "stages": [{"stage": "read", "cost_usd": cost, "failure": failure}],
            },
            {"file": {"id": "f2"}, "stages": [{"stage": "identify", "cost_usd": 0.0}]},
        ]
    }


def test_health_needs_status_ok() -> None:
    assert smoke.health_check(200, {"status": "ok"}).ok
    assert not smoke.health_check(200, {"status": "down"}).ok
    assert not smoke.health_check(0, "connection refused").ok


def test_info_tolerates_no_commit_and_no_gemini_status() -> None:
    checks = smoke.info_checks(200, {"no_keys": False, "readers": {"raster": "x"}, "limits": {}})
    assert all(c.ok for c in checks)
    assert [c.detail for c in checks[1:]] == ["absent (not in /api/info)"] * 2


def test_info_reports_the_gemini_status_and_fails_on_an_exhausted_budget() -> None:
    info = {"readers": {"raster": "x"}, "limits": {}, "commit": "abc123"}
    ok = smoke.info_checks(200, {**info, "gemini": {"status": "ok", "budget_exhausted": False}})
    assert (
        all(c.ok for c in ok)
        and ok[1].detail == "abc123"
        and "budget_exhausted False" in ok[2].detail
    )
    spent = smoke.info_checks(200, {**info, "gemini": {"budget_exhausted": True}})
    assert not spent[2].ok


def test_info_without_readers_fails() -> None:
    assert not smoke.info_checks(200, {"limits": {}})[0].ok
    assert not smoke.info_checks(500, "boom")[0].ok


def test_frontend_must_be_html_with_a_script() -> None:
    page = b"<!doctype html><html><head><script src=/a.js></script></head></html>"
    assert smoke.frontend_check(200, page, "text/html; charset=utf-8").ok
    assert not smoke.frontend_check(200, b'{"detail": "Not Found"}', "application/json").ok


def test_a_stage_failure_or_not_ingested_is_unexpected_a_triage_set_aside_is_not() -> None:
    assert smoke.unexpected_failure({}, [{"stage": "read", "failure": "boom"}]) == "read: boom"
    assert smoke.unexpected_failure({"reason": "not ingested: restarted"}, []) is not None
    assert smoke.unexpected_failure({"reason": "not a floor plan: a photo of a cat"}, []) is None


def test_file_checks_pass_on_a_done_project() -> None:
    checks = smoke.file_checks("x", project(), trace()["files"])
    assert all(c.ok for c in checks), checks


def test_file_checks_fail_on_an_unfinished_file_or_a_failed_stage() -> None:
    queued = smoke.file_checks("x", project(file_state="running"), trace()["files"])
    assert [c.name for c in queued if not c.ok] == ["every file final"]
    failed = smoke.file_checks("x", project(), trace(failure="model crashed")["files"])
    assert [c.name for c in failed if not c.ok] == ["no unexpected failure"]
    assert not smoke.file_checks("x", project(state="failed"), [])[0].ok


def test_costs_are_found_in_the_project_files_and_stages() -> None:
    spent = smoke.costs(project(cost=0.01), trace(cost=0.01)["files"])
    assert [where for where, _ in spent] == ["project", "file f1 plans/a.pdf", "f1 stage read"]
    assert smoke.costs(project(), trace()["files"]) == []


def test_a_paid_call_fails_unless_paid_is_allowed() -> None:
    assert not smoke.cost_check("x", [("project", 0.01)], paid=False).ok
    assert smoke.cost_check("x", [("project", 0.01)], paid=True).ok
    assert smoke.cost_check("x", [], paid=False).ok


def test_an_answer_needs_a_value_its_fields_and_marks_for_a_count() -> None:
    assert smoke.answer_check("x", "a.pdf", "q", 200, ANSWER).ok
    assert smoke.answer_check("x", "a.pdf", "q", 200, {**ANSWER, "answer": 0, "marks": []}).ok
    assert not smoke.answer_check("x", "a.pdf", "q", 200, {**ANSWER, "marks": []}).ok
    assert not smoke.answer_check("x", "a.pdf", "q", 200, REFUSAL).ok
    fields = {k: v for k, v in ANSWER.items() if k != "check"}
    assert smoke.answer_check("x", "a.pdf", "q", 200, fields).detail == "fields missing: ['check']"
    assert not smoke.answer_check("x", "a.pdf", "q", 500, {"detail": "boom"}).ok


def test_the_roof_question_must_be_refused() -> None:
    assert smoke.refusal_check("x", "a.pdf", 200, REFUSAL).ok
    assert not smoke.refusal_check("x", "a.pdf", 200, ANSWER).ok


def test_one_drawing_per_route_in_order() -> None:
    drawings = [
        {"route": "raster", "n": 1},
        {"route": "vector", "n": 2},
        {"route": "raster", "n": 3},
    ]
    assert [d["n"] for d in smoke.first_per_route(drawings)] == [1, 2]


def test_the_table_counts_passes_and_failures() -> None:
    text = smoke.table([smoke.Check("a", "b", True, "x|y"), smoke.Check("a", "c", False)])
    assert "| a | b | pass | x/y |" in text and "| a | c | FAIL |  |" in text
    assert text.endswith("1 passed, 1 failed")


def test_arguments_are_checked(tmp_path: Path) -> None:
    for argv in (["ftp://x"], ["http://x", "--header", "no colon"], ["http://x", "--zip", "/no"]):
        with pytest.raises(SystemExit) as exit_:
            smoke.parse(argv)
        assert exit_.value.code == 2
    assert smoke.parse(["http://x", "--no-upload", "--zip", "/no"]).no_upload


class FakeEnv(BaseHTTPRequestHandler):
    """Just enough of the API for one sample and one upload; `cost` is what every reading paid."""

    cost: ClassVar[float] = 0.0
    seen: ClassVar[list[str]] = []

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        self.seen.append(f"GET {self.path}")
        if path == "/":
            return self._send(200, b"<html><script src=/a.js></script></html>", "text/html")
        replies = {
            "/health": {"status": "ok"},
            "/api/info": {
                "no_keys": False,
                "readers": {"raster": "c"},
                "limits": {},
                "rule_packs": [{"id": "fi"}],
            },
            "/api/projects/p1": project(cost=self.cost),
            "/api/projects/p1/trace": trace(cost=self.cost),
            "/api/drawings/d1": {"drawing_id": "d1"},
            "/api/projects/p1/issues": {"issues": []},
            "/api/projects/p1/checks": {"drawings": []},
            "/api/drawings/d1/checks": {"rules": []},
        }
        self._json(*((200, replies[path]) if path in replies else (404, {"detail": "no"})))

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        path = urllib.parse.urlparse(self.path).path
        self.seen.append(f"POST {self.path}")
        if path in ("/api/projects/sample", "/api/projects"):
            return self._json(202, {"id": "p1", "state": "queued"})
        if path == "/api/ask":
            asked = json.loads(body)
            return self._json(200, REFUSAL if "roof" in asked["question"] else ANSWER)
        if path == "/api/projects/p1/ask":
            return self._json(200, {"parts": [{"drawing_id": "d1"}], "total": 2})
        self._json(404, {"detail": "no"})

    def _json(self, status: int, body: object) -> None:
        self._send(status, json.dumps(body).encode(), "application/json")

    def _send(self, status: int, data: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def env() -> Iterator[str]:
    FakeEnv.cost, FakeEnv.seen = 0.0, []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeEnv)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_a_whole_run_passes_on_a_healthy_env(env: str, tmp_path: Path) -> None:
    upload = tmp_path / "demo.zip"
    upload.write_bytes(b"PK")
    assert smoke.main([env, "--zip", str(upload), "--timeout", "5"]) == 0
    assert "POST /api/projects?name=demo.zip" in FakeEnv.seen
    assert "GET /api/drawings/d1/checks?pack=fi&project=p1" in FakeEnv.seen


def test_a_paid_reading_fails_the_run_unless_paid(env: str) -> None:
    FakeEnv.cost = 0.002
    checks = smoke.run(env, None, paid=False, timeout=5, headers={})
    assert [c.name for c in checks if not c.ok] == ["no paid model call"]
    assert all(c.ok for c in smoke.run(env, None, paid=True, timeout=5, headers={}))


def test_no_env_fails_with_exit_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke.main(["http://127.0.0.1:9", "--no-upload", "--timeout", "1"]) == 1
    assert "FAIL" in capsys.readouterr().out
