"""Stages 1-2: the inventory, one entry per file with its sha256.

Hello world: the hash is recorded and nothing looks it up yet. Reusing the stored drawing model
of a file seen before, and unpacking archives, come later.
"""

import hashlib

from app.core.pipeline.model import FileEntry


def file_entry(path: str, data: bytes) -> FileEntry:
    return FileEntry(path=path, size=len(data), sha256=hashlib.sha256(data).hexdigest())
