r"""The dev prior (the `AnswerPrior` port): a best estimate per dataset source and question family,
for a question whose value the drawing does not give.

It is built from the dev split's organiser answers only, never the sealed eval split, so it is
partner-derived data: the table stays local in the gitignored `data/stoa/priors/` (record 0003),
and only this code is committed. Build it from backend/:

    uv run python -m app.adapters.answer_prior ../data/stoa/split/dev.jsonl

Per (source, family) it keeps the mode of the answers for counts and the median for areas,
lengths and volumes; its confidence is the share of dev answers that value gets right (equal for
a count, within the scorer's 2% for the rest). A family with fewer than 5 dev answers has none.
"""

import argparse
import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, cast, get_args

from app.core.answering.model import Prior, Unit, Unsupported, source_of
from app.core.answering.ports import QuestionParser
from app.core.errors import InvalidInputError

SCHEMA = "answer_prior_v1"
DEV_PRIOR = Path(__file__).resolve().parents[3] / "data" / "stoa" / "priors" / "dev.json"
REL_TOL = 0.02  # eval/stoa_eval/scoring.py REL_TOL: what the scorer counts as right
MIN_ANSWERS = 5  # a family with fewer dev answers gets no prior: its share would mean nothing


class NoPrior:
    """ANSWER_PRIOR=none: a refusal stays null."""

    def prior(self, source: str, family: str) -> Prior | None:
        return None


class TablePrior:
    """ANSWER_PRIOR=dev: the table that `build` wrote."""

    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise InvalidInputError(
                f"ANSWER_PRIOR=dev needs {path}: build it with `uv run python -m "
                "app.adapters.answer_prior ../data/stoa/split/dev.jsonl`, or set ANSWER_PRIOR=none"
            )
        table = json.loads(path.read_text(encoding="utf-8"))
        if table.get("schema") != SCHEMA:
            raise InvalidInputError(f"{path} is not an {SCHEMA} table")
        self._priors = {
            (source, family): Prior.model_validate(prior)
            for source, families in table["priors"].items()
            for family, prior in families.items()
        }

    def prior(self, source: str, family: str) -> Prior | None:
        return self._priors.get((source, family))


def build(rows: Iterable[Mapping[str, Any]], parser: QuestionParser) -> dict[str, Any]:
    """The prior table of dataset question rows (`path`, `question`, `answer`, `unit`). Rows
    with a text answer, an unknown unit or a question the parser can't read are left out, and so
    is a family with fewer than MIN_ANSWERS rows."""
    answers: dict[tuple[str, str, Unit], list[float]] = defaultdict(list)
    for row in rows:
        value, unit = row["answer"], row["unit"]
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        if unit not in get_args(Unit):
            continue
        parsed = parser.parse(row["question"])
        if isinstance(parsed, Unsupported):
            continue
        answers[(source_of(row["path"]), parsed.family(), cast(Unit, unit))].append(value)
    priors: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for (source, family, unit), values in sorted(answers.items()):
        if (
            len(values) < MIN_ANSWERS or family in priors[source]
        ):  # one family asked in two units: keep the first
            continue
        priors[source][family] = _estimate(values, unit).model_dump()
    return {"schema": SCHEMA, "priors": dict(priors)}


def _estimate(values: list[float], unit: Unit) -> Prior:
    if unit == "count":
        value, hits = Counter(values).most_common(1)[0]
    else:
        value = round(statistics.median(values), 3)
        hits = sum(abs(v - value) <= REL_TOL * abs(v) * (1 + 1e-9) for v in values)
    return Prior(value=value, unit=unit, confidence=round(hits / len(values), 4), n=len(values))


def main(argv: list[str] | None = None) -> None:
    from app.adapters.question_templates import TemplateParser

    args = argparse.ArgumentParser(prog="python -m app.adapters.answer_prior")
    args.add_argument("dev", type=Path, help="the dev split, data/stoa/split/dev.jsonl")
    args.add_argument("--out", type=Path, default=DEV_PRIOR)
    parsed = args.parse_args(argv)
    if parsed.dev.name != "dev.jsonl":  # the eval split is sealed: never a prior source
        raise InvalidInputError(f"{parsed.dev} is not the dev split (dev.jsonl)")
    with parsed.dev.open(encoding="utf-8") as lines:
        table = build((json.loads(line) for line in lines if line.strip()), TemplateParser())
    parsed.out.parent.mkdir(parents=True, exist_ok=True)
    parsed.out.write_text(json.dumps(table, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    families = sum(len(found) for found in table["priors"].values())
    print(f"wrote {families} families from {parsed.dev} to {parsed.out}")


if __name__ == "__main__":
    main()
