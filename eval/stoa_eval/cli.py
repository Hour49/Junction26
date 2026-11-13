"""Command line: `python -m stoa_eval <select|baseline|score|schema>` (run from eval/)."""

import argparse
import hashlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast, get_args

from . import baselines
from .jsonl import read_jsonl, write_jsonl
from .models import SCHEMA_DIR, Answer, GoldenItem, Question, render_schemas
from .scoring import format_table, score
from .selection import CellKey, Manifest, SelectionParams, annotate, select

REPO = Path(__file__).resolve().parents[2]
DEFAULT_QUESTIONS = REPO / "data/stoa/full/junction-dataset/questions.jsonl"
GOLDEN_DIR = REPO / "data/stoa/golden"  # gitignored: derived from partner data
DEFAULT_GOLDEN = GOLDEN_DIR / "golden_v0.jsonl"
RUNS_DIR = GOLDEN_DIR / "runs"


def manifest_path(golden: Path) -> Path:
    return golden.with_name(f"{golden.stem}.manifest.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cell_keys(text: str) -> tuple[CellKey, ...]:
    keys = tuple(key.strip() for key in text.split(","))
    allowed = get_args(CellKey)
    if not keys or any(key not in allowed for key in keys):
        raise argparse.ArgumentTypeError(f"cell keys are a comma list of {', '.join(allowed)}")
    return cast(tuple[CellKey, ...], keys)


def run_select(args: argparse.Namespace) -> None:
    params = SelectionParams(
        version=args.version,
        cell_keys=args.cell_keys,
        per_cell=args.per_cell,
        holdout_ratio=args.holdout_ratio,
        seed=args.seed,
    )
    selection = select(read_jsonl(args.questions, Question), params)
    golden = args.out_dir / f"golden_{params.version}.jsonl"
    write_jsonl(golden, selection.items)
    manifest = Manifest(
        params=params,
        questions_sha256=_sha256(args.questions),
        cells=selection.cells,
        holdout_groups=selection.holdout_groups,
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
        f"{dev + holdout} questions (dev {dev}, holdout {holdout}) "
        f"in {len(selection.cells)} cells, {len(short)} cells short of {params.per_cell}; "
        f"{len(selection.holdout_groups)} holdout drawing groups"
    )
    print(f"wrote {golden} and {manifest_path(golden).name}")


def run_baseline(args: argparse.Namespace) -> None:
    golden = [item for _, item in read_jsonl(args.golden, GoldenItem)]
    if args.name == "oracle":
        answers = baselines.oracle(golden)
    else:
        manifest = Manifest.model_validate_json(manifest_path(args.golden).read_text("utf-8"))
        if _sha256(args.questions) != manifest.questions_sha256:
            raise ValueError(f"{args.questions} is not the file {args.golden.name} was made from")
        pool = annotate(read_jsonl(args.questions, Question), manifest.params)
        if sorted({row.group for row in pool if row.split == "holdout"}) != manifest.holdout_groups:
            raise ValueError("the split differs from the manifest's: the selection code changed")
        answers = baselines.constant(golden, pool)
    out = args.out or RUNS_DIR / f"{args.name}.jsonl"
    write_jsonl(out, answers)
    print(f"wrote {len(answers)} answers to {out}")


def run_score(args: argparse.Namespace) -> None:
    golden = [item for _, item in read_jsonl(args.golden, GoldenItem)]
    answers = [answer for _, answer in read_jsonl(args.answers, Answer)]
    result = score(golden, answers)
    print(format_table(result))
    out = args.out or args.answers.with_suffix(".score.json")
    out.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


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

    chosen = commands.add_parser("select", help="pick the golden set from questions.jsonl")
    chosen.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
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
    baseline.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    baseline.add_argument("--out", type=Path, help="default: data/stoa/golden/runs/<name>.jsonl")
    baseline.set_defaults(run=run_baseline)

    scored = commands.add_parser("score", help="score an answers file against the golden set")
    scored.add_argument("answers", type=Path)
    scored.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    scored.add_argument("--out", type=Path, help="default: <answers>.score.json")
    scored.set_defaults(run=run_score)

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
