"""The double-check policy (CHECK_POLICY): which answers are certified, so every other one asks a
person to double-check it (app/core/review/check.py).

The file is golden's `eval/results/gate/check-<config>.json`, schema `check_policy_v1`, chosen on
val (D455: per family, the threshold maximising certified - lambda x wrong; docs/GOLDEN.md):

    {"schema": "check_policy_v1", "part": "val", "split_sha256": "<64 hex>", "lambda": 10, ...,
     "families": {"toilet": {"signal": "g1main", "threshold": 0.31, "val": {...}},
                  "window": {"signal": "g1main", "threshold": null, "val": {...}}},
     "routes": {"bim": {"certified": true, "holdout": {...}}}}

Levels (decision 0011) are optional fields of the same schema, written by `check-policy --medium`:

     "families": {"toilet": {..., "threshold": 0.31, "medium": 0.12}},
     "routes": {"bim": {"certified": true, "level": "high", "dev": {"units": 372, "exact": 372}}},
     "levels": {"cut": 0.2, "crossfit": {"high": {"units": 1517, "exact": 1501}, "medium": {...},
                                         "low": {...}}}

`medium` is the lowest Medium score on the threshold's signal (null: the family has no Medium), a
route's `level` is High exactly when it is certified, and the counts are what the level's
sentence quotes. A file without `levels` loads as before and gives no answer a level.

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
from app.core.review.check import LEVELS, CheckPolicy, Counts, LevelName

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
    medium: dict[str, float] = {}
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
        else:
            continue  # on a signal that is not configured: neither threshold holds
        low = entry.get("medium")
        if low is None:
            continue  # no Medium: the family's answers that ask are Low
        if isinstance(low, bool) or not isinstance(low, int | float) or low > threshold:
            raise InvalidInputError(
                f"{path}: {family}: 'medium' must be a number at or under 'threshold', or null"
            )
        medium[family] = float(low)
    certified = set[str]()
    route_levels: dict[str, LevelName] = {}
    route_counts: dict[str, Counts] = {}
    for route, verdict in cast(dict[str, Any], routes).items():
        entry = cast(dict[str, Any], verdict) if isinstance(verdict, dict) else {}
        if not isinstance(entry.get("certified"), bool):
            raise InvalidInputError(f"{path}: route {route}: 'certified' must be true or false")
        if entry["certified"]:
            certified.add(route)
        made = entry.get("level")
        if made is not None:
            if made not in LEVELS or (made == "high") != entry["certified"]:
                raise InvalidInputError(
                    f"{path}: route {route}: 'level' is high (only when certified), medium or low"
                )
            route_levels[route] = made
        if entry.get("dev") is not None:
            route_counts[route] = _counts(path, f"route {route}: 'dev'", entry["dev"])
    return CheckPolicy(
        thresholds=thresholds,
        routes=frozenset(certified),
        signals=signals,
        medium=medium,
        route_levels=route_levels,
        route_counts=route_counts,
        counts=_level_counts(path, doc.get("levels")),
    )


def _level_counts(path: Path, levels: object) -> dict[LevelName, Counts] | None:
    """The val cross-fit answers at each level (`levels.crossfit`); None: the file has no levels."""
    if levels is None:
        return None
    crossfit = cast(dict[str, Any], levels).get("crossfit") if isinstance(levels, dict) else None
    if not isinstance(crossfit, dict) or set(cast(dict[str, Any], crossfit)) != set(LEVELS):
        raise InvalidInputError(f"{path}: 'levels.crossfit' gives the counts of high, medium, low")
    found = cast(dict[str, Any], crossfit)
    return {name: _counts(path, f"'levels.crossfit.{name}'", found[name]) for name in LEVELS}


def _counts(path: Path, where: str, value: object) -> Counts:
    entry = cast(dict[str, Any], value) if isinstance(value, dict) else {}
    units, exact = entry.get("units"), entry.get("exact")
    if (
        isinstance(units, bool)
        or isinstance(exact, bool)
        or not isinstance(units, int)
        or not isinstance(exact, int)
        or not 0 <= exact <= units
    ):
        raise InvalidInputError(f"{path}: {where} needs whole 'units' and 'exact', exact <= units")
    return Counts(units=units, exact=exact)
