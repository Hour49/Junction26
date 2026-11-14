"""Where services models are kept (services-model.md SV-2, SV-8): one gzipped JSON per source
file, `<cache>/<sha256>.services.v1.json.gz`, beside the fact-sheet cache, written atomically.

The id map (GlobalId -> element id) is kept per file name as the project knows it, not per
content hash, so a re-exported file (new bytes, same name) keeps every old id; the spec's
`<sha256>.ids.json` could not, since a re-export has another sha256.
"""

import gzip
import hashlib
import json
import logging
import tempfile
from pathlib import Path

from app.adapters.ifc_model.services_model import build_services_model
from app.core.services.stored import ServicesModel

logger = logging.getLogger(__name__)


class ServicesStore:
    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir

    def load(self, sha256: str) -> ServicesModel | None:
        path = self._dir / f"{sha256}.services.v1.json.gz"
        if not path.is_file():
            return None
        return ServicesModel.model_validate_json(gzip.decompress(path.read_bytes()))

    def build(
        self, name: str, data: bytes, architecture: bytes | None = None
    ) -> ServicesModel | None:
        """The model of the file `name` with content `data` (and its building model's bytes),
        built once and kept. None when ifcopenshell cannot read it."""
        stored = self.load(hashlib.sha256(data).hexdigest())
        if stored is not None:
            return stored
        ids_path = self._dir / f"{hashlib.sha256(name.encode()).hexdigest()[:24]}.ids.json"
        ids = json.loads(ids_path.read_text(encoding="utf-8")) if ids_path.is_file() else {}
        with tempfile.TemporaryDirectory() as folder:
            services = Path(folder) / "services.ifc"
            services.write_bytes(data)
            building = None
            if architecture is not None:
                building = Path(folder) / "architecture.ifc"
                building.write_bytes(architecture)
            try:
                model, ids = build_services_model(services, ids, building)
            except Exception as error:  # ifcopenshell raises its own and plain RuntimeErrors
                logger.warning("%s: no services model: %s", name, error)
                return None
        self._write(ids_path, json.dumps(ids, indent=0, sort_keys=True).encode())
        raw = model.model_dump_json().encode()
        self._write(self._dir / f"{model.source.sha256}.services.v1.json.gz",
                    gzip.compress(raw, mtime=0))  # fmt: skip
        return model

    def _write(self, path: Path, data: bytes) -> None:
        """Whole or not at all: a run killed mid-write leaves no half file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        part.write_bytes(data)
        part.replace(path)
