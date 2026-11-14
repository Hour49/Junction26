"""The local gate models lgate / lgate2 (app/core/answering/local_gate.py) from their JSON,
schema `local_gate_v1`, written by prototypes/localdec/lgate_rt.py (one file per signal and
config, e.g. data/models/arbiter/T1/lgate2-rt-C1T1.json, gitignored):

    {"schema": "local_gate_v1", "name": "lgate2-rt", "families": [...], "readers": ["l1", "m1"],
     "blocks": ["l1", "readers", "extras"], "prior": {"door": {"7": 0.08, ...}, ...},
     "mu": [...], "sd": [...], "coef": [...], "intercept": -0.3}

No pickles: plain numbers, checked on load.
"""

import json
from pathlib import Path
from typing import Any

from app.core.answering.local_gate import LocalGateModel
from app.core.errors import InvalidInputError, NotFoundError

SCHEMA = "local_gate_v1"
BLOCKS = frozenset({"l1", "readers", "extras", "arbiter_p"})


def load_local_gate(path: Path) -> LocalGateModel:
    if not path.is_file():
        raise NotFoundError(f"{path} is missing (local gate models live in data/models/)")
    try:
        doc: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InvalidInputError(f"{path}: {error}") from error
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise InvalidInputError(f"{path}: not a {SCHEMA} file")
    try:
        blocks = frozenset(doc["blocks"])
        if unknown := sorted(blocks - BLOCKS):
            raise ValueError(f"unknown blocks {unknown}")
        model = LocalGateModel(
            name=str(doc["name"]),
            families=tuple(map(str, doc["families"])),
            readers=tuple(map(str, doc["readers"])),
            blocks=blocks,
            prior={f: {int(k): float(v) for k, v in d.items()} for f, d in doc["prior"].items()},
            mu=tuple(map(float, doc["mu"])),
            sd=tuple(map(float, doc["sd"])),
            coef=tuple(map(float, doc["coef"])),
            intercept=float(doc["intercept"]),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise InvalidInputError(f"{path}: not a {SCHEMA} model ({error!r})") from error
    if not len(model.mu) == len(model.sd) == len(model.coef):
        raise InvalidInputError(f"{path}: mu, sd and coef differ in length")
    if missing := sorted(set(model.families) - set(model.prior)):
        raise InvalidInputError(f"{path}: no prior for {missing}")
    return model
