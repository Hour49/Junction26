"""Stage 5: pick the richest source of a group and record it.

The order is model, then CAD, then vector, then raster (requirement I4). Hello world: the route
follows the file format alone, so a scanned PDF still counts as vector.
"""

from app.core.pipeline.model import DrawingGroup, FileKind, Route, Routed

ROUTE_OF_KIND: dict[FileKind, Route] = {
    "ifc": "bim",
    "dxf": "cad",
    "pdf": "vector",
    "svg": "vector",
    "png": "raster",
    "jpeg": "raster",
}
RICHEST_FIRST: tuple[Route, ...] = ("bim", "cad", "vector", "raster")


def route(group: DrawingGroup) -> Routed:
    """The first file of the richest route present in the group."""
    source = min(group.files, key=lambda file: RICHEST_FIRST.index(ROUTE_OF_KIND[file.kind]))
    return Routed(route=ROUTE_OF_KIND[source.kind], source=source)
