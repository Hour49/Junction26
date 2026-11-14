"""The answer policy (ANSWER_POLICY): which question families are answered from the prior even
when the drawing gives a value, because no reader beats the prior there on val.

The file is golden's `data/stoa/exp/policy.json` (`stoa_eval leaderboard`), schema
`answer_policy_v1`. Per question family (the parser's and the prior's family names, e.g.
"room:kitchen") it names the best arm on val, or "prior" when none beats the prior:

    {"schema": "answer_policy_v1", "part": "val", ...,
     "families": {"room:kitchen": {"source": "prior", "arm": null, ...},
                  "room:wc": {"source": "data/stoa/exp/ocr/G4", "arm": "ocr/G4", ...}}}

Only "prior" matters here: which arm reads a family is the composition's choice
(RASTER_COMPONENTS). The leaderboard ranks arms on the experiment's val part, which is CubiCasa5K
only, so the families it sends to the prior are CubiCasa's: a choice made for raster plans never
touches the sources other readers handle. A policy not made on val is refused.
"""

import json
from pathlib import Path
from typing import Any, cast

from app.core.errors import InvalidInputError

SCHEMA = "answer_policy_v1"
SOURCE = "cubicasa5k"  # the dataset source of the val part the leaderboard ranks on
PRIOR = "prior"


def load_policy(path: Path) -> frozenset[tuple[str, str]]:
    """The (source, family) pairs the file sends to the prior."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or cast(dict[str, Any], doc).get("schema") != SCHEMA:
        raise InvalidInputError(f"{path}: an answer policy is golden's {SCHEMA} policy.json")
    doc = cast(dict[str, Any], doc)
    if doc.get("part") != "val":
        raise InvalidInputError(
            f"{path}: the policy must be chosen on val, not {doc.get('part')!r}"
        )
    families = doc.get("families")
    if not isinstance(families, dict):
        raise InvalidInputError(f"{path}: 'families' must map families to their pick")
    pairs: set[tuple[str, str]] = set()
    for family, pick in cast(dict[str, Any], families).items():
        source = cast(dict[str, Any], pick).get("source") if isinstance(pick, dict) else None
        if not isinstance(source, str) or not source:
            raise InvalidInputError(f"{path}: {family}: no 'source' (an arm folder or 'prior')")
        if source == PRIOR:
            pairs.add((SOURCE, family))
    return frozenset(pairs)
