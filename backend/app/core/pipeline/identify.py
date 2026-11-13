"""Stage 3: what a file is, from its content and never from its extension.

Hello world: every file in a drawing format counts as a drawing. Telling a photo, a text page or
a specification from a drawing comes later; those will be set aside here with a reason.
"""

from app.core.pipeline.model import DrawingFile, FileEntry, FileKind, SetAside

HEAD = 2048  # bytes looked at


def sniff(data: bytes) -> FileKind | None:
    """The drawing format `data` starts as, or None."""
    head = data[:HEAD]
    text = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if text.startswith(b"ISO-10303-21"):
        return "ifc"
    if text.startswith((b"<?xml", b"<svg", b"<!--", b"<!DOCTYPE svg")) and b"<svg" in head:
        return "svg"
    # An ASCII DXF opens with group code 0 and the value SECTION, each on its own line.
    if head.startswith(b"AutoCAD Binary DXF") or text.split()[:2] == [b"0", b"SECTION"]:
        return "dxf"
    return None


def identify(entry: FileEntry, data: bytes) -> DrawingFile | SetAside:
    kind = sniff(data)
    if kind is None:
        return SetAside(path=entry.path, reason="not a drawing format we read")
    return DrawingFile(path=entry.path, size=entry.size, sha256=entry.sha256, kind=kind)
