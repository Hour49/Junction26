"""confidence section Z, step 1 (backend side, no truth): the level of every answer of a finished
test_read_live.sh read, from the read's own outputs only. Opens no image, runs no reader, makes no call.

Reads <run>/questions.jsonl (id, path, question: no answer field), answers.jsonl, extraction/cubicasa5k,
flags/, g1main.json, certified.jsonl. For each question it calls the backend's ask() exactly as
prototypes/golden23/certify.py did, takes the score the check policy read (`score_of`: the answer's g1main
confidence, or the local gate's score of the stored counts) and gives the level of scheme B for each pinned
levels file: High = certified.jsonl's `certified` is true; else Medium when score >= the family's `medium`;
else Low. `certified: null` (a refusal) gets no level.

Stops unless every row's `sure` and answer equal certified.jsonl's: then the scores are the certificate's.

Run from a backend checkout (cd <export>/backend; PYTHONPATH=.):
    uv run --locked python <repo>/prototypes/confidence/test_scores.py --run <run dir> --out <levels.jsonl>

--corrected <dir> (section AJ): golden's corrected certificate instead (eval/certificate/certify.py: kitchens
answered from the drawing, the score is G1main's P of the answered count), checked against
<dir>/certified.jsonl. Needs a backend with the level code and the committed levels policy (SHIPPED): each
row also gets `level_shipped`, the level the backend itself gives the answer.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from app.adapters.answer_policy import load_policy
from app.adapters.answer_prior import NoPrior
from app.adapters.check_policy import load_check
from app.adapters.extraction_v1 import ExtractionV1Reader
from app.adapters.local_gate import load_local_gate
from app.adapters.question_templates import TemplateParser
from app.core.answering.model import Query
from app.core.review.ask import ask
from app.core.review.check import gate_scorer, held, score_of
from app.core.review.model import ReviewState

REPO = Path(__file__).resolve().parents[2]  # the repo root (the run had the checkout's absolute path here)
POLICY = REPO / "data/stoa/exp/golden22/check-C1-T1-recall96-rt-full-small.json"
GATES = [REPO / "data/models/arbiter/T1/lgate2-rt-C1T1.json", REPO / "data/models/arbiter/T1/lgate-rt-noL1-C1T1.json"]
ANSWER_POLICY = Path("../eval/results/policy/policy-C-L-swap.json")
SIGNAL = "g1main"
# the pinned files of the pre-registration (report section 10): cut name -> file, sha256
LEVELS = {
    "020": ("levels-policy.json", "6fe73d8de55596e8ccc268f9813bedb4c08148a7a5c837ba9e3b7df068f8cacc"),
    "010": ("levels-policy-c010.json", "8d7670c54814ed636eecf14931af0dbf7abc6adbfbbc282a595ba3fef23b2e39"),
}
PINS = {
    POLICY: "a9334da1b908866d57fb4066791011bf5344a0f11471a05dba2f0815dd239def",
    GATES[0]: "5a4c4c9a3ef02d2652bc0ff6d9175ab7c3b8241a19daef57951bd4eb843de7d0",
    GATES[1]: "8f86dec681b1f1e5abea746c262c7bff1157f5866104a3a2281252e1206c4f47",
}


SHIPPED = (
    "eval/results/check/check-C1-T1-recall96-rt-full-small-medium20.json",
    "bfce5524cd32f3a6aac94307265892ed99251bc1efbee692ba9855e8d11b369a",
)


class Rated:
    def __init__(self, value: float | None, agrees: bool | None) -> None:
        self.value, self.note, self.agrees = value, "recorded", agrees


class Recorded:
    """The run's answer confidence, and whether g1main's own top count is the answered one (as
    prototypes/golden23/certify.py)."""

    def __init__(self, value: float | None, counts: dict[str, dict[str, float]]) -> None:
        self.value, self.counts = value, counts

    def probability(self, path: str, family: str, value: object) -> Rated:
        dist = {int(k): p for k, p in self.counts.get(family, {}).items()}
        if not dist or isinstance(value, bool) or not isinstance(value, int):
            return Rated(self.value, None)
        return Rated(self.value, max(sorted(dist), key=lambda k: dist[k]) == value)


class G1main:
    """As eval/certificate/certify.py: G1main's P of the answered count (0.0 for a count the reply never
    gives) and whether its most likely count is the answered one."""

    def __init__(self, counts: dict[str, dict[str, float]]) -> None:
        self.counts = counts

    def probability(self, path: str, family: str, value: object) -> Rated:
        dist = {int(k): p for k, p in self.counts.get(family, {}).items()}
        if not dist or isinstance(value, bool) or not isinstance(value, int):
            return Rated(None, None)
        return Rated(dist.get(value, 0.0), max(sorted(dist), key=lambda k: dist[k]) == value)


def pinned(path: Path, sha: str) -> Path:
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    assert got == sha, f"{path} is not the pinned file ({got})"
    return path


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--run", type=Path, required=True)
    args.add_argument("--out", type=Path, required=True)
    args.add_argument("--corrected", type=Path)
    a = args.parse_args()
    for path, sha in PINS.items():
        pinned(path, sha)
    medium = {
        cut: {f: e["medium"] for f, e in json.loads(
            pinned(REPO / "data/stoa/exp/confidence" / name, sha).read_text())["families"].items()}
        for cut, (name, sha) in LEVELS.items()
    }  # fmt: skip
    models = [load_local_gate(p) for p in GATES]
    scorers = {m.name.lower(): gate_scorer(m) for m in models}
    if a.corrected:  # the API's answers: no answer policy, the shipped policy with its levels
        policy = load_check(pinned(Path("..") / SHIPPED[0], SHIPPED[1]), SIGNAL, scorers)
        prior_families = frozenset()
    else:
        policy = load_check(POLICY, SIGNAL, scorers)
        prior_families = load_policy(ANSWER_POLICY)
    folder = a.run / "extraction/cubicasa5k"
    reader = ExtractionV1Reader(folder)
    files = [json.loads(p.read_text(encoding="utf-8"))["file"] for p in sorted(folder.glob("*.json"))]
    drawings = {Path(f).name: d for f in files if (d := reader.drawing(f)) is not None}
    flags = {}
    for path in sorted((a.run / "flags").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        flags[Path(doc["path"]).name] = tuple(doc.get("flags") or ())
    g1main = {Path(f).name: by for f, by in json.loads((a.run / "g1main.json").read_text()).items()}
    answers = {row["id"]: row for row in map(json.loads, (a.run / "answers.jsonl").read_text().splitlines())}
    verdicts = (a.corrected or a.run) / "certified.jsonl"
    certified = {row["id"]: row for row in map(json.loads, verdicts.read_text().splitlines())}
    parser = TemplateParser()
    out, differ, differing = [], 0, Counter[str]()
    for line in (a.run / "questions.jsonl").read_text(encoding="utf-8").splitlines():
        q = json.loads(line)
        name = Path(q["path"]).name
        if name not in drawings or q["id"] not in answers:
            continue
        run, cert = answers[q["id"]], certified[q["id"]]
        counts = g1main.get(name, {})
        confidence = G1main(counts) if a.corrected else Recorded(run.get("confidence"), counts)
        found = ask(
            q["question"], drawings[name], parser=parser, clock=lambda: 0.0,
            prior=NoPrior(), state=ReviewState(), prior_families=prior_families,
            confidence=confidence, flags=flags.get(name, ()), raster=True,
            check=policy, route="raster", scorers=scorers,
        )  # fmt: skip
        if found.answer.sure != cert["certified"] or found.answer.answer != cert["answer"]:
            differ += 1
            differing[str(cert["family"])] += 1
        parsed = parser.parse(q["question"])
        family = parsed.family() if isinstance(parsed, Query) else None
        score = agrees = why_held = None
        if found.row is not None and family is not None:
            score = score_of(policy, family, confidence=found.answer.confidence, drawing=drawings[name],
                             value=found.answer.answer, scorers=scorers)  # fmt: skip
            why_held = held(found.row, drawings[name])
            agrees = confidence.probability(q["path"], family, found.answer.answer).agrees
        row = {
            "id": q["id"], "file": name, "family": cert["family"], "policy_family": family,
            "certified": cert["certified"], "mismatch": cert["mismatch"],
            "signal": None if family is None else policy.signals.get(family, SIGNAL),
            "score": score, "confidence": found.answer.confidence, "agrees": agrees, "held": why_held,
        }  # fmt: skip
        if a.corrected:
            made = getattr(found, "level", None)
            row["level_shipped"] = None if made is None else made.level.capitalize()
            row["basis_shipped"] = None if made is None else made.basis
        for cut, by in medium.items():
            t = by.get(family or "")
            row[f"level_{cut}"] = (
                None if cert["certified"] is None
                else "High" if cert["certified"]
                else "Medium" if score is not None and t is not None and score >= t
                else "Low"
            )  # fmt: skip
        out.append(row)
    assert len(out) == len(certified), f"{len(out)} rows, certified.jsonl has {len(certified)}"
    assert differ == 0, (
        f"{differ} rows where ask() here is not certified.jsonl's: the scores are not the certificate's "
        f"(by family: {dict(differing)})"
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(row) + "\n" for row in out), encoding="utf-8")
    rated = [r for r in out if r["certified"] is not None]
    print(f"{len(out)} questions, {len(rated)} rated, {sum(r['certified'] for r in rated)} certified, "
          f"0 rows differ from certified.jsonl, {sum(r['score'] is None for r in rated)} rated without a score, "
          f"{sum(r['mismatch'] for r in out)} mismatch -> {a.out}")  # fmt: skip


if __name__ == "__main__":
    main()
