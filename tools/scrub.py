#!/usr/bin/env python3
"""Find personal traces in the tracked files of this public repo (stdlib only).

Looks for home directories (/home/<name>, /Users/<name>, C:\\Users\\<name>) and Tailscale hostnames
(<machine>.ts.net). Prints `path:line: kind` for each hit, never the matched text, and exits 1 if
there is any. Placeholders such as /home/<user>/ and ~/ don't match. CI runs it in the tools job;
tests: tools/test_scrub.py.

Usage: python3 tools/scrub.py [repo dir, default: this repo]
"""
import re
import subprocess
import sys
from pathlib import Path

NAME = r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
KINDS = {
    # not after a word character, so a URL such as example.com/home/about isn't a hit
    "home path": re.compile(rf"(?<![\w.~-])/(home|Users)/{NAME}"),
    "Windows home path": re.compile(rf"\b[A-Za-z]:[\\/]Users[\\/]{NAME}", re.IGNORECASE),
    "Tailscale hostname": re.compile(r"\b[A-Za-z0-9-]+\.ts\.net\b"),
}


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    listed = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True,
                            text=True, check=True).stdout
    files = [name for name in listed.split("\0") if name]
    hits = 0
    for name in files:
        path = root / name
        if path.is_symlink() or not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", "replace")
        for lineno, line in enumerate(text.split("\n"), 1):
            for kind, pattern in KINDS.items():
                if pattern.search(line):
                    print(f"{name}:{lineno}: {kind}")
                    hits += 1
    if hits:
        print(f"scrub: {hits} personal trace(s) in tracked files. The repo is public: use a "
              "placeholder (~/, /home/<user>/, <machine>.ts.net).", file=sys.stderr)
        return 1
    print(f"scrub: {len(files)} tracked files, no home paths or tailnet hostnames")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
