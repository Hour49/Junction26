"""integ-12: join certify.py's verdicts with the truth (golden-23 step 3). Per family and pooled:
answers rated, wrong, flagged share (certified false), recall of wrong flagged, exact among the
unflagged; refusals and mismatches (ask() answer != the run's) counted apart, never silently.

    cd <checkout>/eval && PYTHONPATH=. uv run --locked python <this> \
        <questions with truth .jsonl> <run>/answers.jsonl <run>/certified.jsonl > <run>/certificate.md
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from stoa_eval.ab import hits_of
from stoa_eval.models import Answer, NumberedQuestion


def main() -> None:
    truth_path, answers_path, certified_path = map(Path, sys.argv[1:4])
    certified = [json.loads(line) for line in certified_path.read_text().splitlines() if line.strip()]
    ids = {row["id"] for row in certified}
    questions = [
        NumberedQuestion.model_validate(q)
        for q in map(json.loads, truth_path.read_text().splitlines())
        if q["id"] in ids
    ]
    answers = {
        a.id: a
        for a in (Answer.model_validate_json(line) for line in answers_path.read_text().splitlines())
    }
    exact = hits_of(questions, answers)  # the run's own answer, Stoa's rule
    rows: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    refused, mismatch = defaultdict(int), defaultdict(int)
    for row in certified:
        family = row["family"] or "unsupported"
        if row["mismatch"]:
            mismatch[family] += 1
        if row["certified"] is None:
            refused[family] += 1
            continue
        rows[family].append((exact[row["id"]], not row["certified"]))
    print(f"{len(certified)} questions; {sum(mismatch.values())} ask() answers differ from the "
          f"run's; {sum(refused.values())} not rated (refusals or not a takeoff count)\n")  # fmt: skip
    print("| family | rated | wrong | flagged | wrong flagged (recall) | unflagged exact | not rated | mismatch |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    pooled: list[tuple[bool, bool]] = []
    for family in sorted(set(rows) | set(refused)):
        pooled += rows[family]
        print(line(family, rows[family], refused[family], mismatch[family]))
    print(line("**pooled**", pooled, sum(refused.values()), sum(mismatch.values())))


def line(name: str, xs: list[tuple[bool, bool]], refused: int, mismatch: int) -> str:
    n, wrong = len(xs), sum(not e for e, _ in xs)
    flagged = sum(f for _, f in xs)
    caught = sum((not e) and f for e, f in xs)
    rest = [e for e, f in xs if not f]
    rec = f"{caught}/{wrong} ({caught / wrong:.1%})" if wrong else "-"
    share = f"{flagged / n:.1%}" if n else "-"
    acc = f"{sum(rest) / len(rest):.1%} ({len(rest)})" if rest else "-"
    return f"| {name} | {n} | {wrong} | {share} | {rec} | {acc} | {refused} | {mismatch} |"


if __name__ == "__main__":
    main()
