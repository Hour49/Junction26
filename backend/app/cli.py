r"""Command line entry point. Run from backend/:

    uv run python -m app.cli golden --golden-dir ../data/stoa/golden/v2 \
        --dataset ../data/stoa/full/junction-dataset --drawings pipeline \
        --out ../data/stoa/runs/<name>

`golden` runs the pipeline on a golden v2 folder and writes what eval/ scores:

    <out>/extraction/<source>/<name>.json   one extraction_v1 per Part 1 file (--drawings pipeline)
    <out>/ingest.json                       what each stage did to each file (--drawings pipeline)
    <out>/answers.jsonl                     one answer_v1 line per Part 2 question

`--drawings pipeline` ingests the Part 1 files and answers from the pipeline's own extraction.
`--drawings gold` skips ingest and answers from the Part 1 gold, which takes reading errors out
(a Part 2 run). backend/README.md has the scoring commands.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from app.adapters.answer_v1 import AnswerV1Writer
from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.adapters.golden_dir import GoldenDir
from app.composition import build_pipeline
from app.core.errors import DomainError, InvalidInputError
from app.settings import Settings


def run_golden(args: argparse.Namespace, settings: Settings) -> None:
    out: Path = args.out
    if out.exists() and any(out.iterdir()):
        raise InvalidInputError(f"{out} is not empty: give each run its own --out folder")
    golden = GoldenDir(args.golden_dir)
    pipeline = build_pipeline(settings, args.dataset)
    if args.drawings == "pipeline":
        files = golden.files()
        extraction = out / "extraction"
        extraction.mkdir(parents=True)
        writer = ExtractionV1Writer(extraction, {file.file: file.split for file in files})
        report = pipeline.ingest([file.file for file in files], writer)
        (out / "ingest.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(
            f"ingest: {len(report.sheets)} drawing models in {extraction}, "
            f"{len(report.set_aside)} files set aside (details in {out / 'ingest.json'})"
        )
        drawings = ExtractionV1Reader(extraction)
    else:
        drawings = ExtractionV1Reader(golden.gold)
    answers = out / "answers.jsonl"
    methods = pipeline.answer_questions(golden.questions(), drawings, AnswerV1Writer(answers))
    print(f"answering: {sum(methods.values())} answers in {answers}")
    for method, count in sorted(methods.items()):
        print(f"  {count:6d}  {method}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m app.cli")
    commands = root.add_subparsers(dest="command", required=True)
    golden = commands.add_parser("golden", help="run the pipeline on a golden v2 folder")
    golden.add_argument("--golden-dir", type=Path, required=True, help="e.g. data/stoa/golden/v2")
    golden.add_argument(
        "--dataset", type=Path, required=True, help="the unzipped dataset (holds data/<source>/)"
    )
    golden.add_argument(
        "--drawings",
        choices=["pipeline", "gold"],
        required=True,
        help="answer from the pipeline's own extraction, or from the Part 1 gold",
    )
    golden.add_argument("--out", type=Path, required=True, help="a new folder for this run")
    golden.set_defaults(run=run_golden)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    try:
        args.run(args, settings)
    except DomainError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
