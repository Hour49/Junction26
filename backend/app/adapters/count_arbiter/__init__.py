"""The local count arbiter T1 as a raster component (`RASTER_COMPONENTS` source
`arbiter-t1:<arm>[:<one-view tune run>]`), the local stand-in for the Decisions count swap.

It reads the page three ways: `<arm>`'s detector over eight views (the base, whose elements and
plans it returns), the same detector on the canvas as is with its one-view thresholds (the
folder's detector.json, or the tune run named, as `detector:<arm>:<run>`), and L1, a page-level
count model. app/core/pipeline/count_arbiter.py picks each element family's count from those;
where the pick differs from the base's count, elements are dropped (the lowest `attrs.score`
first) or added without a location (the first plan's box, `attrs.located` false), as the
Decisions swap does. `plan` is never changed (T1's scored arm left it as the detector read it).

ARBITER_MODEL_DIR (default data/models/arbiter/T1/, gitignored, from
data/stoa/exp/local-dec/) holds:

- `arbiter.json`: local-dec's ship/arbiter-T1.json (per family mu, sd, coef, intercept);
- `prior.json`: ship/prior-T1.json (per family, count -> share of train answers);
- `l1.onnx`, `l1.json`, `temps.json`: L1-cnxt-t-1024's model.onnx, model.onnx.json, temps.json.

L1 runs once per page on the CPU: grayscale, long side scaled to `size` (Lanczos), pasted
top-left on white, /255; P = softmax(logits / T) per head (prototypes/localdec/prep.py).
"""

import json
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.adapters.raster_detector import Session, onnx_session
from app.core.drawing.model import Element, ElementClass
from app.core.errors import InvalidInputError, NotFoundError
from app.core.pipeline.count_arbiter import (
    FAMILY_CLASSES,
    ArbiterModel,
    FamilyModel,
    Reading,
    pick,
)
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles, Extractor

ADDED: Mapping[str, ElementClass] = {
    "door": "door",
    "window": "window",
    "sink": "sink",
    "toilet": "toilet",
    "shower+bathtub": "shower",
    "sauna": "sauna_stove",
}


def _json(path: Path) -> Any:
    if not path.is_file():
        raise NotFoundError(f"{path} is missing (the arbiter's files live in data/models/arbiter/)")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InvalidInputError(f"{path}: {error}") from error


def load_model(folder: Path) -> ArbiterModel:
    """`arbiter.json` and `prior.json` of the folder as the core's model."""
    shipped, prior = _json(folder / "arbiter.json"), _json(folder / "prior.json")
    try:
        families = {}
        for family, fit in shipped["families"].items():
            model = FamilyModel(
                tuple(map(float, fit["mu"])), tuple(map(float, fit["sd"])),
                tuple(map(float, fit["coef"])), float(fit["intercept"]),
            )  # fmt: skip
            if not len(model.mu) == len(model.sd) == len(model.coef):
                raise ValueError(f"{family}: mu, sd and coef differ in length")
            families[family] = model
        shares = {f: {int(k): float(v) for k, v in d.items()} for f, d in prior.items()}
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise InvalidInputError(f"{folder}: not an arbiter model ({error!r})") from error
    if missing := sorted(set(families) - set(shares)):
        raise InvalidInputError(f"{folder}/prior.json has no family {missing}")
    return ArbiterModel(families, shares)


class L1PageCounts:
    """L1: P(count = i) per family for one page, from its ONNX model."""

    def __init__(
        self, session: Session, heads: Sequence[str], size: int, temps: Mapping[str, float]
    ) -> None:
        self._session = session
        self._heads = tuple(heads)
        self._size = size
        self._temps = temps

    @classmethod
    def from_folder(cls, folder: Path) -> "L1PageCounts":
        facts, temps = _json(folder / "l1.json"), _json(folder / "temps.json")
        try:
            heads, size = list(facts["heads"]), int(facts["size"])
            temperature = {head: float(temps[head]) for head in heads}
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidInputError(f"{folder}: l1.json or temps.json ({error!r})") from error
        if not (folder / "l1.onnx").is_file():
            raise NotFoundError(f"{folder / 'l1.onnx'} is missing")
        return cls(onnx_session(folder / "l1.onnx"), heads, size, temperature)

    def page(self, data: bytes) -> np.ndarray:
        """The model's input: (1, 1, size, size) float32."""
        with Image.open(BytesIO(data)) as image:
            gray = image.convert("L")
        w, h = gray.size
        scale = self._size / max(w, h)
        gray = gray.resize(
            (max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS
        )
        canvas = Image.new("L", (self._size, self._size), 255)
        canvas.paste(gray, (0, 0))
        return (np.asarray(canvas, np.float32) / 255.0)[None, None]

    def probs(self, data: bytes) -> dict[str, list[float]]:
        name = self._session.get_inputs()[0].name
        outputs = self._session.run(None, {name: self.page(data)})
        if len(outputs) != len(self._heads):
            raise InvalidInputError(f"L1 gave {len(outputs)} outputs for {len(self._heads)} heads")
        found = {}
        for head, logits in zip(self._heads, outputs, strict=True):
            z = np.asarray(logits, np.float64).reshape(-1) / self._temps[head]
            e = np.exp(z - z.max())
            found[head] = (e / e.sum()).tolist()
        return found


def _score(element: Element) -> float:
    value = element.attrs.get("score")
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


def _looked_for(found: Extracted, classes: Sequence[str]) -> bool:
    return found.read is None or set(classes) <= set(found.read)


def reading_of(
    family: str, base: Extracted, second: Extracted, probs: Mapping[str, Sequence[float]]
) -> Reading:
    """The core's input for one family from the three reads (also used by the parity script).
    `plan` counts plans: its base and second count are the reads' plans, with no scores."""
    if family == "plan":
        n = len(base.plans)
        return Reading(n, (), n, len(second.plans), tuple(probs[family]))
    classes = FAMILY_CLASSES[family]
    mine = [e for e in base.elements if e.class_ in classes]
    return Reading(
        base=len(mine),
        scores=tuple(_score(e) for e in mine),
        plans=len(base.plans),
        second=sum(e.class_ in classes for e in second.elements),
        probs=tuple(probs[family]),
    )


class ArbiterCountExtractor:
    def __init__(
        self,
        base: Extractor,
        second: Extractor,
        l1: L1PageCounts,
        model: ArbiterModel,
        files: DrawingFiles,
    ) -> None:
        self._base = base
        self._second = second
        self._l1 = l1
        self._model = model
        self._files = files

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._base.extract(source, sheet)
        second = self._second.extract(source, sheet)
        probs = self._l1.probs(self._files.read(source.path))
        elements = list(found.elements)
        changes: list[str] = []
        for family, classes in FAMILY_CLASSES.items():
            if family not in self._model.families:
                continue
            if not (_looked_for(found, classes) and _looked_for(second, classes)):
                continue  # a reader did not look for it: no count to check
            reading = reading_of(family, found, second, probs)
            chosen = pick(self._model, family, reading)
            count = reading.base
            if chosen.count == count:
                continue
            changes.append(f"{family} {count} -> {chosen.count} (P = {chosen.p:.3f})")
            mine = [e for e in elements if e.class_ in classes]
            if chosen.count < count:
                drop = {
                    e.id
                    for e in sorted(mine, key=lambda e: (_score(e), e.id))[: count - chosen.count]
                }
                elements = [e for e in elements if e.id not in drop]
            else:
                box = found.plans[0].box if found.plans else (0.0, 0.0, 1.0, 1.0)
                plan = found.plans[0].id if found.plans else None
                for n in range(chosen.count - count):
                    elements.append(
                        Element(
                            id=f"arbiter-{family}-{n + 1}", class_=ADDED[family], page=1,
                            plan=plan, box=box,
                            attrs={"located": False, "source": "arbiter-t1",
                                   "p": round(chosen.p, 4)},
                        )
                    )  # fmt: skip
        note = "arbiter t1: " + ("; ".join(changes) if changes else "counts kept")
        return found.model_copy(update={"elements": tuple(elements), "notes": (*found.notes, note)})

    @classmethod
    def from_folder(
        cls, base: Extractor, second: Extractor, files: DrawingFiles, folder: Path
    ) -> "ArbiterCountExtractor":
        return cls(base, second, L1PageCounts.from_folder(folder), load_model(folder), files)
