"""The confidence gate (GATE_POLICY): per question family, the threshold above which an answer's
confidence marks it sure.

The file is golden's `data/stoa/exp/gate.json` (`stoa_eval gate-policy`), schema
`gate_policy_v1`, chosen on val (docs/GOLDEN.md):

    {"schema": "gate_policy_v1", "part": "val", "split_sha256": "<64 hex>", "certified": false, ...,
     "families": {"toilet": {"signal": "g1main", "threshold": 0.7625, "group": "elements",
                             "val": {...}}}}

A threshold holds only for the signal it was chosen on, so the loader keeps the families whose
`signal` is the answer confidence's (DECISIONS_CONFIDENCE: `g1main`). A file without the split's
sha256, or not chosen on val, is refused.
"""

import json
import re
from pathlib import Path
from typing import Any, cast

from app.core.errors import InvalidInputError

SCHEMA = "gate_policy_v1"
SHA256 = re.compile(r"[0-9a-f]{64}")


def load_gate(path: Path, signal: str) -> dict[str, float]:
    """Family -> threshold, for the families gated on `signal`."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or cast(dict[str, Any], doc).get("schema") != SCHEMA:
        raise InvalidInputError(f"{path}: a confidence gate is golden's {SCHEMA} gate.json")
    doc = cast(dict[str, Any], doc)
    if doc.get("part") != "val":
        raise InvalidInputError(f"{path}: the gate must be chosen on val, not {doc.get('part')!r}")
    sha = doc.get("split_sha256")
    if not isinstance(sha, str) or not SHA256.fullmatch(sha):
        raise InvalidInputError(f"{path}: no split_sha256: which split chose it is unknown")
    families = doc.get("families")
    if not isinstance(families, dict):
        raise InvalidInputError(f"{path}: 'families' must map families to their gate")
    gates: dict[str, float] = {}
    for family, gate in cast(dict[str, Any], families).items():
        entry = cast(dict[str, Any], gate) if isinstance(gate, dict) else {}
        threshold = entry.get("threshold")
        if isinstance(threshold, bool) or not isinstance(threshold, int | float):
            raise InvalidInputError(f"{path}: {family}: no numeric 'threshold'")
        if entry.get("signal") == signal:
            gates[family] = float(threshold)
    return gates
