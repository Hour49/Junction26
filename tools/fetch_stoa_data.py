#!/usr/bin/env python3
"""Download and unzip the Stoa challenge datasets into data/stoa/ (gitignored). Stdlib only.

Usage: python3 tools/fetch_stoa_data.py [preview|full|all]    (default: preview)

The links come from the environment or this clone's .env (STOA_PREVIEW_URL, STOA_FULL_URL), so the partner's
links stay out of this public repo. Downloads resume after an interruption, the file size must match the server's,
there must be room for the zip and its contents, and extraction refuses any entry that would land outside the
target folder. Layout: data/README.md. Tests: tools/test_fetch_stoa_data.py.
"""
import os
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "stoa"
SETS = {"preview": "STOA_PREVIEW_URL", "full": "STOA_FULL_URL"}
CHUNK = 1 << 20


def env_value(name, env_file=ROOT / ".env"):
    if os.environ.get(name):
        return os.environ[name]
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == name:
                return value.strip().strip("\"'")
    return None


def check_space(folder, needed):
    free = shutil.disk_usage(folder).free
    if free < needed:
        raise SystemExit(f"not enough disk space in {folder}: {free / 1e9:.1f} GB free, "
                         f"{needed / 1e9:.1f} GB needed (the zip plus its contents)")


def download(url, dest):
    """Fetch url into dest, resuming a partial file. Returns the size in bytes."""
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")) as head:
        total = int(head.headers["Content-Length"])
    have = dest.stat().st_size if dest.exists() else 0
    if have == total:
        print(f"{dest.name}: already downloaded ({total / 1e9:.2f} GB)")
        return total
    if have > total:
        have = 0
    check_space(dest.parent, (total - have) + total)  # the rest of the zip, then roughly its contents
    request = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(request) as response:
        resumed = have > 0 and response.status == 206
        done = have if resumed else 0
        with dest.open("ab" if resumed else "wb") as out:
            next_report = done + total // 20
            while chunk := response.read(CHUNK):
                out.write(chunk)
                done += len(chunk)
                if done >= next_report:
                    print(f"{dest.name}: {done / 1e9:.2f} / {total / 1e9:.2f} GB", flush=True)
                    next_report += total // 20
    size = dest.stat().st_size
    if size != total:
        raise SystemExit(f"{dest.name}: got {size} bytes, expected {total}; rerun to resume")
    return total


def safe_extract(zip_path, target):
    """Unzip into target via a temporary sibling folder; refuse entries that escape it."""
    if target.exists():
        print(f"{target}: already extracted (delete the folder to extract again)")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        check_space(target.parent, sum(info.file_size for info in archive.infolist()))
    partial = target.with_name(target.name + ".partial")
    if partial.exists():
        shutil.rmtree(partial)  # our own unfinished extraction from an earlier run
    partial.mkdir(parents=True)
    base = partial.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if not (base / info.filename).resolve().is_relative_to(base):
                shutil.rmtree(partial)
                raise SystemExit(f"{zip_path.name}: refusing entry {info.filename!r} (outside the target)")
        archive.extractall(partial)
    partial.rename(target)
    print(f"{target}: extracted")


def fetch(name):
    url = env_value(SETS[name])
    if not url:
        raise SystemExit(f"{SETS[name]} is not set: add it to .env (link from the Stoa challenge brief)")
    downloads = DATA / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    zip_path = downloads / Path(url).name
    download(url, zip_path)
    safe_extract(zip_path, DATA / name)


def main(argv):
    choice = argv[1] if len(argv) > 1 else "preview"
    if choice not in (*SETS, "all"):
        raise SystemExit(__doc__)
    for name in SETS if choice == "all" else (choice,):
        fetch(name)


if __name__ == "__main__":
    main(sys.argv)
