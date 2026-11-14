"""The no-keys demo archive: a small project drawn by code, so no partner data is in the repo.

    cd backend && uv run python scripts/make_sample_archive.py [--out <zip>]

The default out is data/samples/sample-project.zip (gitignored).

What is in it, and what ingest should make of each file (tests/ingest checks it):

    plans/flat-a.pdf          a drawn plan in the swiss style: the vector reader reads its rooms,
                              doors, windows and fixtures at 1:100              -> ready
    plans/flat-a.png          the same sheet as an image: grouped with the PDF, read from it
                                                                                -> ready
    plans/flat-b.pdf          a drawn plan whose printed room area disagrees with the drawn
                              outline: the second count finds it              -> flagged
                              Its bedroom ("Zimmer 1.05") is 8.06 m2, drawn and printed alike:
                              it passes the Finnish pack (at least 7 m2) and fails the Zürich
                              one (at least 10 m2), the demo's one failed rule
    scans/ground-floor.png    a plan as an image only: the raster route        -> flagged until
                              a raster reader is plugged in (EXTRACTOR_RASTER)
    scans/ground-floor-copy.png  the same bytes again: not ingested twice     -> reused
    photos/plan-photo.jpg     a phone photo of that plan (perspective, table, EXIF) -> flagged
    photos/site.jpg           a phone photo of a site, not a drawing          -> set aside
    model/house.ifc           a small IFC model: walls, spaces, doors, windows -> ready
    cad/detail.dxf            a DXF with no sheet next to it                   -> set aside
    docs/specification.pdf    a text document                                  -> text only
    docs/notes.txt            plain text                                       -> text only

Everything is deterministic: the same bytes on every run, so the hash cache sees them as one.
"""

import argparse
import ctypes
import io
import math
import random
import re
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.guid
import pypdfium2
from PIL import Image, ImageDraw, ImageFilter
from pypdfium2 import raw

Point = tuple[float, float]
Rgb = tuple[int, int, int]
BLACK: Rgb = (0, 0, 0)
WHITE: Rgb = (255, 255, 255)
GREY, DOOR_GREY, RED = (138, 138, 138), (68, 68, 68), (176, 58, 46)
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "data" / "samples" / "sample-project.zip"
ZIP_TIME = (2026, 11, 14, 0, 0, 0)


# --------------------------------------------------------------------------- vector PDF sheets


def rect(x0: float, y0: float, x1: float, y1: float) -> list[Point]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def ring(cx: float, cy: float, radius: float, points: int) -> list[Point]:
    turn = 2 * math.pi / (points - 1)
    return [
        (cx + radius * math.cos(turn * at), cy + radius * math.sin(turn * at))
        for at in range(points - 1)
    ] + [(cx + radius, cy)]


class SheetPdf:
    """One page, drawn in points from the top left (y down), as tests/pdf_sheets.py does."""

    def __init__(self, width: float = 600, height: float = 400) -> None:
        self.width, self.height = width, height
        self._document = pypdfium2.PdfDocument.new()
        self._page = self._document.new_page(width, height)

    def path(
        self, points: Sequence[Point], stroke: Rgb | None = BLACK, width: float = 1.0,
        fill: Rgb | None = None,
    ) -> None:  # fmt: skip
        obj = raw.FPDFPageObj_CreateNewPath(points[0][0], self.height - points[0][1])
        for x, y in points[1:]:
            raw.FPDFPath_LineTo(obj, x, self.height - y)
        if stroke is not None:
            raw.FPDFPageObj_SetStrokeColor(obj, *stroke, 255)
            raw.FPDFPageObj_SetStrokeWidth(obj, width)
        mode = raw.FPDF_FILLMODE_NONE
        if fill is not None:
            raw.FPDFPageObj_SetFillColor(obj, *fill, 255)
            mode = raw.FPDF_FILLMODE_WINDING
        raw.FPDFPath_SetDrawMode(obj, mode, stroke is not None)
        raw.FPDFPage_InsertObject(self._page.raw, obj)

    def text(self, text: str, x: float, y: float, size: float = 6.0) -> None:
        obj = raw.FPDFPageObj_NewTextObj(self._document.raw, b"Helvetica", size)
        encoded = (text + "\x00").encode("utf-16-le")
        buffer = ctypes.create_string_buffer(encoded, len(encoded))
        raw.FPDFText_SetText(obj, ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ushort)))
        raw.FPDFPageObj_Transform(obj, 1, 0, 0, 1, x, self.height - y)
        raw.FPDFPage_InsertObject(self._page.raw, obj)

    def pdf(self) -> bytes:
        raw.FPDFPage_GenerateContent(self._page.raw)
        buffer = io.BytesIO()
        self._document.save(buffer)
        return _fixed(buffer.getvalue())

    def png(self, scale: int = 2) -> bytes:
        document = pypdfium2.PdfDocument(self.pdf())
        try:
            image = document[0].render(scale=scale).to_pil()
        finally:
            document.close()
        return png_bytes(image)


def _fixed(pdf: bytes) -> bytes:
    """pdfium writes the time and a random file ID: both become fixed, at the same length, so
    the cross-reference offsets stay right and the bytes are the same on every run."""
    pdf = re.sub(rb"/CreationDate\(D:[^)]*\)", b"/CreationDate(D:20261114000000+00'00')", pdf)
    return re.sub(
        rb"/ID\[<[0-9A-F]{32}><[0-9A-F]{32}>\]",
        b"/ID[<" + b"0" * 32 + b"><" + b"0" * 32 + b">]",
        pdf,
    )


def swiss_room(
    sheet: SheetPdf, box: tuple[float, float, float, float], *lines: str, fill: int = 255
) -> None:
    """A room outline with its label lines (name, number, printed area) written inside."""
    sheet.path(rect(*box), stroke=GREY, width=0.37, fill=(fill, fill, fill))
    for at, line in enumerate(lines):
        sheet.text(line, box[0] + 4, box[1] + 10 + 8 * at)


def swiss_window(sheet: SheetPdf, x0: float, y0: float, x1: float, y1: float) -> None:
    sheet.path(rect(x0, y0, x1, y1), width=0.51, fill=WHITE)
    for y in (y0 + 1, y1 - 1):
        sheet.path([(x0, y), (x1, y)], width=0.37)


def flat_sheet(
    kitchen_area: str, room_bottom: float = 150, room_area: str = "14.94 m²"
) -> SheetPdf:
    """A two-room flat with a bathroom and balcony at 1:100. A kitchen of 200 x 100 pt less the
    50 x 40 pt store inside it is 22.40 m2; another printed value is a conflict. The room (a
    bedroom) is 120 pt wide from y 50 to `room_bottom`, printed `room_area`."""
    sheet = SheetPdf(600, 400)
    swiss_room(sheet, (100, 50, 300, 150), "Küche", "1.01", kitchen_area)
    swiss_room(sheet, (150, 80, 200, 120), "Reduit", "1.02", "2.49 m²")
    swiss_room(sheet, (300, 50, 400, 150), "Bad", "1.03", "12.45 m²")
    swiss_room(sheet, (100, 150, 300, 200), "Balkon", "1.04", "12.45 m²", fill=228)
    swiss_room(sheet, (400, 50, 520, room_bottom), "Zimmer", "1.05", room_area)
    sheet.text("Whg. A", 104, 142)
    sheet.path(rect(98, 48, 522, 202), stroke=RED, width=1.28)
    for x in (296, 396):  # doors
        sheet.path(rect(x, 90, x + 8, 110), stroke=DOOR_GREY, width=0.37)
    swiss_window(sheet, 120, 46, 180, 52)
    swiss_window(sheet, 430, 46, 490, 52)
    sheet.path(ring(320, 70, 6, 48), width=0.51)  # toilet: basin outline with its tank line
    sheet.path([(316, 62), (324, 62)], width=0.51)
    sheet.path(ring(340, 70, 6, 48), width=0.51)  # washbasin
    sheet.path(ring(360, 120, 10, 69), width=0.51)  # bathtub
    sheet.text("Massstab 1:100 (A3)", 450, 380)
    return sheet


def text_pdf() -> bytes:
    """A specification: lines of text and no drawing."""
    sheet = SheetPdf(595, 842)
    words = "The contractor shall supply and fit all doors and windows to the schedule"
    words = words.split(" ")
    for line in range(60):
        sheet.text(" ".join(words[line % 5 :] + words[: line % 5]), 50, 60 + 12 * line, size=9)
    return sheet.pdf()


# --------------------------------------------------------------------------- raster plans, photos


def raster_plan() -> Image.Image:
    """A scanned-looking plan: walls, door swings and room names on white paper."""
    image = Image.new("RGB", (1200, 850), WHITE)
    draw = ImageDraw.Draw(image)
    walls = [(100, 100, 1100, 750), (100, 100, 600, 450), (600, 100, 1100, 450)]
    for box in walls:
        draw.rectangle(box, outline=BLACK, width=8)
    for x, y in ((330, 450), (830, 450)):  # door openings with their swing
        draw.rectangle((x, y - 5, x + 80, y + 5), fill=WHITE)
        draw.arc((x - 80, y - 80, x + 80, y + 80), 270, 360, fill=BLACK, width=2)
    for x in (250, 750):  # windows in the top wall
        draw.rectangle((x, 94, x + 120, 106), fill=WHITE, outline=BLACK, width=2)
    for x, y, name in ((300, 270, "LIVING"), (800, 270, "BEDROOM"), (560, 600, "KITCHEN")):
        draw.text((x, y), name, fill=BLACK)
    return image


# Where the paper's corners land in the 1600 x 1200 photo: top left, top right, bottom right,
# bottom left. A rectifier that finds them undoes the photo (tests/ingest/test_ingest_frame.py).
PHOTO_CORNERS: tuple[Point, Point, Point, Point] = (
    (260, 220),
    (1330, 160),
    (1420, 1010),
    (180, 1060),
)
PHOTO_SIZE = (1600, 1200)


def corners_of(size: tuple[int, int]) -> tuple[Point, Point, Point, Point]:
    width, height = size
    return (0, 0), (width, 0), (width, height), (0, height)


def phone_photo(plan: Image.Image) -> Image.Image:
    """The plan on a wooden table, seen at an angle, lit unevenly, slightly out of focus."""
    width, height = PHOTO_SIZE
    table = Image.linear_gradient("L").resize((width, height)).convert("RGB")
    table = Image.blend(Image.new("RGB", (width, height), (120, 82, 50)), table, 0.25)
    corners = PHOTO_CORNERS
    warped = plan.transform((width, height), Image.Transform.PERSPECTIVE,
                            perspective(corners, corners_of(plan.size)), Image.Resampling.BICUBIC,
                            fillcolor=(0, 0, 0))  # fmt: skip
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).polygon(list(corners), fill=255)
    paper = Image.eval(warped, lambda level: int(level * 0.86))  # room light, not scanner white
    photo = Image.composite(paper, table, mask)
    light = Image.radial_gradient("L").resize((width, height)).convert("RGB")
    photo = Image.blend(photo, Image.eval(light, lambda level: 255 - level // 3), 0.12)
    return photo.filter(ImageFilter.GaussianBlur(1.2))


SKY = ((90, 4), (140, 5), (210, 8))  # red, green, blue: the lowest level and the step


def site_photo() -> Image.Image:
    """A sky, a building block and grass, with sensor noise: a photo that is not a drawing."""
    width, height = 1600, 1200
    sky = Image.linear_gradient("L").resize((width, height // 2))
    image = Image.new("RGB", (width, height), (70, 130, 60))
    tint = [sky.point([low + v // step for v in range(256)]) for low, step in SKY]
    image.paste(Image.merge("RGB", tint), (0, 0))
    ImageDraw.Draw(image).rectangle((500, 300, 1100, 800), fill=(150, 120, 100))
    grain = random.Random(0).randbytes(width * height)  # seeded: the same bytes every run
    noise = Image.frombytes("L", (width, height), grain).convert("RGB")
    return Image.blend(image, noise, 0.15)


def perspective(output: Sequence[Point], source: Sequence[Point]) -> tuple[float, ...]:
    """PIL's PERSPECTIVE coefficients that take each of the four `output` points (in the image
    being made) to the matching `source` point (in the image read from)."""
    rows: list[list[float]] = []
    values: list[float] = []
    for (x, y), (u, v) in zip(output, source, strict=True):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        values.append(u)
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        values.append(v)
    return tuple(_solve(rows, values))


def _solve(rows: list[list[float]], values: list[float]) -> list[float]:
    """Gauss-Jordan elimination with partial pivoting, for the 8x8 system above."""
    matrix = [[*row, value] for row, value in zip(rows, values, strict=True)]
    size = len(matrix)
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(matrix[row][column]))
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        for row in range(size):
            if row != column:
                factor = matrix[row][column] / matrix[column][column]
                matrix[row] = [
                    a - factor * b for a, b in zip(matrix[row], matrix[column], strict=True)
                ]
    return [matrix[row][size] / matrix[row][row] for row in range(size)]


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def jpeg_bytes(image: Image.Image) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "SyntheticPhone"  # Make
    exif[0x0110] = "Model 1"  # Model
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=82, exif=exif)
    return buffer.getvalue()


# --------------------------------------------------------------------------- the IFC model


class _Ifc:
    """A model with what the IFC reader looks at, with fixed GlobalIds and header time."""

    def __init__(self) -> None:
        self.file: Any = ifcopenshell.file(schema="IFC4")
        self._next = 0
        units = [
            self.new("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE"),
            self.new("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
            self.new("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE"),
        ]
        self.origin = self.new("IfcAxis2Placement3D", Location=self.point(0.0, 0.0, 0.0))
        self.context = self.new("IfcGeometricRepresentationContext", ContextType="Model",
                                CoordinateSpaceDimension=3, Precision=1e-5,
                                WorldCoordinateSystem=self.origin)  # fmt: skip
        self.project = self.rooted("IfcProject", Name="Sample house",
                                   UnitsInContext=self.new("IfcUnitAssignment", Units=units),
                                   RepresentationContexts=[self.context])  # fmt: skip

    def new(self, kind: str, **attrs: Any) -> Any:
        return self.file.create_entity(kind, **attrs)

    def rooted(self, kind: str, **attrs: Any) -> Any:
        self._next += 1
        guid = ifcopenshell.guid.compress(f"{self._next:032x}")
        return self.new(kind, GlobalId=guid, **attrs)

    def point(self, *metres: float) -> Any:
        return self.new("IfcCartesianPoint", Coordinates=metres)

    def element(self, kind: str, storey: Any, name: str, **quantities: float) -> None:
        element = self.rooted(kind, Name=name)
        self.rooted("IfcRelContainedInSpatialStructure", RelatingStructure=storey,
                    RelatedElements=[element])  # fmt: skip
        if quantities:
            stated = [
                self.new(f"IfcQuantity{unit}", Name=quantity, **{f"{unit}Value": value})
                for quantity, value in quantities.items()
                for unit in ("Length", "Area", "Volume")
                if quantity.endswith(unit)
            ]
            quantity_set = self.rooted(
                "IfcElementQuantity", Name="Qto_BaseQuantities", Quantities=stated
            )
            self.rooted("IfcRelDefinesByProperties", RelatedObjects=[element],
                        RelatingPropertyDefinition=quantity_set)  # fmt: skip

    def space(self, storey: Any, number: str, name: str, outline: list[Point]) -> None:
        curve = self.new(
            "IfcPolyline", Points=[self.point(x, y) for x, y in (*outline, outline[0])]
        )
        solid = self.new(
            "IfcExtrudedAreaSolid",
            SweptArea=self.new(
                "IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=curve
            ),
            Position=self.origin,
            ExtrudedDirection=self.new("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
            Depth=2.6,
        )
        shape = self.new("IfcProductDefinitionShape", Representations=[
            self.new("IfcShapeRepresentation", ContextOfItems=self.context,
                     RepresentationIdentifier="Body", RepresentationType="SweptSolid",
                     Items=[solid])])  # fmt: skip
        space = self.rooted("IfcSpace", Name=number, LongName=name, Representation=shape,
                            ObjectPlacement=self.new("IfcLocalPlacement",
                                                     RelativePlacement=self.origin))  # fmt: skip
        self.rooted("IfcRelAggregates", RelatingObject=storey, RelatedObjects=[space])

    def ifc(self) -> bytes:
        self.file.header.file_name.time_stamp = "2026-11-14T00:00:00"
        return self.file.to_string().encode()


def ifc_model() -> bytes:
    model = _Ifc()
    storey = model.rooted("IfcBuildingStorey", Name="Ground floor")
    model.rooted("IfcRelAggregates", RelatingObject=model.project, RelatedObjects=[storey])
    for at, length in enumerate((8.0, 6.0, 8.0, 6.0)):
        model.element("IfcWall", storey, f"Wall {at + 1}", Length=length,
                      NetSideArea=length * 2.6, NetVolume=length * 2.6 * 0.2)  # fmt: skip
    for at in range(2):
        model.element("IfcDoor", storey, f"Door {at + 1}")
    for at in range(3):
        model.element("IfcWindow", storey, f"Window {at + 1}")
    model.element("IfcSlab", storey, "Floor slab", NetVolume=8.0 * 6.0 * 0.25)
    model.space(storey, "0.01", "Living", [(0, 0), (5, 0), (5, 6), (0, 6)])
    model.space(storey, "0.02", "Kitchen", [(5, 0), (8, 0), (8, 6), (5, 6)])
    return model.ifc()


DXF = "0 SECTION 2 ENTITIES 0 LINE 8 WALLS 10 0.0 20 0.0 11 5.0 21 0.0 0 ENDSEC 0 EOF ".replace(
    " ", "\n"
)  # a DXF puts each group code and value on its own line
NOTES = "Site visit 2026-11-12: the client wants the balcony glazed. Drawings to follow.\n"


# --------------------------------------------------------------------------- the archive


def sample_files() -> dict[str, bytes]:
    flat_a = flat_sheet("22.40 m²")
    plan = raster_plan()
    plan_png = png_bytes(plan)
    return {
        "plans/flat-a.pdf": flat_a.pdf(),
        "plans/flat-a.png": flat_a.png(),
        # the kitchen's outline gives 22.40 m2; the bedroom is 4.23 x 1.91 m, printed as drawn
        "plans/flat-b.pdf": flat_sheet("30.00 m²", room_bottom=104, room_area="8.06 m²").pdf(),
        "scans/ground-floor.png": plan_png,
        "scans/ground-floor-copy.png": plan_png,
        "photos/plan-photo.jpg": jpeg_bytes(phone_photo(plan)),
        "photos/site.jpg": jpeg_bytes(site_photo()),
        "model/house.ifc": ifc_model(),
        "cad/detail.dxf": DXF.encode(),
        "docs/specification.pdf": text_pdf(),
        "docs/notes.txt": NOTES.encode(),
    }


def build_archive(files: dict[str, bytes] | None = None) -> bytes:
    """The sample project as zip bytes, with fixed entry times so the bytes never change."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in (files or sample_files()).items():
            archive.writestr(zipfile.ZipInfo(path, date_time=ZIP_TIME), data,
                             compress_type=zipfile.ZIP_DEFLATED)  # fmt: skip
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Writes the no-keys demo archive.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out: Path = parser.parse_args().out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_archive())
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
