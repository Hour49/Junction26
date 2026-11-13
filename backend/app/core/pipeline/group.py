"""Stage 4: the files of one drawing become one group.

Hello world: files in the same folder with the same name (any extension) are one drawing, e.g. a
swiss plan as PDF, PNG and DXF. An IFC model and its sheet PDFs have different names and still
land in separate groups.
"""

from collections.abc import Iterable
from pathlib import PurePosixPath

from app.core.pipeline.model import DrawingFile, DrawingGroup


def group(files: Iterable[DrawingFile]) -> list[DrawingGroup]:
    """Groups in the order their first file came, each with its files in the order given."""
    members: dict[str, list[DrawingFile]] = {}
    for file in files:
        key = str(PurePosixPath(file.path).with_suffix(""))
        members.setdefault(key, []).append(file)
    return [DrawingGroup(key=key, files=tuple(found)) for key, found in members.items()]
