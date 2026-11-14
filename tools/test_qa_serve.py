"""tools/qa_serve.py: a built frontend and the backend on one origin."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import qa_serve


class FakeBackend(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/missing":
            self._reply(404, {"detail": "no drawing", "code": "not-found"})
        else:
            self._reply(200, {"path": self.path})

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self._reply(
            202, {"path": self.path, "got": body.decode(), "type": self.headers["Content-Type"]}
        )

    def _reply(self, status: int, body: dict[str, str]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        pass


def _serve(server: ThreadingHTTPServer) -> Iterator[str]:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def site(tmp_path: Path) -> Iterator[str]:
    (tmp_path / "index.html").write_text("<p>app</p>")
    (tmp_path / "app.js").write_text("console.log(1)")
    backend = ThreadingHTTPServer(("127.0.0.1", 0), FakeBackend)
    for backend_url in _serve(backend):
        front = qa_serve.server(tmp_path, 0, backend_url)
        front.RequestHandlerClass.log_message = lambda *args: None  # type: ignore[method-assign]
        yield from _serve(front)


def get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def test_files_are_served_and_any_other_path_gets_the_app(site: str) -> None:
    assert get(f"{site}/app.js") == (200, b"console.log(1)")
    assert get(f"{site}/projects/abc") == (200, b"<p>app</p>")


def test_the_api_is_passed_to_the_backend_with_its_status_and_body(site: str) -> None:
    status, body = get(f"{site}/api/info?x=1")
    assert (status, json.loads(body)) == (200, {"path": "/api/info?x=1"})
    status, body = get(f"{site}/api/missing")
    assert (status, json.loads(body)["code"]) == (404, "not-found")
    request = urllib.request.Request(
        f"{site}/api/projects?name=a.pdf", data=b"%PDF", method="POST",
        headers={"Content-Type": "application/octet-stream"},
    )  # fmt: skip
    with urllib.request.urlopen(request) as response:
        assert response.status == 202
        assert json.loads(response.read()) == {
            "path": "/api/projects?name=a.pdf", "got": "%PDF", "type": "application/octet-stream",
        }  # fmt: skip
