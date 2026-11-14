"""`IFC_FACTS=true`: the fact sheet of an IFC model file (app/core/ifc_facts.py), built once per
file from facts_arch.py, facts_mep.py and facts_finish.py and kept, for the answering core's fact
fallback (app/core/answering/facts.py).

`cache_dir` keeps each sheet as JSON by the file's sha256 and the fact code's version (`CODE`),
so a run over many questions reads a large model once across runs too (the CLI's scoring runs;
an API process keeps its own memory).
"""

import hashlib
import logging
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import ifcopenshell

from app.adapters.ifc_model import facts_arch, facts_finish, facts_mep
from app.adapters.ifc_model.facts_arch import arch_facts
from app.adapters.ifc_model.facts_finish import finish_facts
from app.adapters.ifc_model.facts_mep import mep_facts
from app.core import ifc_facts
from app.core.ifc_facts import Discipline, FactSheet
from app.core.pipeline.ports import DrawingFiles

logger = logging.getLogger(__name__)
SHEETS_KEPT = 8  # in memory; a sheet of a large MEP model is ~10 MB of facts
# The fact code's version: a change to a fact writer or to the schema misses the old cache.
CODE = hashlib.sha256(
    b"".join(
        Path(m.__file__ or "").read_bytes()
        for m in (facts_arch, facts_mep, facts_finish, ifc_facts)
    )
).hexdigest()[:12]


class IfcFactSource:
    def __init__(self, files: DrawingFiles, cache_dir: Path | None = None) -> None:
        self._files = files
        self._cache_dir = cache_dir
        self._sheets: dict[str, FactSheet | None] = {}

    def facts(self, file: str) -> FactSheet | None:
        if PurePosixPath(file).suffix.lower() != ".ifc":
            return None
        if file not in self._sheets:
            if len(self._sheets) >= SHEETS_KEPT:
                del self._sheets[next(iter(self._sheets))]
            self._sheets[file] = self._sheet(file)
        return self._sheets[file]

    def _sheet(self, file: str) -> FactSheet | None:
        data = self._files.read(file)
        cached = None
        if self._cache_dir is not None:
            cached = self._cache_dir / f"{hashlib.sha256(data).hexdigest()}-{CODE}.json"
            if cached.is_file():
                try:
                    return FactSheet.model_validate_json(cached.read_text(encoding="utf-8"))
                except ValueError as error:  # pydantic's ValidationError is one
                    logger.warning("%s: cached sheet unreadable, rebuilt: %s", file, error)
        try:
            sheet = read_facts(data, PurePosixPath(file).stem)
        except Exception as error:  # ifcopenshell raises its own and plain RuntimeErrors
            logger.warning("%s: no fact sheet: %s", file, error)
            return None
        if cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            part = cached.with_suffix(".part")  # a run killed mid-write leaves no half sheet
            part.write_text(sheet.model_dump_json(), encoding="utf-8")
            part.replace(cached)
        return sheet


def read_facts(data: bytes, model: str) -> FactSheet:
    """Every fact facts_arch.py, facts_mep.py and facts_finish.py read from an IFC file's bytes."""
    with tempfile.NamedTemporaryFile(suffix=".ifc") as on_disk:
        on_disk.write(data.decode("utf-8", errors="replace").encode())  # as objects.read_model
        on_disk.flush()
        opened: Any = ifcopenshell.open  # its typed overloads leave `lazy` out
        file = opened(on_disk.name, lazy=True)
        # while the file is on disk: lazy reads go back to it
        facts = [*arch_facts(file), *mep_facts(file), *finish_facts(file)]
    disciplines: list[Discipline] = sorted({fact.discipline for fact in facts})
    return FactSheet(model=model, disciplines=disciplines, facts=facts)
