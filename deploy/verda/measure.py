"""Time hour49-reader: cold start, warm latency per sheet, throughput.

    python3 deploy/verda/measure.py --images <png>... [--warm 20] [--parallel 1]

The first request is sent when no replica runs (check with `verda_serve.py replicas`), so its
time is the cold start (replica start, bundle fetch, model load, first sheet). Then each image
is sent `--warm` times in turn, one at a time (latency) or `--parallel` at once (throughput).
Prints one JSON line per request (client seconds, server seconds, provider, element count) and a
summary. URL and inference key from the repo's .env (VERDA_READER_URL, VERDA_INFERENCE_API_KEY),
never printed. Standard library only.
"""

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import verda_serve


def post(url: str, key: str, data: bytes, timeout: float = 120) -> dict:
    request = urllib.request.Request(url + "/read", data=data, method="POST")
    request.add_header("Authorization", f"Bearer {key}")
    request.add_header("Content-Type", "application/octet-stream")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
            status = response.status
    except (TimeoutError, urllib.error.URLError) as error:
        if isinstance(error, urllib.error.HTTPError):
            return {"status": error.code, "error": error.read().decode()[:300],
                    "client_s": round(time.perf_counter() - started, 3)}  # fmt: skip
        return {"status": "timeout", "error": str(error)[:300],
                "client_s": round(time.perf_counter() - started, 3)}  # fmt: skip
    return {
        "status": status,
        "client_s": round(time.perf_counter() - started, 3),
        "server_s": body.get("seconds"),
        "provider": body.get("provider"),
        "model": body.get("model"),
        "elements": len(body["extracted"]["elements"]),
        "plans": len(body["extracted"]["plans"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--images", type=Path, nargs="+", required=True)
    parser.add_argument("--warm", type=int, default=20)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--no-cold", action="store_true")
    parser.add_argument("--timeout", type=float, default=120, help="seconds per warm request")
    args = parser.parse_args()
    env = verda_serve._env()
    url, key = env["VERDA_READER_URL"].rstrip("/"), env["VERDA_INFERENCE_API_KEY"]
    images = [path.read_bytes() for path in args.images]
    if not args.no_cold:
        print(json.dumps({"cold": True, **post(url, key, images[0], 600)}), flush=True)
    jobs = [images[i % len(images)] for i in range(args.warm)]
    started = time.perf_counter()
    with ThreadPoolExecutor(args.parallel) as pool:
        results = list(pool.map(lambda data: post(url, key, data, args.timeout), jobs))
    wall = time.perf_counter() - started
    for result in results:
        print(json.dumps(result))
    ok = [r for r in results if r["status"] == 200]
    client = [r["client_s"] for r in ok]
    server = [r["server_s"] for r in ok]
    summary = {
        "requests": len(results),
        "ok": len(ok),
        "parallel": args.parallel,
        "wall_s": round(wall, 2),
        "sheets_per_s": round(len(ok) / wall, 2) if wall else None,
    }
    if ok:
        summary |= {
            "client_median_s": round(statistics.median(client), 3),
            "client_p90_s": round(sorted(client)[int(0.9 * (len(client) - 1))], 3),
            "server_median_s": round(statistics.median(server), 3),
        }
    print(json.dumps({"summary": summary}))


if __name__ == "__main__":
    main()
