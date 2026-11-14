"""The double-check policy (CHECK_POLICY): which answers are certified, so every other one asks a
person to double-check it (app/core/review/check.py).

The file is golden's `eval/results/gate/check-<config>.json`, schema `check_policy_v1`, chosen on
val (D455: per family, the threshold maximising certified - lambda x wrong; docs/GOLDEN.md):

    {"schema": "check_policy_v1", "part": "val", "split_sha256": "<64 hex>", "lambda": 10, ...,
     "families": {"toilet": {"signal": "g1main", "threshold": 0.31, "val": {...}},
                  "window": {"signal": "g1main", "threshold": null, "val": {...}}},
     "routes": {"bim": {"certified": true, "holdout": {...}}}}

A threshold holds only for the signal it was chosen on: the answer confidence's, or a local gate
model's that LOCAL_GATES configures (signal names compare without case: local-dec's models say
`lgate-rt-noL1`, its signal files `lgate-rt-nol1`). A family on another signal, or with a null
threshold, is never certified. A file without the split's sha256, or not chosen on val, is
refused.
"""

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from app.core.errors import InvalidInputError
from app.core.review.check import CheckPolicy

SCHEMA = "check_policy_v1"
SHA256 = re.compile(r"[0-9a-f]{64}")


def load_check(path: Path, signal: str | None, scorers: Iterable[str] = ()) -> CheckPolicy:
    """The thresholds on `signal` (the answer confidence's; None: off) or on one of `scorers`
    (the local gates' signal names), so a family on neither is never certified on the raster
    route, and the certified routes."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or cast(dict[str, Any], doc).get("schema") != SCHEMA:
        raise InvalidInputError(f"{path}: a double-check policy is golden's {SCHEMA} file")
    doc = cast(dict[str, Any], doc)
    if doc.get("part") != "val":
        raise InvalidInputError(
            f"{path}: the policy must be chosen on val, not {doc.get('part')!r}"
        )
    sha = doc.get("split_sha256")
    if not isinstance(sha, str) or not SHA256.fullmatch(sha):
        raise InvalidInputError(f"{path}: no split_sha256: which split chose it is unknown")
    families, routes = doc.get("families"), doc.get("routes", {})
    if not isinstance(families, dict) or not isinstance(routes, dict):
        raise InvalidInputError(f"{path}: 'families' and 'routes' must be objects")
    confidence = None if signal is None else signal.lower()
    local = {name.lower() for name in scorers}
    thresholds: dict[str, float] = {}
    signals: dict[str, str] = {}
    for family, gate in cast(dict[str, Any], families).items():
        entry = cast(dict[str, Any], gate) if isinstance(gate, dict) else {}
        threshold = entry.get("threshold")
        if threshold is None:
            continue  # never certified: no threshold reached the rule's utility on val
        if isinstance(threshold, bool) or not isinstance(threshold, int | float):
            raise InvalidInputError(f"{path}: {family}: 'threshold' must be a number or null")
        on = entry.get("signal")
        on = on.lower() if isinstance(on, str) else None
        if on is not None and on == confidence:
            thresholds[family] = float(threshold)
        elif on in local:
            thresholds[family] = float(threshold)
            signals[family] = on
    certified = set[str]()
    for route, verdict in cast(dict[str, Any], routes).items():
        entry = cast(dict[str, Any], verdict) if isinstance(verdict, dict) else {}
        if not isinstance(entry.get("certified"), bool):
            raise InvalidInputError(f"{path}: route {route}: 'certified' must be true or false")
        if entry["certified"]:
            certified.add(route)
    return CheckPolicy(thresholds=thresholds, routes=frozenset(certified), signals=signals)
