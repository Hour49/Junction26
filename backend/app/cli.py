r"""Command line entry point. Run from backend/:

    uv run python -m app.cli golden --golden-dir ../data/stoa/golden/v2 \
        --dataset ../data/stoa/full/junction-dataset --drawings pipeline \
        --out ../data/stoa/runs/<name>

`golden` runs the pipeline on a golden v2 folder and writes what eval/ scores:

    <out>/extraction/<source>/<name>.json   one extraction_v1 per Part 1 file (--drawings pipeline)
    <out>/ingest.json                       what each stage did to each file (--drawings pipeline)
    <out>/answers.jsonl                     one answer_v1 line per Part 2 question, and per line
                                            of part2_answering/extras.jsonl when the folder has it

`--drawings pipeline` ingests the Part 1 files and answers from the pipeline's own extraction.
`--drawings gold` skips ingest and answers from the Part 1 gold, which takes reading errors out
(a Part 2 run). backend/README.md has the scoring commands.

`answer` does the same for any questions file in the dataset's format (the dataset's
questions.jsonl, data/stoa/split/dev.jsonl): every drawing a question names is ingested once,
then every question is answered from it. Same three outputs.

    uv run python -m app.cli answer --questions ../data/stoa/split/dev.jsonl \
        --dataset ../data/stoa/full/junction-dataset --out ../data/stoa/runs/<name>

The sealed eval side of the split is refused unless `--milestone` is given.
"""

import argparse
import logging
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.adapters.answer_v1 import AnswerV1Writer
from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer, Split
from app.adapters.golden_dir import GoldenDir
from app.adapters.questions_file import QuestionsFile
from app.composition import Pipeline, build_pipeline
from app.core.answering.model import Question
from app.core.answering.ports import DrawingSource
from app.core.errors import DomainError, InvalidInputError
from app.settings import Settings

# The sealed split of this checkout (eval/README.md), when it has been made.
SPLIT_DIR = Path(__file__).resolve().parents[2] / "data" / "stoa" / "split"


def run_golden(args: argparse.Namespace, settings: Settings) -> None:
    out = _new_folder(args.out)
    golden = GoldenDir(args.golden_dir)
    pipeline = build_pipeline(settings, args.dataset)
    if args.drawings == "pipeline":
        drawings = _ingest(pipeline, {file.file: file.split for file in golden.files()}, out)
    else:
        drawings = ExtractionV1Reader(golden.gold)
    extras = golden.extras()
    _answer(
        pipeline, [*golden.questions(), *extras], drawings, out, f"{len(extras)} of them extras"
    )


def run_answer(args: argparse.Namespace, settings: Settings) -> None:
    out = _new_folder(args.out)
    asked = QuestionsFile(args.questions)
    sealed = asked.sealed_by(args.split_dir)
    if sealed is not None and not args.milestone:
        raise InvalidInputError(
            f"{args.questions} is the sealed eval side of the split ({sealed}): it is answered "
            "only at a milestone, with --milestone"
        )
    questions = asked.questions()
    split: Split = "dev" if sealed is None else "eval"
    pipeline = build_pipeline(settings, args.dataset)
    files: dict[str, Split] = {question.file: split for question in questions}
    _answer(pipeline, questions, _ingest(pipeline, files, out), out, f"about {len(files)} files")


def _new_folder(out: Path) -> Path:
    if out.exists() and any(out.iterdir()):
        raise InvalidInputError(f"{out} is not empty: give each run its own --out folder")
    return out


def _ingest(pipeline: Pipeline, splits: Mapping[str, Split], out: Path) -> ExtractionV1Reader:
    """Ingests the files (each with the side of the split it is on) into <out>/extraction and
    <out>/ingest.json. Returns the drawing models it wrote."""
    extraction = out / "extraction"
    extraction.mkdir(parents=True)
    report = pipeline.ingest(list(splits), ExtractionV1Writer(extraction, splits))
    (out / "ingest.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        f"ingest: {len(report.sheets)} drawing models in {extraction}, "
        f"{len(report.set_aside)} files set aside (details in {out / 'ingest.json'})"
    )
    return ExtractionV1Reader(extraction)


def _answer(
    pipeline: Pipeline, questions: Sequence[Question], drawings: DrawingSource, out: Path, what: str
) -> None:
    answers = out / "answers.jsonl"
    methods = pipeline.answer_questions(questions, drawings, AnswerV1Writer(answers))
    print(f"answering: {sum(methods.values())} answers in {answers}, {what}")
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
    answer = commands.add_parser("answer", help="run the pipeline on a questions file")
    answer.add_argument(
        "--questions",
        type=Path,
        required=True,
        help="JSONL in the dataset's format (path, question)",
    )
    answer.add_argument(
        "--dataset", type=Path, required=True, help="the unzipped dataset (holds data/<source>/)"
    )
    answer.add_argument("--out", type=Path, required=True, help="a new folder for this run")
    answer.add_argument(
        "--milestone", action="store_true", help="needed to answer the sealed eval split"
    )
    answer.add_argument(
        "--split-dir", type=Path, default=SPLIT_DIR, help="the sealed split (its manifest.json)"
    )
    answer.set_defaults(run=run_answer)
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
