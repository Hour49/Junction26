"""Pack and upload the two bundles hour49-reader boots from, and hand their links to Verda.

    uv run --no-project --with boto3 python deploy/verda/bundle.py [--model <folder>] [--deps]

- deps.tar.gz: the Python packages (onnxruntime-gpu with its CUDA 12 and cuDNN wheels, numpy,
  pillow, pydantic) for python:3.13-slim, from data/models/serve/build/site (built by --deps).
- app.tar.gz: server.py, the backend's `app` package and the model folder (model.onnx and its
  JSON configs: model.json, detector.json or thresholds.json) as model/<its name>/.

Both go to the private bucket hour49-reader-bundles (Verda object storage, FIN-03). Each gets a
7-day presigned GET link, stored as the Verda secret hour49-reader-deps-url / -app-url, which the
deployment passes to boot.sh as READER_DEPS_URL / READER_APP_URL. Keys come from the repo's .env
and are never printed; the links are never printed either.
"""

import argparse
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import verda_serve

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "data/models/serve/build"
BUCKET = "hour49-reader-bundles"
ENDPOINT = "https://objects.eu-north-3.verda.storage"
WEEK = 7 * 24 * 3600
DEPS = [
    # CUDA 12, not 13: some of Verda's L40S nodes have a driver older than CUDA 13 (seen
    # 2026-11-14: "CUDA driver version is insufficient"); 1.26 is the last CUDA 12 release on PyPI
    "onnxruntime-gpu[cuda,cudnn]==1.26.0",
    "nvidia-cublas-cu12",
    "numpy==2.5.4",
    "pillow==13.0.0",
    "pydantic==2.14.3",
]


def s3():
    import boto3
    from botocore.config import Config

    env = verda_serve._env()
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name="eu-north-3",
        aws_access_key_id=env["VERDA_S3_ACCESS_KEY"],
        aws_secret_access_key=env["VERDA_S3_SECRET_KEY"],
        config=Config(
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def build_deps() -> Path:
    site = BUILD / "site"
    if not site.is_dir():
        subprocess.run(
            ["uv", "pip", "install", "--quiet", "--target", str(site), "--python-version", "3.13",
             "--python-platform", "x86_64-manylinux_2_28", "--only-binary", ":all:", *DEPS],
            check=True,
        )  # fmt: skip
    out = BUILD / "deps.tar.gz"
    # pigz when there is one: the bundle is 2.5 GB unpacked
    subprocess.run(
        f"tar -C {BUILD} -cf - site | (pigz -6 2>/dev/null || gzip -6) > {out}",
        shell=True,
        check=True,
    )
    return out


def build_app(model: Path) -> Path:
    if not (model / "model.onnx").is_file() or not (model / "model.json").is_file():
        sys.exit(f"{model} needs model.onnx and model.json (core's export)")
    out = BUILD / "app.tar.gz"
    skip = lambda info: None if "__pycache__" in info.name else info
    with tarfile.open(out, "w:gz", compresslevel=6) as tar:
        tar.add(Path(__file__).parent / "server.py", "server.py")
        tar.add(ROOT / "backend/app", "app", filter=skip)
        tar.add((model / "model.onnx").resolve(), f"model/{model.name}/model.onnx")
        # model.json, detector.json and thresholds.json: whatever load_config reads
        for config in sorted(model.glob("*.json")):
            tar.add(config, f"model/{model.name}/{config.name}")
    return out


def ensure_bucket(auth: str) -> None:
    names = [b.get("name") or b.get("bucket_name") for b in verda_serve._call(
        "GET", "/object-storage/buckets", auth) or []]  # fmt: skip
    if BUCKET not in names:
        verda_serve._call("POST", "/object-storage/buckets", auth,
                          {"bucket_name": BUCKET, "location_code": "FIN-03"})  # fmt: skip
        print("created bucket", BUCKET)


def put_secret(auth: str, name: str, value: str) -> None:
    existing = {s["name"] for s in verda_serve._call("GET", "/secrets", auth) or []}
    if name in existing:
        verda_serve._call("DELETE", f"/secrets/{name}?force=true", auth)
    verda_serve._call("POST", "/secrets", auth, {"name": name, "value": value})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", type=Path, default=ROOT / "data/models/serve/pilot-rfdetr-s")
    parser.add_argument("--deps", action="store_true", help="also pack and upload deps.tar.gz")
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    auth = verda_serve.token()
    ensure_bucket(auth)
    client = s3()
    parts = [("app", build_app(args.model))]
    if args.deps:
        parts.insert(0, ("deps", build_deps()))
    for part, path in parts:
        key = path.name
        client.upload_file(str(path), BUCKET, key)
        print(f"uploaded {key}: {path.stat().st_size / 1e6:.0f} MB")
        link = client.generate_presigned_url(
            "get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=WEEK
        )
        put_secret(auth, f"hour49-reader-{part}-url", link)
        print(f"secret hour49-reader-{part}-url set (link valid 7 days)")


if __name__ == "__main__":
    main()
