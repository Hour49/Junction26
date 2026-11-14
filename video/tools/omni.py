"""Generate one video take with Gemini Omni through the Interactions API.

Usage (from the repo root, key in the gitignored .env):

    set -a && . ./.env && set +a
    python3 -I video/tools/omni.py --take 002 --image video/media/source/s01_last_frame.png \
        --prompt-file video/script/prompts/s02_smash.txt

Writes into video/media/takes/<take>/: take.mp4 (or other returned media), prompt.txt, input
files, meta.json (response without the base64 payload: id, usage, timings). Appends one line to
video/media/takes/log.jsonl. Gemini Omni models only accept the Interactions API
(generateContent returns "This model only supports Interactions API", checked 2026-11-14).
"""

import argparse
import base64
import json
import mimetypes
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://generativelanguage.googleapis.com/v1beta/interactions"
VIDEO_DIR = Path(__file__).resolve().parents[1]
TAKES = VIDEO_DIR / "media" / "takes"


def call(url, key, body=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=900))
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:1500]}")


def media_parts(node):
    """Yield every dict in the response that carries a large base64 `data` payload."""
    if isinstance(node, dict):
        if isinstance(node.get("data"), str) and len(node["data"]) > 1000:
            yield node
        for v in node.values():
            yield from media_parts(v)
    elif isinstance(node, list):
        for v in node:
            yield from media_parts(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--take", required=True, help="take id, e.g. 002 (folder must not exist)")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--image", action="append", default=[], help="input image (repeatable)")
    ap.add_argument("--model", default="gemini-omni-1.2-flash")
    ap.add_argument("--modality", default="video")
    args = ap.parse_args()

    key = os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY not set (source .env)")
    out = TAKES / args.take
    if out.exists():
        sys.exit(f"{out} exists: pick a new take id")
    out.mkdir(parents=True)

    prompt = Path(args.prompt_file).read_text()
    (out / "prompt.txt").write_text(prompt)
    parts = []
    for i, img in enumerate(args.image, 1):
        mime = mimetypes.guess_type(img)[0] or "image/png"
        shutil.copy(img, out / f"input_{i}{Path(img).suffix}")
        data = base64.b64encode(Path(img).read_bytes()).decode()
        parts.append({"type": "image", "data": data, "mime_type": mime})
    parts.append({"type": "text", "text": prompt})

    body = {"model": args.model, "input": parts, "response_modalities": [args.modality]}
    t0 = time.time()
    d = call(BASE, key, body)
    while d.get("status") in ("in_progress", "queued", "running"):
        time.sleep(10)
        d = call(f"{BASE}/{d['id']}", key)
    secs = round(time.time() - t0)

    saved = []
    for n, p in enumerate(media_parts(d), 1):
        ext = (p.get("mime_type") or "application/bin").split("/")[-1]
        name = "take.mp4" if (n == 1 and ext == "mp4") else f"out_{n}.{ext}"
        (out / name).write_bytes(base64.b64decode(p.pop("data")))
        saved.append(name)

    meta = {"take": args.take, "model": args.model, "images": args.image,
            "prompt_file": args.prompt_file, "seconds": secs, "saved": saved, "response": d}
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    log = {k: meta[k] for k in ("take", "model", "images", "prompt_file", "seconds", "saved")}
    log.update(status=d.get("status"), usage=d.get("usage"), at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    with open(TAKES / "log.jsonl", "a") as f:
        f.write(json.dumps(log) + "\n")
    print(json.dumps(log, indent=2))
    if not saved:
        sys.exit("no media in response: see meta.json")


if __name__ == "__main__":
    main()
