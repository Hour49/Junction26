"""Stage 4: the files of one drawing become one group.

Files in the same folder with the same name (any extension) are one drawing, e.g. a swiss plan
as PDF, PNG and DXF. An IFC model and its sheet PDFs have different names, so a name does not
pair them: the sources a `SourceFinder` found for a file join that file's group, and one model
is in the group of each of its sheets.
"""

from collections.abc import Iterable, Mapping, Sequence
from pathlib import PurePosixPath

from app.core.pipeline.model import DrawingFile, DrawingGroup


def key_of(file: DrawingFile) -> str:
    """The group a file is in by its own name: its path without the extension."""
    return str(PurePosixPath(file.path).with_suffix(""))


def group(
    files: Iterable[DrawingFile], sources: Mapping[str, Sequence[DrawingFile]]
) -> list[DrawingGroup]:
    """Groups in the order their first file came, each with its files in the order given and
    then the sources found for them (`sources`: by the path of the file they were found for).
    A found source is in the group to be read from: its own group is the one `key_of` names."""
    members: dict[str, list[DrawingFile]] = {}
    for file in files:
        members.setdefault(key_of(file), []).append(file)
    for found in members.values():
        for file in tuple(found):
            found += [source for source in sources.get(file.path, ()) if source not in found]
    return [DrawingGroup(key=key, files=tuple(found)) for key, found in members.items()]
