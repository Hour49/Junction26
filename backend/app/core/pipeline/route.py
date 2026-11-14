"""Stage 5: pick the richest source of a group and record it.

The order is model, then CAD, then vector, then raster (requirement I4), among the routes that
have a reader: a route whose reader reads nothing (a hello-world adapter) never takes a drawing
away from one that reads it, e.g. a swiss plan's DXF from its PDF while there is no CAD reader.
A scanned PDF (its page is an image, with no drawn content: `scanned`) is a raster source.
"""

from collections.abc import Collection

from app.core.pipeline.model import DrawingFile, DrawingGroup, FileKind, Route, Routed

ROUTE_OF_KIND: dict[FileKind, Route] = {
    "ifc": "bim",
    "dxf": "cad",
    "pdf": "vector",
    "svg": "vector",
    "png": "raster",
    "jpeg": "raster",
}
RICHEST_FIRST: tuple[Route, ...] = ("bim", "cad", "vector", "raster")


def route(
    group: DrawingGroup,
    readable: Collection[Route] = RICHEST_FIRST,
    scanned: Collection[str] = (),
) -> Routed:
    """The first file of the richest route present in the group whose reader reads something
    (`readable`). A group with no file on such a route keeps its richest route: its sheet still
    gets a drawing model, which says nothing was read. `scanned`: the paths of scanned PDFs,
    which the raster route reads."""

    def route_of(file: DrawingFile) -> Route:
        return "raster" if file.path in scanned else ROUTE_OF_KIND[file.kind]

    def rank(file: DrawingFile) -> tuple[bool, int]:
        found = route_of(file)
        return found not in readable, RICHEST_FIRST.index(found)

    source = min(group.files, key=rank)
    return Routed(route=route_of(source), source=source)
