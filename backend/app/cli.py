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

`glb` builds the 3D views (MODEL_3D) ahead, for a deploy: of every IFC file of each project given
by id, and of each IFC file given by path (cached by content, so the same file uploaded later is
served at once). A view that was unavailable is tried again. Exit 1 when one is not ready.

    uv run python -m app.cli glb <project id or file.ifc> ...
"""

import argparse
import hashlib
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path

from app.adapters.answer_v1 import AnswerV1Writer
from app.adapters.archive.store import DiskProjectStore
from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer, Split
from app.adapters.golden_dir import GoldenDir
from app.adapters.ifc_model.glb import GlbModels
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


def run_glb(args: argparse.Namespace, settings: Settings) -> int:
    models = GlbModels(
        settings.projects_dir / "models-3d",
        settings.model_3d_memory_mb,
        settings.model_3d_timeout_s,
    )
    store = DiskProjectStore(settings.projects_dir)
    known = set(store.project_ids())
    files: list[tuple[str, Callable[[], bytes]]] = []
    for given in args.targets:
        if given in known:
            status = store.load_project(given)[0]
            files += [
                (f"{given}/{file.path}", partial(store.read_upload, given, file.path))
                for file in status.files
                if file.kind == "ifc"
            ]
        elif Path(given).is_file():
            files.append((given, Path(given).read_bytes))
        else:
            raise InvalidInputError(f"{given} is no project id and no file")
    ready = True
    for name, read in files:
        data = read()
        found = models.convert(hashlib.sha256(data).hexdigest(), data)
        if found.state == "ready":
            print(f"{name}: ready, {found.elements} elements")
        else:
            print(f"{name}: unavailable ({found.code}): {found.reason}")
            ready = False
    return 0 if ready else 1


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


def run_disc_render(args: argparse.Namespace, settings: Settings) -> None:
    from app.adapters.ifc_model import plan_picture  # ifcopenshell only when asked

    sheets = plan_picture.read_plans(args.model, args.background)
    for dpi in args.dpi:
        for variant in args.variant:
            out = args.out / f"{variant}-{dpi}"
            pictures = plan_picture.draw_plans(
                sheets, out, dpi=dpi, variant=variant, seed=args.seed
            )
            print(f"{len(pictures)} pictures in {out}")


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
    bench = commands.add_parser("disc-bench", help="discipline picture bench").add_subparsers(
        dest="step", required=True
    )
    render = bench.add_parser("render", help="plan pictures and their truth from an IFC model")
    render.add_argument("--model", type=Path, required=True, help="a services model (.ifc)")
    render.add_argument("--background", type=Path, help="the same building's architecture")
    render.add_argument(
        "--out", type=Path, required=True, help="pictures and truth go to <out>/<variant>-<dpi>/"
    )
    render.add_argument("--dpi", type=int, nargs="+", default=[150])
    render.add_argument(
        "--variant",
        nargs="+",
        default=["clean"],
        choices=["clean", "scan", "photo", "no-legend", "no-scale"],
    )
    render.add_argument("--seed", type=int, default=0)
    render.set_defaults(run=run_disc_render)
    glb = commands.add_parser("glb", help="build the 3D views of IFC files ahead (MODEL_3D)")
    glb.add_argument("targets", nargs="+", help="project ids (data/projects) or IFC file paths")
    glb.set_defaults(run=run_glb)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    try:
        failed = args.run(args, settings)
    except DomainError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return failed or 0


if __name__ == "__main__":
    sys.exit(main())
