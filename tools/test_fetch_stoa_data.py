"""Offline tests for tools/fetch_stoa_data.py: a local HTTP server stands in for the dataset host."""
import importlib.util
import threading
import zipfile
from collections import namedtuple
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("fetch", Path(__file__).with_name("fetch_stoa_data.py"))
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)

PAYLOAD = bytes(range(256)) * 40  # 10 KB


def serve(honour_range):
    class Handler(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAYLOAD)))
            self.end_headers()

        def do_GET(self):
            start = 0
            if honour_range and self.headers.get("Range"):
                start = int(self.headers["Range"].split("=")[1].rstrip("-"))
                self.send_response(206)
            else:
                self.send_response(200)
            body = PAYLOAD[start:]
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture(params=[True, False], ids=["server-resumes", "server-ignores-range"])
def url(request):
    server = serve(honour_range=request.param)
    yield f"http://127.0.0.1:{server.server_address[1]}/junction-dataset-preview.zip"
    server.shutdown()


def test_download_from_scratch(url, tmp_path):
    dest = tmp_path / "set.zip"
    assert fetch.download(url, dest) == len(PAYLOAD)
    assert dest.read_bytes() == PAYLOAD


def test_download_completes_a_partial_file(url, tmp_path):
    dest = tmp_path / "set.zip"
    dest.write_bytes(PAYLOAD[:3000])
    fetch.download(url, dest)
    assert dest.read_bytes() == PAYLOAD


def test_download_refuses_without_disk_space(url, tmp_path, monkeypatch):
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(fetch.shutil, "disk_usage", lambda _: usage(0, 0, 100))
    with pytest.raises(SystemExit, match="not enough disk space"):
        fetch.download(url, tmp_path / "set.zip")
    assert not (tmp_path / "set.zip").exists()


def make_zip(path, names):
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, f"content of {name}")
    return path


def test_extract_unpacks_into_the_target(tmp_path):
    archive = make_zip(tmp_path / "set.zip", ["drawings/A-101.pdf", "schedules/doors.xlsx"])
    fetch.safe_extract(archive, tmp_path / "preview")
    assert (tmp_path / "preview" / "drawings" / "A-101.pdf").read_text() == "content of drawings/A-101.pdf"
    assert not (tmp_path / "preview.partial").exists()


def test_extract_refuses_an_entry_outside_the_target(tmp_path):
    archive = make_zip(tmp_path / "set.zip", ["ok.txt", "../evil.txt"])
    with pytest.raises(SystemExit, match="refusing entry"):
        fetch.safe_extract(archive, tmp_path / "out" / "preview")
    assert not (tmp_path / "out" / "evil.txt").exists()
    assert not (tmp_path / "out" / "preview").exists()
    assert not (tmp_path / "out" / "preview.partial").exists()


def test_extract_leaves_an_existing_target_alone(tmp_path, capsys):
    archive = make_zip(tmp_path / "set.zip", ["new.txt"])
    (tmp_path / "preview").mkdir()
    fetch.safe_extract(archive, tmp_path / "preview")
    assert not (tmp_path / "preview" / "new.txt").exists()
    assert "already extracted" in capsys.readouterr().out


def test_env_var_wins_over_the_env_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# links\nSTOA_PREVIEW_URL='https://file.example/p.zip'\n")
    monkeypatch.delenv("STOA_PREVIEW_URL", raising=False)
    assert fetch.env_value("STOA_PREVIEW_URL", env) == "https://file.example/p.zip"
    monkeypatch.setenv("STOA_PREVIEW_URL", "https://env.example/p.zip")
    assert fetch.env_value("STOA_PREVIEW_URL", env) == "https://env.example/p.zip"


def test_missing_link_names_the_variable(monkeypatch, tmp_path):
    monkeypatch.delenv("STOA_FULL_URL", raising=False)
    monkeypatch.setattr(fetch, "ROOT", tmp_path)
    monkeypatch.setattr(fetch, "env_value", lambda name: None)
    with pytest.raises(SystemExit, match="STOA_FULL_URL is not set"):
        fetch.fetch("full")
