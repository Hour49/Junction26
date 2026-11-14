"""Writing a file whole: to a temporary name of this writer (process and thread), then a rename,
so a reader never sees half a file and two writers of one file never take each other's temporary
file."""

import os
import threading
from pathlib import Path


def write_whole(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
