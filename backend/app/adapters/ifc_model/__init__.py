"""`EXTRACTOR_BIM=ifc`: the model route's `Extractor`, for a plan sheet whose group holds the IFC
building model it was rendered from.

The model says what every object is: its class, its storey, its GlobalId, and for walls and
slabs the file's own quantities (objects.py). The sheet's SVG twin, the same drawing with every
shape tagged by GlobalId, says where each object is drawn (svg.py). The sheet's own PDF gives the
scale and the title, read as the vector route reads them. sheet.py puts the three together.

So columns, stairs, railings, slabs and beams, which the PDF draws in styles it shares between
classes, are told apart here, and a room knows its number, its names and its storey. What the
sheet does not draw is no element: it has no place on the page (see sheet.py). It is in the
drawing's `model_objects`, which lists every object of the model, of every storey, with its
quantities and, when the sheet draws it, the element or room it is drawn as.

A model file that is asked about itself has no page. Ingest then hands it over as its own sheet,
without pages, and the extractor gives its `model_objects` and nothing drawn.

Without the twin there is nothing to place the model's objects with, and the extractor says so
and reads nothing. app/adapters/dataset_files.py pairs a sheet with its model only when the twin
is there, so such a sheet stays on the vector route.

`SECOND_COUNTER=ifc` is `IfcSecondCounter`: for ingest stage 8, what the model lists on the
sheet's storey, per element class and for rooms. The extraction's side is what the sheet draws.
It also passes on what the sheet's own PDF says a second time (its scale bar), and a sheet that
has no model goes to that counter alone.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.adapters.ifc_model.objects import CLASSES, IfcObject, Model, read_model
from app.adapters.ifc_model.sheet import SheetReading, read_sheet
from app.adapters.ifc_model.svg import read_svg
from app.adapters.vector_pdf.ifc_render import STOREY
from app.adapters.vector_pdf.objects import read_page
from app.adapters.vector_pdf.scale import read_scale
from app.core.drawing.model import (
    Attr,
    MeasuredValue,
    ModelClass,
    ModelObject,
    ReadClass,
    Scale,
    Subject,
)
from app.core.errors import NotFoundError
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, Sheet
from app.core.pipeline.ports import DrawingFiles, SecondCounter

SAME_SHAPE = 0.01  # relative difference of width / height between the SVG frame and the page
LOOKS_FOR: tuple[ReadClass, ...] = ("room", *CLASSES.values())
MODELS_KEPT = 8


class IfcModels:
    """Parsed models by content hash: the sheets of one building read its model once. Only the
    plain objects are kept (objects.py), not the parsed file."""

    def __init__(self, files: DrawingFiles) -> None:
        self._files = files
        self._models: dict[str, Model] = {}

    def model(self, source: DrawingFile) -> Model:
        if source.sha256 not in self._models:
            if len(self._models) >= MODELS_KEPT:
                del self._models[next(iter(self._models))]
            self._models[source.sha256] = read_model(self._files.read(source.path))
        return self._models[source.sha256]


@dataclass(frozen=True)
class _Read:
    model: Model
    reading: SheetReading
    scale: Scale
    notes: tuple[str, ...]


class IfcModelExtractor:
    def __init__(self, files: DrawingFiles, models: IfcModels) -> None:
        self._files, self._models = files, models

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        if source.kind == "ifc" and not sheet.pages:  # the model itself is asked about
            return Extracted(
                method="ifc_model",
                scale=Scale(status="no_scale"),
                read=LOOKS_FOR,
                model_objects=_listed(self._models.model(source), {}),
            )
        read = _read(self._files, self._models, source, sheet)
        if isinstance(read, str):
            return Extracted(
                method="plan_drawing",
                scale=Scale(status="no_scale"),
                read=(),
                notes=(f"ifc extractor: {read}",),
            )
        return Extracted(
            method="plan_drawing",  # the elements are what the sheet draws, named by the model
            scale=read.scale,
            plans=read.reading.plans,
            elements=read.reading.elements,
            rooms=read.reading.rooms,
            read=LOOKS_FOR,
            model_objects=_listed(read.model, read.reading.drawn),
            notes=(*read.notes, *read.reading.notes),
        )


class IfcSecondCounter:
    """What the model lists on the storey a sheet shows: its objects per element class and its
    spaces, drawn or not. Stage 8 compares them with what the sheet draws. `sheets` is the
    second counter of the sheet file itself: it measures a sheet that has no model, and its
    readings of a sheet that has one are passed on."""

    def __init__(self, files: DrawingFiles, models: IfcModels, sheets: SecondCounter) -> None:
        self._files, self._models, self._sheets = files, models, sheets

    def measure(self, source: DrawingFile, sheet: Sheet) -> Sequence[Measurement]:
        if source.kind != "ifc":
            return self._sheets.measure(source, sheet)
        own = self._sheets.measure(sheet.file, sheet)
        read = _read(self._files, self._models, source, sheet)
        if isinstance(read, str) or (storey := read.reading.storey) is None:
            return own
        spaces = sum(space.storey == storey for space in read.model.spaces)
        return [
            *own,
            *(
                Measurement(
                    quantity="element_count",
                    subject=Subject(kind="class", ref=class_),
                    value=MeasuredValue(
                        value=len(read.model.on_storey(class_, storey)),
                        unit="count",
                        method="ifc_model",
                    ),
                )
                for class_ in CLASSES.values()
            ),
            Measurement(
                quantity="room_count",
                subject=Subject(kind="sheet", ref=None),
                value=MeasuredValue(value=spaces, unit="rooms", method="ifc_model"),
            ),
        ]


def _listed(model: Model, drawn: Mapping[str, str]) -> tuple[ModelObject, ...]:
    """Every object of the model, of every storey, as the drawing's `model_objects`. `drawn`: by
    GlobalId, the id of the element or room a sheet draws the object as."""
    found: list[tuple[ModelClass, IfcObject]] = [
        *((class_, listed) for class_ in CLASSES.values() for listed in model.elements[class_]),
        *(("space", space) for space in model.spaces),
    ]
    ids = {
        listed.guid: f"m{number}"
        for number, (class_, listed) in enumerate(found, start=1)
        if class_ == "window"
    }
    return tuple(
        ModelObject(
            id=f"m{number}",
            class_=class_,
            storey=listed.storey,
            global_id=listed.guid,
            name=listed.name,
            long_name=listed.long_name,
            quantities=dict(listed.quantities),
            element=drawn.get(listed.guid),
            attrs={"source_class": listed.source_class, **_windows(listed, ids)},
        )
        for number, (class_, listed) in enumerate(found, start=1)
    )


def _windows(space: IfcObject, ids: Mapping[str, str]) -> dict[str, Attr]:
    """What a space's model object says of its windows (decision 0004, 2026-11-14): `windows`,
    how many of the model's windows belong to it, drawn on this sheet or not, and `window_ids`,
    their model object ids. Nothing when that is not known, so such a space says what it said."""
    if space.windows is None:
        return {}
    listed = [ids[guid] for guid in space.windows if guid in ids]
    return {"windows": len(listed), **({"window_ids": " ".join(listed)} if listed else {})}


def _read(files: DrawingFiles, models: IfcModels, source: DrawingFile, sheet: Sheet) -> _Read | str:
    """The sheet as the model and its SVG twin give it, or why it cannot be read that way."""
    if source.kind != "ifc":
        return f"the source {source.path} is {source.kind}, not an IFC model"
    if sheet.file.kind != "pdf":
        return f"{sheet.file.path} is {sheet.file.kind}: only a PDF sheet has an SVG twin"
    twin = str(PurePosixPath(sheet.file.path).with_suffix(".svg"))
    try:
        svg = read_svg(files.read(twin))
    except NotFoundError:
        return f"{twin} is missing, so the model's objects cannot be placed on the sheet"
    page = read_page(files.read(sheet.file.path))
    _, _, width, height = svg.view_box
    if abs((width / height) / (page.width / page.height) - 1) > SAME_SHAPE:
        return f"{twin} does not have the shape of {sheet.file.path}"
    scale, notes = read_scale(page)
    titled = next(
        (found.group(1) for text in page.texts if (found := STOREY.search(text.text))), None
    )
    m_per_svg_unit = None if scale.m_per_unit is None else scale.m_per_unit * page.width / width
    model = models.model(source)
    return _Read(model, read_sheet(model, svg, m_per_svg_unit, titled), scale, notes)
