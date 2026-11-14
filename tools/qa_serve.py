#!/usr/bin/env python3
"""Serves a built frontend and passes /api and /health to the backend, so the browser sees one
origin as in development (the Vite dev server's proxy). The API has no CORS (docs/API.md), so a
frontend served from another origin could not call it. Used by tools/qa-env.sh --frontend.

    python3 tools/qa_serve.py <dist folder> <port> <backend URL>

Any other path that is not a file in <dist folder> gets index.html (a single-page app's routes).
Standard library only; bound to 127.0.0.1.
"""

import functools
import sys
import urllib.error
import urllib.request
from email.message import Message
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PASSED = ("/api/", "/api?", "/health")
REQUEST_HEADERS = ("content-type", "accept", "content-length")
RESPONSE_HEADERS = (
    "content-type",
    "cache-control",
    "content-disposition",
    "location",
    "x-accel-buffering",
)
TIMEOUT_S = 600  # an upload is ingested inside the request in tests; uploads can be large


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, backend: str, **kwargs: object) -> None:
        self.backend = backend.rstrip("/")
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def do_GET(self) -> None:
        if self.path.startswith(PASSED):
            return self._pass()
        if not (Path(self.directory) / self.path.split("?")[0].lstrip("/")).is_file():
            self.path = "/index.html"  # the app's own routes
        return super().do_GET()

    def do_POST(self) -> None:
        self._pass()

    def do_PUT(self) -> None:
        self._pass()

    def do_DELETE(self) -> None:
        self._pass()

    def _pass(self) -> None:
        size = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(size) if size else None
        headers = {k: v for k, v in self.headers.items() if k.lower() in REQUEST_HEADERS}
        request = urllib.request.Request(
            self.backend + self.path, data=body, method=self.command, headers=headers
        )
        try:
            response = urllib.request.urlopen(request, timeout=TIMEOUT_S)
        except urllib.error.HTTPError as error:
            response = error  # 4xx/5xx: passed on as they are
        except urllib.error.URLError as error:
            self.send_error(502, f"backend unreachable: {error.reason}")
            return
        with response:
            self.send_response(response.status)
            for name, value in response.headers.items():
                if name.lower() in RESPONSE_HEADERS:
                    self.send_header(name, value)
            if _streamed(response.headers):
                # an event stream (the chat's steps): each piece goes on as it arrives; the reply has no
                # length, so it ends when this connection closes
                self.close_connection = True
                self.end_headers()
                try:
                    while piece := response.read1(65536):
                        self.wfile.write(piece)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the browser left; the backend finishes the turn by itself
                return
            data = response.read()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _streamed(headers: Message) -> bool:
    """Whether the backend sends this reply piece by piece: an event stream, or any chunked body."""
    kind = (headers.get("Content-Type") or "").lower()
    return (
        kind.startswith("text/event-stream")
        or "chunked" in (headers.get("Transfer-Encoding") or "").lower()
    )


def server(dist: Path, port: int, backend: str) -> ThreadingHTTPServer:
    handler = functools.partial(Handler, directory=str(dist), backend=backend)
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit("usage: qa_serve.py <dist folder> <port> <backend URL>")
    dist, port, backend = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    if not (dist / "index.html").is_file():
        sys.exit(f"qa_serve: no index.html in {dist}")
    print(f"qa_serve: {dist} on http://127.0.0.1:{port}, /api -> {backend}", flush=True)
    server(dist, port, backend).serve_forever()


if __name__ == "__main__":
    main()
