"""Verda serverless deployment `hour49-reader`: the raster reader as a scale-to-zero GPU endpoint.

    python3 deploy/verda/verda_serve.py resources | creds | list | balance | status | replicas
    python3 deploy/verda/verda_serve.py create [--image <ref> --creds <name>] [--compute L40S]
    python3 deploy/verda/verda_serve.py scale --max 0|1|2      # 0: pause (no replica, no cost)
    python3 deploy/verda/verda_serve.py logs | restart | delete

Reads VERDA_CLIENT_ID and VERDA_CLIENT_SECRET from the repo's .env (never printed, never logged).
The endpoint (https://containers.datacrunch.io/hour49-reader) takes the inference key as a bearer
token. Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.datacrunch.io/v1"
ENV = Path(__file__).resolve().parents[2] / ".env"
NAME = "hour49-reader"
PORT = 8000


def _env() -> dict[str, str]:
    values = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("'\"")
    return values


def _call(method: str, path: str, token: str | None = None, body: dict | None = None):
    request = urllib.request.Request(API + path, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(request, data=data, timeout=60) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as error:
        raise SystemExit(
            f"{method} {path}: HTTP {error.code} {error.read().decode()[:800]}"
        ) from None
    try:
        return json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return raw


def token() -> str:
    env = _env()
    reply = _call(
        "POST",
        "/oauth2/token",
        body={
            "grant_type": "client_credentials",
            "client_id": env["VERDA_CLIENT_ID"],
            "client_secret": env["VERDA_CLIENT_SECRET"],
        },
    )
    return reply["access_token"]


BOOT = Path(__file__).with_name("boot.sh")
STOCK = "docker.io/library/python:3.13-slim"
BOOT_SECRET = "hour49-reader-boot"


def deployment(image: str, compute: str, creds: str | None, max_replicas: int) -> dict:
    """Scale to zero after 5 idle minutes, at most `max_replicas`, one request per replica at a
    time (the model reads one sheet at a time), on-demand. On the stock image the container
    runs boot.sh, which fetches the bundles through the two secret links (bundle.py)."""
    registry: dict = {"is_private": creds is not None}
    if creds is not None:
        registry["credentials"] = {"name": creds}
    container: dict = {
        "image": image,
        "exposed_port": PORT,
        "healthcheck": {"enabled": True, "port": PORT, "path": "/health"},
        "entrypoint_overrides": {"enabled": False},
        "env": [],
        "volume_mounts": [],
    }
    if image == STOCK:
        # boot.sh comes in as a file secret: every argument and env value is capped at 253 chars
        container["entrypoint_overrides"] = {
            "enabled": True,
            "entrypoint": ["sh"],
            "cmd": ["/boot/boot.sh"],
        }
        container["volume_mounts"] = [
            {"type": "secret", "mount_path": "/boot", "secret_name": BOOT_SECRET},
        ]
        container["env"] = [
            {"name": "READER_DEPS_URL", "value_or_reference_to_secret": "hour49-reader-deps-url",
             "type": "secret"},
            {"name": "READER_APP_URL", "value_or_reference_to_secret": "hour49-reader-app-url",
             "type": "secret"},
        ]  # fmt: skip
    return {
        "name": NAME,
        "is_spot": False,
        "compute": {"name": compute, "size": 1},
        "container_registry_settings": registry,
        "containers": [container],
        "scaling": {
            "min_replica_count": 0,
            "max_replica_count": max_replicas,
            "scale_down_policy": {"delay_seconds": 300},
            "scale_up_policy": {"delay_seconds": 0},
            "queue_message_ttl_seconds": 300,
            "concurrent_requests_per_replica": 1,
            "scaling_triggers": {"queue_load": {"threshold": 1}},
        },
    }


def upload_boot(auth: str) -> None:
    """boot.sh as the file secret the stock image mounts at /boot (replaced if it exists)."""
    if BOOT_SECRET in {item["name"] for item in _call("GET", "/file-secrets", auth) or []}:
        _call("DELETE", f"/file-secrets/{BOOT_SECRET}", auth)
    content = base64.b64encode(BOOT.read_bytes()).decode()
    files = [{"file_name": "boot.sh", "base64_content": content}]
    _call("POST", "/file-secrets", auth, {"name": BOOT_SECRET, "files": files})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("resources", "creds", "list", "balance", "status", "replicas", "logs", "delete",
                 "restart"):  # fmt: skip
        sub.add_parser(name)
    sub.add_parser("raw").add_argument("path")
    create = sub.add_parser("create")
    create.add_argument("--image", default=STOCK)
    create.add_argument("--compute", default="L40S")
    create.add_argument("--creds")
    create.add_argument("--max", type=int, default=1, choices=(1, 2))
    scale = sub.add_parser("scale")
    scale.add_argument("--max", type=int, required=True, choices=(0, 1, 2))
    args = parser.parse_args()
    auth = token()
    one = f"/container-deployments/{NAME}"

    if args.cmd == "resources":
        for item in _call("GET", "/serverless-compute-resources", auth):
            print(json.dumps(item))
    elif args.cmd == "creds":
        for item in _call("GET", "/container-registry-credentials", auth):
            print(item.get("name"), item.get("type"), item.get("created_at"))
    elif args.cmd == "list":
        for item in _call("GET", "/container-deployments", auth):
            print(item["name"], item.get("compute"), item.get("endpoint_base_url"))
    elif args.cmd == "balance":
        print(json.dumps(_call("GET", "/balance", auth)))
    elif args.cmd == "status":
        print(json.dumps(_call("GET", one + "/status", auth)))
    elif args.cmd == "replicas":
        print(json.dumps(_call("GET", one + "/replicas", auth)))
    elif args.cmd == "logs":
        print(json.dumps(_call("GET", one + "/logs", auth))[:20000])
    elif args.cmd == "raw":
        print(json.dumps(_call("GET", args.path, auth))[:20000])
    elif args.cmd == "create":
        if args.image == STOCK:
            upload_boot(auth)
        made = _call("POST", "/container-deployments", auth,
                     deployment(args.image, args.compute, args.creds, args.max))  # fmt: skip
        print(made.get("name"), made.get("endpoint_base_url"))
    elif args.cmd == "scale":
        if args.max == 0:
            _call("POST", one + "/pause", auth)
            print("paused")
            return
        current = _call("GET", one + "/scaling", auth)
        current["max_replica_count"] = args.max
        current["min_replica_count"] = 0
        _call("PATCH", one + "/scaling", auth, current)
        status = _call("GET", one + "/status", auth)
        if isinstance(status, dict) and status.get("status") == "paused":
            _call("POST", one + "/resume", auth)
        print("max replicas", args.max)
    elif args.cmd == "restart":
        _call("POST", one + "/restart", auth)
        print("restarted (replicas start again with the current bundles)")
    elif args.cmd == "delete":
        _call("DELETE", one, auth)
        print("deleted", NAME)
    else:
        sys.exit(f"unknown command {args.cmd}")


if __name__ == "__main__":
    main()
