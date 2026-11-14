"""Record and replay the agent chat's model calls, so a chat run that repeats costs 0 USD.

  python3 -m chat.replay --cache ../data/stoa/chat-eval/replay --mode record|replay [--port 0]
  python3 -m chat.replay --cache ... --rekey     # after a change to key_of

An OpenAI-compatible endpoint on 127.0.0.1 for the backend's AGENT_BASE_URL. Each POST is keyed
by its path and its JSON body (keys sorted, measured timings blanked: VOLATILE). A key in the
cache is answered from it, with the recorded status, body and usage (so the turn's cost_usd is
what the call cost when recorded).
A miss: `record` forwards it to --upstream with the request's own Authorization header (the key
is passed on, never stored or printed) and stores a 200 reply; `replay` answers 503 and spends
nothing. GET /stats gives the counts. The cache holds request and reply bodies, which carry
drawing text: keep it under data/ (gitignored).
"""

import argparse
import hashlib
import json
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai"
# (url, body, headers) -> (status, body); urllib by default, a fake in tests
Upstream = Callable[[str, bytes, dict[str, str]], tuple[int, bytes]]
# A field that differs run to run in what the backend sends (tool results carry their measured
# latency_s), also inside a tool message's JSON-in-a-string; its number is blanked in the key.
VOLATILE = re.compile(r'((?:\\)*"latency_s(?:\\)*":\s*)-?[0-9.eE+-]+')


def urllib_upstream(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def key_of(path: str, body: bytes) -> str:
    """The cache key: the path and the body's JSON with keys sorted and VOLATILE numbers blanked
    (a body that is not JSON is keyed as sent)."""
    try:
        text = json.dumps(json.loads(body), sort_keys=True, separators=(",", ":"))
        canon = VOLATILE.sub(r"\g<1>0", text).encode()
    except ValueError:
        canon = body
    return hashlib.sha256(path.encode() + b"\n" + canon).hexdigest()[:32]


def rekey(cache: Path) -> int:
    """Rename every recorded call to its key under today's key_of; the count renamed."""
    moved = 0
    for stored in cache.glob("*.json"):
        got: dict[str, Any] = json.loads(stored.read_text())
        body = json.dumps(got["request"]).encode()
        target = cache / f"{key_of(got['path'], body)}.json"
        if target != stored:
            stored.replace(target)
            moved += 1
    return moved


class Replay:
    """The cache and the counts, apart from HTTP so tests can call `answer` directly."""

    def __init__(self, cache: Path, mode: str, upstream_url: str, upstream: Upstream) -> None:
        if mode not in ("record", "replay"):
            raise ValueError(f"mode is record or replay, not {mode!r}")
        self.cache = cache
        self.mode = mode
        self.upstream_url = upstream_url.rstrip("/")
        self.upstream = upstream
        self.counts = {"hits": 0, "misses": 0, "forwarded": 0, "recorded": 0}
        self._lock = threading.Lock()
        cache.mkdir(parents=True, exist_ok=True)

    def answer(self, path: str, body: bytes, auth: str | None) -> tuple[int, bytes]:
        key = key_of(path, body)
        stored = self.cache / f"{key}.json"
        if stored.exists():
            got: dict[str, Any] = json.loads(stored.read_text())
            self._count("hits")
            return int(got["status"]), json.dumps(got["reply"]).encode()
        self._count("misses")
        if self.mode == "replay":
            # kept so a miss can be diffed against the recorded call it should have matched
            (self.cache / "misses").mkdir(exist_ok=True)
            (self.cache / "misses" / f"{key}.json").write_bytes(body)
            error = {"error": {"message": f"replay: no recorded reply for {key}", "code": 503}}
            return 503, json.dumps(error).encode()
        headers = {"Content-Type": "application/json", **({"Authorization": auth} if auth else {})}
        status, data = self.upstream(self.upstream_url + path, body, headers)
        self._count("forwarded")
        if status == 200:
            try:
                reply = json.loads(data)
            except ValueError:
                return status, data
            record = {"path": path, "request": json.loads(body), "status": status, "reply": reply}
            tmp = stored.with_suffix(".tmp")
            tmp.write_text(json.dumps(record, ensure_ascii=False))
            tmp.replace(stored)
            self._count("recorded")
        return status, data

    def _count(self, name: str) -> None:
        with self._lock:
            self.counts[name] += 1


def serve(replay: Replay, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            status, data = replay.answer(self.path, body, self.headers.get("Authorization"))
            self._send(status, data)

        def do_GET(self) -> None:
            if self.path != "/stats":
                self._send(404, b'{"error": "not found"}')
                return
            self._send(200, json.dumps({"mode": replay.mode, **replay.counts}).encode())

        def _send(self, status: int, data: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            pass  # the request line is enough noise; /stats has the counts

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--mode", choices=["record", "replay"], default="replay")
    ap.add_argument("--port", type=int, default=0, help="0: a free port, printed")
    ap.add_argument("--upstream", default=GEMINI)
    ap.add_argument("--rekey", action="store_true", help="re-key the cache after a key_of change")
    args = ap.parse_args()
    if args.rekey:
        print(f"replay: re-keyed {rekey(args.cache)} recorded calls")
        return
    server = serve(Replay(args.cache, args.mode, args.upstream, urllib_upstream), args.port)
    print(f"replay: {args.mode} on http://127.0.0.1:{server.server_address[1]}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
