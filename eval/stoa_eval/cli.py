"""Command line: `python -m stoa_eval <split|select|baseline|score|history|schema>` (from eval/)."""

import argparse
import hashlib
import subprocess
import sys
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import cast, get_args
from zoneinfo import ZoneInfo

from . import baselines
from .coverage import format_coverage_table, load_answers, score_all
from .families import group_of
from .history import append_record, format_history, make_record, read_history, write_history_csv
from .jsonl import iter_jsonl, read_jsonl, write_jsonl
from .models import SCHEMA_DIR, Answer, GoldenItem, NumberedQuestion, Question, render_schemas
from .scoring import format_table, score
from .selection import CellKey, Manifest, SelectionParams, annotate, select
from .split import (
    DEFAULT_EVAL_SHARE,
    DEFAULT_SEED,
    SPLIT_NAMES,
    SplitManifest,
    eval_groups,
    group_sizes,
    split_counts,
)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_QUESTIONS = REPO / "data/stoa/full/junction-dataset/questions.jsonl"
SPLIT_DIR = REPO / "data/stoa/split"  # gitignored, like everything derived from partner data
GOLDEN_DIR = REPO / "data/stoa/golden"
DEFAULT_GOLDEN = GOLDEN_DIR / "golden_v1.jsonl"
RUNS_DIR = GOLDEN_DIR / "runs"
SPLIT_MANIFEST = "manifest.json"
EVAL_WARNING = "warning: sealed split: score at milestones only"
RESULTS = Path(__file__).resolve().parents[1] / "results/runs.jsonl"  # tracked: aggregates only
HELSINKI = ZoneInfo("Europe/Helsinki")


def manifest_path(golden: Path) -> Path:
    return golden.with_name(f"{golden.stem}.manifest.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _split_manifest(split_dir: Path, questions: Path | None = None) -> SplitManifest:
    """The split's manifest, after checking that dev.jsonl and eval.jsonl are the files it wrote
    and, given `questions`, that the split was made from that file."""
    path = split_dir / SPLIT_MANIFEST
    if not path.exists():
        raise ValueError(f"{path} is missing: run `python -m stoa_eval split` first")
    manifest = SplitManifest.model_validate_json(path.read_text("utf-8"))
    for name, digest in manifest.files_sha256.items():
        if _sha256(split_dir / name) != digest:
            raise ValueError(f"{split_dir / name} changed after the split: run split again")
    if questions is not None and _sha256(questions) != manifest.questions_sha256:
        raise ValueError(f"{questions} is not the file the split in {split_dir} was made from")
    return manifest


def _git_commit() -> tuple[str, bool]:
    """Short sha of HEAD, and whether tracked files have uncommitted changes."""

    def git(*args: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
        )
        return done.stdout.strip()

    try:
        return git("rev-parse", "--short", "HEAD"), bool(git("status", "--porcelain", "-uno"))
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"can't read the git commit to record the run: {error}") from error


def _cell_keys(text: str) -> tuple[CellKey, ...]:
    keys = tuple(key.strip() for key in text.split(","))
    allowed = get_args(CellKey)
    if not keys or any(key not in allowed for key in keys):
        raise argparse.ArgumentTypeError(f"cell keys are a comma list of {', '.join(allowed)}")
    return cast(tuple[CellKey, ...], keys)


def run_split(args: argparse.Namespace) -> None:
    sizes = group_sizes(question for _, question in iter_jsonl(args.questions, Question))
    sealed = eval_groups(sizes, args.eval_share, args.seed)
    paths = {name: args.out_dir / f"{name}.jsonl" for name in SPLIT_NAMES}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (
        paths["dev"].open("w", encoding="utf-8") as dev,
        paths["eval"].open("w", encoding="utf-8") as held,
    ):
        files = {"dev": dev, "eval": held}

        def written() -> Iterator[tuple[Question, str]]:
            for line, question in iter_jsonl(args.questions, Question):
                split = "eval" if group_of(question.path) in sealed else "dev"
                row = NumberedQuestion(**question.model_dump(), id=line)
                files[split].write(row.model_dump_json() + "\n")
                yield question, split

        counts = split_counts(written())
    manifest = SplitManifest(
        seed=args.seed,
        eval_share_target=args.eval_share,
        questions_sha256=_sha256(args.questions),
        files_sha256={path.name: _sha256(path) for path in paths.values()},
        by_source=counts["source"],
        by_source_type=counts["source_type"],
        eval_groups=sorted(sealed),
    )
    (args.out_dir / SPLIT_MANIFEST).write_text(manifest.model_dump_json(indent=2) + "\n", "utf-8")
    print(
        f"{'source':<30} {'questions dev':>13} {'eval':>6} {'share':>6} "
        f"{'groups dev':>10} {'eval':>5}"
    )
    for level in (manifest.by_source, manifest.by_source_type):
        for key, count in level.items():
            share = f"{count.eval_share:.1%}" if count.eval_share is not None else "n/a"
            print(
                f"{key:<30} {count.dev_questions:>13} {count.eval_questions:>6} {share:>6} "
                f"{count.dev_groups:>10} {count.eval_groups:>5}"
            )
        print()
    print(f"wrote {', '.join(str(path) for path in paths.values())} and {SPLIT_MANIFEST}")


def run_select(args: argparse.Namespace) -> None:
    params = SelectionParams(
        version=args.version,
        cell_keys=args.cell_keys,
        per_cell=args.per_cell,
        holdout_ratio=args.holdout_ratio,
        seed=args.seed,
    )
    split = _split_manifest(args.split_dir, args.questions)
    selection = select(read_jsonl(args.questions, Question), params, set(split.eval_groups))
    golden = args.out_dir / f"golden_{params.version}.jsonl"
    write_jsonl(golden, selection.items)
    manifest = Manifest(
        params=params,
        questions_sha256=split.questions_sha256,
        split_manifest_sha256=_sha256(args.split_dir / SPLIT_MANIFEST),
        cells=selection.cells,
    )
    manifest_path(golden).write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    width = max(len(" ".join(cell.cell.values())) for cell in selection.cells)
    print(f"{'cell':<{width}}  available  dev  holdout")
    for cell in selection.cells:
        name = " ".join(cell.cell.values())
        print(f"{name:<{width}}  {cell.available:>9}  {cell.dev:>3}  {cell.holdout:>7}")
    dev = sum(cell.dev for cell in selection.cells)
    holdout = sum(cell.holdout for cell in selection.cells)
    short = [cell for cell in selection.cells if cell.dev + cell.holdout < params.per_cell]
    print(
        f"{dev + holdout} questions (dev {dev}, holdout {holdout} from the eval split) "
        f"in {len(selection.cells)} cells, {len(short)} cells short of {params.per_cell}"
    )
    print(f"wrote {golden} and {manifest_path(golden).name}")


def run_baseline(args: argparse.Namespace) -> None:
    golden = [item for _, item in read_jsonl(args.golden, GoldenItem)]
    if args.name == "oracle":
        answers = baselines.oracle(golden)
    else:
        manifest = Manifest.model_validate_json(manifest_path(args.golden).read_text("utf-8"))
        _split_manifest(args.split_dir)
        if _sha256(args.split_dir / SPLIT_MANIFEST) != manifest.split_manifest_sha256:
            raise ValueError(
                f"{args.golden.name} was made from another split than {args.split_dir}"
            )
        dev = [
            (row.id, row) for _, row in iter_jsonl(args.split_dir / "dev.jsonl", NumberedQuestion)
        ]
        answers = baselines.constant(golden, annotate(dev, holdout=set()))
    out = args.out or RUNS_DIR / f"{args.name}.jsonl"
    write_jsonl(out, answers)
    print(f"wrote {len(answers)} answers to {out}")


def run_score(args: argparse.Namespace) -> None:
    if args.record and not args.name:
        raise ValueError("--record needs --name <method name>")
    if args.record and args.against == "eval" and not args.milestone:
        raise ValueError(
            "refused: a run against the sealed eval split is recorded only with --milestone"
        )
    golden_version: str | None = None
    if args.against == "golden":
        golden = [item for _, item in read_jsonl(args.golden, GoldenItem)]
        manifest = Manifest.model_validate_json(manifest_path(args.golden).read_text("utf-8"))
        golden_version, questions_sha256 = manifest.params.version, manifest.questions_sha256
        result = score(golden, [answer for _, answer in read_jsonl(args.answers, Answer)])
        print(format_table(result))
        out = args.out or args.answers.with_suffix(".score.json")
    else:
        questions_sha256 = _split_manifest(args.split_dir).questions_sha256
        if args.against == "eval":
            print(EVAL_WARNING, file=sys.stderr)
        names = SPLIT_NAMES if args.against == "all" else (args.against,)
        answers = load_answers(iter_jsonl(args.answers, Answer))
        questions = (
            (row, name)
            for name in names
            for _, row in iter_jsonl(args.split_dir / f"{name}.jsonl", NumberedQuestion)
        )
        result = score_all(questions, answers)
        print(format_coverage_table(result, args.top))
        out = args.out or args.answers.with_suffix(f".score-{args.against}.json")
    out.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    if args.record:
        commit, dirty = _git_commit()
        record = make_record(
            result,
            against=args.against,
            name=args.name,
            note=args.note,
            milestone=args.milestone,
            golden_version=golden_version,
            questions_sha256=questions_sha256,
            score_sha256=_sha256(out),
            commit=commit,
            dirty=dirty,
            now=datetime.now(HELSINKI),
        )
        append_record(args.results, record)
        print(f"recorded {args.name!r} in {args.results}")


def run_history(args: argparse.Namespace) -> None:
    records = read_history(args.results, args.against)
    print(format_history(records))
    if args.csv:
        write_history_csv(args.csv, records)
        print(f"wrote {args.csv}")


def run_schema(args: argparse.Namespace) -> None:
    for name, text in render_schemas().items():
        path = SCHEMA_DIR / name
        if args.check:
            if not path.exists() or path.read_text("utf-8") != text:
                raise ValueError(f"{path} is stale: run `python -m stoa_eval schema`")
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path}")


def parser() -> argparse.ArgumentParser:
    defaults = SelectionParams()
    root = argparse.ArgumentParser(prog="python -m stoa_eval", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    sealed = commands.add_parser("split", help="write the sealed 80/20 dev/eval split")
    sealed.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    sealed.add_argument("--out-dir", type=Path, default=SPLIT_DIR)
    sealed.add_argument("--eval-share", type=float, default=DEFAULT_EVAL_SHARE)
    sealed.add_argument("--seed", type=int, default=DEFAULT_SEED)
    sealed.set_defaults(run=run_split)

    chosen = commands.add_parser("select", help="pick the golden set from questions.jsonl")
    chosen.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    chosen.add_argument("--split-dir", type=Path, default=SPLIT_DIR)
    chosen.add_argument("--out-dir", type=Path, default=GOLDEN_DIR)
    chosen.add_argument("--version", default=defaults.version)
    chosen.add_argument("--cell-keys", type=_cell_keys, default=defaults.cell_keys)
    chosen.add_argument("--per-cell", type=int, default=defaults.per_cell)
    chosen.add_argument("--holdout-ratio", type=float, default=defaults.holdout_ratio)
    chosen.add_argument("--seed", type=int, default=defaults.seed)
    chosen.set_defaults(run=run_select)

    baseline = commands.add_parser("baseline", help="write oracle or constant answers")
    baseline.add_argument("name", choices=["oracle", "constant"])
    baseline.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    baseline.add_argument("--split-dir", type=Path, default=SPLIT_DIR)
    baseline.add_argument("--out", type=Path, help="default: data/stoa/golden/runs/<name>.jsonl")
    baseline.set_defaults(run=run_baseline)

    scored = commands.add_parser("score", help="score an answers file")
    scored.add_argument("answers", type=Path)
    scored.add_argument(
        "--against",
        choices=["golden", "all", "dev", "eval"],
        default="golden",
        help="golden: the golden set, where a missing answer is wrong. all, dev, eval: the "
        "questions of the sealed split, reporting coverage and accuracy on the answered",
    )
    scored.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    scored.add_argument("--split-dir", type=Path, default=SPLIT_DIR)
    scored.add_argument("--top", type=int, default=20, help="templates printed for all/dev/eval")
    scored.add_argument(
        "--out", type=Path, help="default: <answers>.score.json, or .score-<against>.json"
    )
    scored.add_argument("--record", action="store_true", help="append a summary row to --results")
    scored.add_argument("--name", help="the method's name, for --record")
    scored.add_argument("--note", help="a short note for --record")
    scored.add_argument("--milestone", action="store_true", help="needed to record an eval run")
    scored.add_argument("--results", type=Path, default=RESULTS)
    scored.set_defaults(run=run_score)

    history = commands.add_parser("history", help="print the recorded runs, oldest first")
    history.add_argument("--against", choices=["golden", "all", "dev", "eval"])
    history.add_argument("--results", type=Path, default=RESULTS)
    history.add_argument("--csv", type=Path, help="also write the table as CSV, for a chart")
    history.set_defaults(run=run_history)

    schema = commands.add_parser("schema", help="write the JSON Schemas into eval/schemas/")
    schema.add_argument("--check", action="store_true", help="fail if a committed one is stale")
    schema.set_defaults(run=run_schema)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.run(args)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0
