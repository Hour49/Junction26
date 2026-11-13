"""Joining a path that came from outside (a dataset row, a drawing's `file`) onto our folder."""

from pathlib import Path

from app.core.errors import InvalidInputError


def inside(root: Path, relative: str) -> Path:
    """`root / relative`, refused when it would land outside `root` (`..`, an absolute path)."""
    base = root.resolve()
    target = (base / relative).resolve()
    if not target.is_relative_to(base) or target == base:
        raise InvalidInputError(f"{relative!r} is not a path inside {root}")
    return target
