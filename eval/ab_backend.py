"""The backend half of `stoa_eval ab` and `stoa_eval gate`: runs in backend/'s environment, with
backend/ on the path, and uses the backend as a library, so the experiments are answered by the
same parser and takeoff the pipeline runs. `stoa_eval` starts it; nobody needs to call it by hand.

    answer   --questions Q --drawings DIR --out A.jsonl [--prior TABLE [--policy P]]
             answers every question of Q from the extraction_v1 files in DIR (the pipeline's
             answering, `Pipeline.answer_questions`, with QUESTION_PARSER=templates); a file
             missing from DIR is refused. With --prior, a refusal carries that table's value.
             With --policy P (an answer_policy_v1 file, read by the backend's own ANSWER_POLICY
             loader) as well, the families P sends to the prior are answered from --prior and
             nothing else is: a refusal stays null, so the arm differs from the plain one by the
             policy alone.
    prior    --train Q --out TABLE
             fits the answer prior (`app.adapters.answer_prior.build`) on the experiment's train
             questions only (data/stoa/exp/train_questions.jsonl), never val, test or dev.jsonl.
    families --questions Q --out F.json
             question id -> the parser's family (`unsupported` when it can't read the question).
    g1main   --replies DIR --questions Q --dataset ROOT --out D.json
             dataset path -> family -> {count: probability}: Gemini Decisions' G1main replies,
             read by the backend's own parser (`app.adapters.decisions.g1main.parse`), the
             distribution DECISIONS_CONFIDENCE reads at runtime. DIR is decide's cache (one JSON
             per image: {file, request, response}; a reply asked with other questions is refused)
             or the backend's own DECISIONS_CACHE_DIR (every name <image sha256>-<question
             set>-...), read for Q's drawings under ROOT by the backend's G1MainReader, which never
             calls the API here: a page not in that cache gets no distribution.
    swap     --answers A.jsonl --questions Q --replies DIR --arm ARM --out B.jsonl
             the answers after the Decisions count swap of ARM (`SWAP_ARMS`, e.g. S1536) with the
             backend's own rule (`app.adapters.decisions.uses.swapped`): a count of a family the arm
             swaps becomes Gemini's own count when Gemini gives it less than the arm's threshold. An
             image without a reply keeps its answers, as at runtime.
"""

import argparse
import dataclasses
import hashlib
import json
import re
import sys
from pathlib import Path

from app.adapters.answer_prior import TablePrior, build
from app.adapters.answer_v1 import AnswerV1Writer
from app.adapters.decisions.client import MODEL, DecisionsError
from app.adapters.decisions.g1main import (
    QUESTIONS_SHA,
    CountDist,
    G1MainReader,
    PageCounts,
    parse,
)
from app.adapters.decisions.uses import SWAP_ARMS, swapped
from app.adapters.extraction_v1 import ExtractionV1Reader
from app.adapters.question_templates import TemplateParser
from app.adapters.questions_file import QuestionsFile
from app.composition import build_pipeline
from app.core.answering.model import Prior, Unsupported
from app.core.answering.ports import AnswerPrior
from app.settings import Settings

TRAIN_QUESTIONS = "train_questions.jsonl"


class _PolicyOnly:
    """The prior for the answer policy's (source, family) pairs only."""

    def __init__(self, prior: AnswerPrior, pairs: frozenset[tuple[str, str]]) -> None:
        self._prior = prior
        self._pairs = pairs

    def prior(self, source: str, family: str) -> Prior | None:
        return self._prior.prior(source, family) if (source, family) in self._pairs else None


def answer(args: argparse.Namespace) -> None:
    if args.policy is not None and args.prior is None:
        raise SystemExit("--policy answers its families from --prior: give both")
    policy = "" if args.policy is None else str(args.policy)
    settings = Settings(question_parser="templates", answer_prior="none", answer_policy=policy)
    pipeline = build_pipeline(settings, args.dataset)
    if args.prior is not None:
        table = TablePrior(args.prior)
        prior = table if args.policy is None else _PolicyOnly(table, pipeline.prior_families)
        pipeline = dataclasses.replace(pipeline, prior=prior)
    questions = QuestionsFile(args.questions).questions()
    args.out.unlink(missing_ok=True)
    pipeline.answer_questions(
        questions, ExtractionV1Reader(args.drawings), AnswerV1Writer(args.out)
    )


def prior(args: argparse.Namespace) -> None:
    if args.train.name != TRAIN_QUESTIONS:  # val and test must not leak into the prior
        raise SystemExit(f"{args.train} is not the experiment's {TRAIN_QUESTIONS}")
    with args.train.open(encoding="utf-8") as lines:
        table = build((json.loads(line) for line in lines if line.strip()), TemplateParser())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(table, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def families(args: argparse.Namespace) -> None:
    parser = TemplateParser()
    found: dict[int, str] = {}
    for question in QuestionsFile(args.questions).questions():
        parsed = parser.parse(question.text)
        found[question.id] = "unsupported" if isinstance(parsed, Unsupported) else parsed.family()
    args.out.write_text(json.dumps(found) + "\n", encoding="utf-8")


RUNTIME_CACHE = re.compile(rf"[0-9a-f]{{64}}-{QUESTIONS_SHA[:12]}-.+\.json")


class _CacheOnly:
    """The Decisions client's model name, but no API: G1MainReader reads its cache or fails."""

    model = MODEL

    def decide(self, body: object) -> object:
        raise DecisionsError("not in the cache")


def _replies(folder: Path, questions: Path, dataset: Path) -> dict[str, dict[str, CountDist]]:
    """Dataset path -> family -> Gemini's count distribution, from decide's cached replies or the
    backend's own cache (see the module's docstring)."""
    names = [path.name for path in folder.glob("*.json")]
    if names and all(RUNTIME_CACHE.fullmatch(name) for name in names):
        reader = G1MainReader(_CacheOnly(), folder)
        files = sorted({q.file for q in QuestionsFile(questions).questions()})
        read: dict[str, dict[str, CountDist]] = {}
        for file in files:
            try:
                read[file] = reader.read((dataset / file).read_bytes()).families
            except DecisionsError:
                continue
        print(f"g1main: {len(read)} of {len(files)} drawings in the backend cache", file=sys.stderr)
        return read
    found: dict[str, dict[str, CountDist]] = {}
    for path in sorted(folder.glob("*.json")):
        cached = json.loads(path.read_text(encoding="utf-8"))
        asked = json.dumps(cached["request"]["questions"], sort_keys=True).encode()
        if hashlib.sha256(asked).hexdigest() != QUESTIONS_SHA:
            raise SystemExit(f"{path}: not asked with the backend's G1main questions")
        if cached["file"] in found:
            raise SystemExit(f"{path}: a second reply for {cached['file']}")
        found[cached["file"]] = parse(cached["response"])
    return found


def g1main(args: argparse.Namespace) -> None:
    found = {
        file: {family: dist.probs for family, dist in dists.items()}
        for file, dists in _replies(args.replies, args.questions, args.dataset).items()
    }
    args.out.write_text(json.dumps(found) + "\n", encoding="utf-8")


def swap(args: argparse.Namespace) -> None:
    if args.arm not in SWAP_ARMS:
        raise SystemExit(f"no swap arm {args.arm!r}; arms are {', '.join(SWAP_ARMS)}")
    below = SWAP_ARMS[args.arm]
    replies = _replies(args.replies, args.questions, args.dataset)
    pages = {file: PageCounts(dists, "cached reply") for file, dists in replies.items()}
    parser = TemplateParser()
    asked = {q.id: q for q in QuestionsFile(args.questions).questions()}
    lines = args.answers.read_text(encoding="utf-8").splitlines()
    with args.out.open("w", encoding="utf-8") as out:
        for line in lines:
            row = json.loads(line)
            question = asked[row["id"]]
            parsed = parser.parse(question.text)
            value = row.get("answer")
            whole = isinstance(value, int | float) and not isinstance(value, bool)
            if (
                not isinstance(parsed, Unsupported)
                and parsed.family() in below
                and question.file in pages
                and whole
                and float(value).is_integer()
            ):
                row["answer"] = swapped(int(value), pages[question.file], parsed.family(), below)
            out.write(json.dumps(row) + "\n")


def main() -> None:
    root = argparse.ArgumentParser(prog="ab_backend.py")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("answer")
    run.add_argument("--questions", type=Path, required=True)
    run.add_argument("--drawings", type=Path, required=True)
    run.add_argument("--dataset", type=Path, default=Path("."))
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--prior", type=Path)
    run.add_argument("--policy", type=Path)
    run.set_defaults(run=answer)
    fit = commands.add_parser("prior")
    fit.add_argument("--train", type=Path, required=True)
    fit.add_argument("--out", type=Path, required=True)
    fit.set_defaults(run=prior)
    kinds = commands.add_parser("families")
    kinds.add_argument("--questions", type=Path, required=True)
    kinds.add_argument("--out", type=Path, required=True)
    kinds.set_defaults(run=families)
    swaps = commands.add_parser("swap")
    swaps.add_argument("--answers", type=Path, required=True)
    swaps.add_argument("--questions", type=Path, required=True)
    swaps.add_argument("--replies", type=Path, required=True)
    swaps.add_argument("--dataset", type=Path, required=True)
    swaps.add_argument("--arm", required=True)
    swaps.add_argument("--out", type=Path, required=True)
    swaps.set_defaults(run=swap)
    replies = commands.add_parser("g1main")
    replies.add_argument("--replies", type=Path, required=True)
    replies.add_argument("--questions", type=Path, required=True)
    replies.add_argument("--dataset", type=Path, required=True)
    replies.add_argument("--out", type=Path, required=True)
    replies.set_defaults(run=g1main)
    args = root.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
