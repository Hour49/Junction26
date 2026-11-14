"""golden-23: which answers the double-check policy certifies, computed by the backend's own ask() on the
drawings a run stored, so the test certificate uses exactly the code the API runs. Golden never runs it on
test: integ runs it once on the test read's outputs and joins the result with the truth.

Run from a backend checkout with #129 and #153 (cd backend; PYTHONPATH=.):

    uv run --locked python ../../Junction26/prototypes/golden23/certify.py \
        --drawings <a run's <out>/extraction (extraction_v1) or stored drawings, one JSON per page> \
        --questions <jsonl: id, path, question> --answers <answers.jsonl of the same run: id, answer, confidence> \
        --policy <check_policy_v1> --local-gates <model.json,...> [--answer-policy <answer_policy_v1>] \
        [--flags <dir of ingest outcome JSON with `path` and `flags`>] \
        --g1main <dataset path -> family -> {count: P}: eval/ab_backend.py g1main on the run's Decisions cache> \
        --out <certified.jsonl>

--g1main (golden-25, #174's rule in the certificate): a plan count is certified only when G1main's own most
likely plan count is the answered one; the run's answers.jsonl keeps only the score, so that count comes from the
same replies the run read. A page with no G1main distribution gives no agreement: its plan count asks.

Writes one line per question: id, file, family, answer (ask()'s), recorded (the run's), certified (true: no
double-check request; false: asks; null: not a takeoff count the policy rates, e.g. a refusal), the reason when
it asks. A line whose ask() answer differs from the run's answer is flagged `mismatch` (the drawing or the
config is not the run's): the certificate must not count those silently. --api-answers also writes ask()'s
answer line per question (answer_v1.1, the question's id), so the join can judge the answer the API gives.

Changed 2026-11-14 (golden, after integ-13's test read): the score is G1main's P of ask()'s answered count,
read from --g1main as DecisionsConfidence reads it (CountDist.p: 0.0 for a count it never gives), no longer
the run's recorded `confidence`. Why: the CLI run answers room:kitchen from the dev prior (ANSWER_POLICY on a
`data/cubicasa5k/...` path), so its line's confidence is the prior's hit rate (0.9579), which certified all
516 test kitchen answers. The API never answers from the prior for an upload (its file is the bare name, so
source_of() is ""): it answers the drawing's count and scores it with G1main (checked live on val
colorful-10711 at 671d67f: method takeoff, g1main 0.909, sure). On every line the run answered by takeoff the
two scores are equal (printed as a parity count).
"""

import argparse
import json
from pathlib import Path

from app.adapters.answer_policy import load_policy
from app.adapters.answer_prior import NoPrior
from app.adapters.check_policy import load_check
from app.adapters.extraction_v1 import ExtractionV1Reader
from app.adapters.local_gate import load_local_gate
from app.adapters.question_templates import TemplateParser
from app.core.drawing.model import Drawing
from app.core.review.ask import ask
from app.core.review.check import gate_scorer
from app.core.review.model import ReviewState

SIGNAL = "g1main"  # the answer confidence's (DECISIONS_CONFIDENCE)


class Rated:
    def __init__(self, value: float | None, agrees: bool | None) -> None:
        self.value, self.note, self.agrees = value, "g1main", agrees


class G1main:
    """What DecisionsConfidence says at runtime for the page, from the run's G1main distributions:
    P of the answered count (0.0 for a count the reply never gives) and whether its most likely
    count (CountDist.top: a tie goes to the smaller) is the answered one; None and None when the
    page has no distribution for the family or the value is not a count."""

    def __init__(self, counts: dict[str, dict[str, float]]) -> None:
        self.counts = counts

    def probability(self, path: str, family: str, value: object) -> Rated:
        dist = {int(k): p for k, p in self.counts.get(family, {}).items()}
        if not dist or isinstance(value, bool) or not isinstance(value, int):
            return Rated(None, None)
        return Rated(dist.get(value, 0.0), max(sorted(dist), key=lambda k: dist[k]) == value)


def main() -> None:
    args = argparse.ArgumentParser()
    for name in ("--drawings", "--questions", "--answers", "--policy", "--out"):
        args.add_argument(name, type=Path, required=True)
    args.add_argument("--local-gates", default="")
    args.add_argument("--answer-policy", type=Path)
    args.add_argument("--flags", type=Path)
    args.add_argument("--g1main", type=Path, required=True)
    args.add_argument("--api-answers", type=Path)
    a = args.parse_args()
    models = [load_local_gate(Path(p)) for p in a.local_gates.split(",") if p.strip()]
    scorers = {m.name.lower(): gate_scorer(m) for m in models}
    policy = load_check(a.policy, SIGNAL, scorers)
    prior_families = load_policy(a.answer_policy) if a.answer_policy else frozenset()
    drawings: dict[str, Drawing] = {}
    paths = sorted(a.drawings.glob("*.json"))
    if paths and "schema" in json.loads(paths[0].read_text(encoding="utf-8")):
        reader = ExtractionV1Reader(a.drawings)  # a pipeline run's <out>/extraction, as eval reads it
        files = [json.loads(path.read_text(encoding="utf-8"))["file"] for path in paths]
        found = {file: reader.drawing(file) for file in files}
        drawings = {Path(file).name: d for file, d in found.items() if d is not None}
    else:  # the backend's stored drawings (data/projects/drawings/<id>.json)
        for path in paths:
            drawing = Drawing.model_validate(json.loads(path.read_text(encoding="utf-8")))
            drawings[Path(drawing.file).name] = drawing
    flags: dict[str, tuple[str, ...]] = {}
    if a.flags:
        for path in sorted(a.flags.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            flags[Path(doc["path"]).name] = tuple(doc.get("flags") or ())
    g1main = {Path(f).name: by for f, by in json.loads(a.g1main.read_text(encoding="utf-8")).items()}
    answers = {row["id"]: row for row in map(json.loads, a.answers.read_text().splitlines())}
    out, lines, parity = [], [], [0, 0]  # takeoff lines whose recorded score equals G1main's, all
    for line in a.questions.read_text(encoding="utf-8").splitlines():
        q = json.loads(line)
        name = Path(q["path"]).name
        if name not in drawings or q["id"] not in answers:
            continue
        run = answers[q["id"]]
        found = ask(
            q["question"], drawings[name], parser=TemplateParser(), clock=lambda: 0.0,
            prior=NoPrior(), state=ReviewState(), prior_families=prior_families,
            confidence=G1main(g1main.get(name, {})), flags=flags.get(name, ()), raster=True,
            check=policy, route="raster", scorers=scorers,
        )  # fmt: skip
        sure = found.answer.sure
        if run.get("method") == "takeoff" and found.answer.method == "takeoff":
            parity[0] += found.answer.confidence == run.get("confidence")
            parity[1] += 1
        lines.append(found.answer.model_copy(update={"id": q["id"]}).model_dump_json())
        out.append({
            "id": q["id"], "file": name, "family": found.query, "answer": found.answer.answer,
            "recorded": run.get("answer"), "mismatch": found.answer.answer != run.get("answer"),
            "certified": sure, "reason": None if found.check is None else found.check.reason,
        })  # fmt: skip
    a.out.write_text("".join(json.dumps(row) + "\n" for row in out), encoding="utf-8")
    if a.api_answers:
        a.api_answers.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    rated = [r for r in out if r["certified"] is not None]
    print(
        f"{len(out)} questions, {len(rated)} rated, {sum(r['certified'] for r in rated)} certified, "
        f"{sum(r['mismatch'] for r in out)} answers differ from the run's -> {a.out}; G1main score equal "
        f"to the run's on {parity[0]} of {parity[1]} lines both answered by takeoff"
    )


if __name__ == "__main__":
    main()
