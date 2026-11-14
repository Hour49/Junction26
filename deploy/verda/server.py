"""The raster reader over HTTP, for a Verda serverless container (deployment `hour49-reader`).

    GET  /health -> {"status": "ok", "model": ..., "provider": ...}
    POST /read   (body: the image bytes, PNG or JPEG) -> {"schema": "reader_v1", "extracted": {...}}

`extracted` is the backend's `Extracted` (method, scale, plans, elements with `attrs.score`, rooms,
read, notes) as JSON, the same fields extraction_v1 files carry, so the client
(backend/app/adapters/raster_remote) validates it with the backend's own model. The detector is
the backend's `OnnxDetector` (app/adapters/raster_detector), run on the GPU, so the endpoint
gives what the CPU component gives locally.

Environment: READER_MODEL (core's export: model.onnx, model.json and detector.json, default
/opt/reader/model),
READER_APP (folder holding the backend's `app` package, default /opt/reader), PORT (8000).
Verda's gateway checks the inference key before a request reaches the container; the server
itself listens only on the container's port. Standard library plus the backend's dependencies.
"""

import hashlib
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, os.environ.get("READER_APP", "/opt/reader"))

from app.adapters.raster_detector import OnnxDetector, load_config
from app.core.drawing.model import Page
from app.core.pipeline.model import DrawingFile, Sheet

MAX_BYTES = 40_000_000  # the largest CubiCasa PNG is about 9 MB
KINDS = {b"\x89PNG": "png", b"\xff\xd8\xff": "jpeg"}


class Upload:
    """The `DrawingFiles` port over the one image of a request."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, path: str) -> bytes:
        return self._data


def session(model: Path):
    import onnxruntime

    if "CUDAExecutionProvider" in onnxruntime.get_available_providers():
        onnxruntime.preload_dlls()  # the CUDA and cuDNN libraries of the nvidia-* wheels
    providers: list = ["CPUExecutionProvider"]
    if "CUDAExecutionProvider" in onnxruntime.get_available_providers():
        # full fp32: with TF32 (the CUDA provider's default) a box inside the model's NMS moved
        # by 20 px against the CPU on 2 of 20 val pages (parity.py, 2026-11-14)
        providers.insert(0, ("CUDAExecutionProvider", {"use_tf32": 0}))
    options = onnxruntime.SessionOptions()
    options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
    return onnxruntime.InferenceSession(str(model), options, providers=providers)


class Reader:
    def __init__(self, folder: Path) -> None:
        started = time.perf_counter()
        self.config = load_config(folder)
        self.session = session(folder / "model.onnx")
        self.name = folder.name
        self.provider = self.session.get_providers()[0]
        self.load_s = round(time.perf_counter() - started, 2)

    def read(self, data: bytes) -> dict:
        kind = next((k for magic, k in KINDS.items() if data.startswith(magic)), None)
        if kind is None:
            raise ValueError("the body is not a PNG or JPEG image")
        source = DrawingFile(
            path="upload", size=len(data), sha256=hashlib.sha256(data).hexdigest(), kind=kind
        )
        sheet = Sheet(file=source, pages=(Page(page=1, width=1, height=1, unit="px"),))
        started = time.perf_counter()
        extracted = OnnxDetector(Upload(data), self.config, self.session, self.name).extract(
            source, sheet
        )
        return {
            "schema": "reader_v1",
            "model": self.name,
            "provider": self.provider,
            "seconds": round(time.perf_counter() - started, 4),
            "extracted": extracted.model_dump(mode="json", by_alias=True),
        }


def _route(path: str) -> str:
    """The path without query or trailing slash (Verda's gateway forwards `/read?`)."""
    return urlsplit(path).path.rstrip("/")


def handler(reader: Reader) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, status: int, body: dict) -> None:
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            if _route(self.path) in ("/health", ""):
                self._send(200, {"status": "ok", "model": reader.name,
                                 "provider": reader.provider, "load_s": reader.load_s})  # fmt: skip
            else:
                self._send(404, {"error": f"no route {self.path}"})

        def do_POST(self) -> None:
            if _route(self.path) != "/read":
                self._send(404, {"error": f"no route {self.path}"})
                return
            size = int(self.headers.get("Content-Length") or 0)
            if not 0 < size <= MAX_BYTES:
                self._send(413 if size else 400, {"error": f"body of {size} bytes"})
                return
            data = self.rfile.read(size)
            try:
                self._send(200, reader.read(data))
            except ValueError as error:
                self._send(400, {"error": str(error)})

        def log_message(self, format: str, *args) -> None:
            if _route(self.path) != "/health":  # Verda probes it every second
                sys.stderr.write(f"{self.command} {self.path} {args[1] if len(args) > 1 else ''}\n")

    return Handler


def main() -> None:
    reader = Reader(Path(os.environ.get("READER_MODEL", "/opt/reader/model")))
    print(f"reader {reader.name} on {reader.provider}, loaded in {reader.load_s} s", flush=True)
    port = int(os.environ.get("PORT", "8000"))
    HTTPServer(("0.0.0.0", port), handler(reader)).serve_forever()


if __name__ == "__main__":
    main()
