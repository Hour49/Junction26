"""`stoa_eval services-gen` and `services-score`: the hard services questions (services.py).

services-gen MODEL.ifc ... --manifest M.json [--out DIR]
    each model's graph (`services_backend.py` in backend/'s environment, cached in
    DIR/graphs/<stem>.json; a model that fails to parse is skipped and named), then
    DIR/questions.jsonl (every split, each row with its split) and DIR/oracle.jsonl (the
    truth as answers, which scores 100 %). DIR defaults to data/stoa/services (gitignored:
    the questions name the dataset's models and elements).
services-score QUESTIONS ANSWERS [--split dev|heldout] [--milestone] [--name N --note T]
    ANSWERS: one {"id", "value", "refused", "reason"} line per question (a missing line is
    wrong). The held-out buildings only with --milestone. With --name, the aggregates (no
    names) go to eval/results/services/runs/<time>-<name>.json; commit that with the PR.
"""

import argparse
import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import backend
from .run_store import slug
from .services import (
    ServicesAnswer,
    ServicesGraph,
    ServicesQuestion,
    format_report,
    generate,
    score,
    split_of,
)

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data/stoa/services"
RESULTS = Path(__file__).resolve().parents[1] / "results/services/runs"


def run_gen(args: argparse.Namespace) -> None:
    manifest = json.loads(args.manifest.read_text("utf-8"))
    rows: list[ServicesQuestion] = []
    for ifc in args.ifc:
        split = split_of(ifc.stem, manifest)
        graph_path = args.out / "graphs" / f"{ifc.stem}.json"
        if not graph_path.exists():
            try:
                backend.run(
                    "graph", "--ifc", str(ifc.resolve()), "--out", str(graph_path.resolve()),
                    script=backend.SERVICES_SCRIPT,
                )  # fmt: skip
            except ValueError as error:
                print(f"skipped {ifc.stem}: {error}")
                continue
        graph = ServicesGraph.model_validate_json(graph_path.read_text("utf-8"))
        made = generate(graph, split, args.seed)
        print(f"{ifc.stem} ({split}): {len(graph.nodes)} nodes, {len(graph.edges)} edges, "
              f"{len(made) // 4} questions")  # fmt: skip
        rows += made
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "questions.jsonl").open("w", encoding="utf-8") as f:
        f.writelines(row.model_dump_json() + "\n" for row in rows)
    oracle = [
        ServicesAnswer(id=r.id, value=r.truth, refused=not r.answerable, reason=r.reason)
        for r in rows
    ]
    with (args.out / "oracle.jsonl").open("w", encoding="utf-8") as f:
        f.writelines(a.model_dump_json() + "\n" for a in oracle)
    print(f"wrote {len(rows)} rows ({len(rows) // 4} questions x 4 phrasings) to {args.out}")


def run_score(args: argparse.Namespace) -> None:

    if args.split == "heldout" and not args.milestone:
        raise ValueError("the held-out buildings are scored once per milestone: add --milestone")
    text = args.questions.read_text("utf-8")
    questions = [
        q
        for line in text.splitlines()
        if line.strip() and (q := ServicesQuestion.model_validate_json(line)).split == args.split
    ]
    if not questions:
        raise ValueError(f"no {args.split} questions in {args.questions}")
    answers = [
        ServicesAnswer.model_validate_json(line)
        for line in args.answers.read_text("utf-8").splitlines()
        if line.strip()
    ]
    report = score(questions, answers)
    print(f"{args.split}: {len(questions)} rows")
    print(format_report(report))
    if args.name:
        commit, dirty = args.git_commit()
        now = datetime.now(ZoneInfo("Europe/Helsinki"))
        record = {
            "recorded_at": now.isoformat(timespec="seconds"), "commit": commit, "dirty": dirty,
            "name": args.name, "note": args.note, "split": args.split,
            "questions_sha256": hashlib.sha256(text.encode()).hexdigest(), "report": report,
        }  # fmt: skip
        args.results.mkdir(parents=True, exist_ok=True)
        out = args.results / f"{now:%Y%m%d-%H%M%S}-{slug(args.name)}.json"
        out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
        print(f"recorded {args.name!r} in {out} (commit it with your PR)")


def add_parsers(commands: Any, git_commit: Callable[[], tuple[str, bool]]) -> None:
    """The two subcommands on cli's parser; `git_commit` is cli's (short sha, dirty)."""
    gen = commands.add_parser("services-gen", help="hard services questions from IFC models")
    gen.add_argument("ifc", type=Path, nargs="+", help="IFC services models")
    gen.add_argument(
        "--manifest", type=Path, required=True, help='{"dev": [...], "heldout": [...]}'
    )
    gen.add_argument("--out", type=Path, default=OUT)
    gen.add_argument("--seed", type=int, default=14)
    gen.set_defaults(run=run_gen)
    scored = commands.add_parser("services-score", help="score answers to the services questions")
    scored.add_argument("questions", type=Path)
    scored.add_argument("answers", type=Path, help="services answer lines")
    scored.add_argument("--split", choices=["dev", "heldout"], default="dev")
    scored.add_argument("--milestone", action="store_true", help="needed for the held-out split")
    scored.add_argument("--name", help="record the aggregates under this method name")
    scored.add_argument("--note", default="", help="a line for the record (no paths)")
    scored.add_argument("--results", type=Path, default=RESULTS)
    scored.set_defaults(run=run_score, git_commit=git_commit)
