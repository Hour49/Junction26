"""Command line: `python -m stoa_eval <command>` (from eval/): split, select, select-plans,
baseline, baseline-extraction, score, score-extraction, history, validate-extraction, schema."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import cast, get_args
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from . import baselines
from .coverage import format_coverage_table, load_answers, score_all
from .extraction import Extraction
from .extraction_scoring import format_extraction_table, score_extraction
from .extras_scoring import format_slices, score_golden
from .families import group_of, source_of
from .history import (
    format_extraction_history,
    format_history,
    format_progress,
    make_extraction_record,
    make_record,
    read_extraction_history,
    read_history,
    write_extraction_csv,
    write_history_csv,
)
from .jsonl import iter_jsonl, read_jsonl, write_jsonl
from .models import (
    SCHEMA_DIR,
    Answer,
    ExtraItem,
    GoldenItem,
    NumberedQuestion,
    Question,
    render_schemas,
)
from .plans import (
    CONFLICT_EXTRA_IDS,
    ConflictFile,
    PlanFile,
    PlansManifest,
    PlansParams,
    SourceCount,
    Split,
    pick,
    pick_scale_cases,
    strata,
)
from .run_store import Part, Record, run_stem, write_record
from .scale_scoring import ScaleCase, case_of
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
GOLDEN_V2 = GOLDEN_DIR / "v2"  # two parts: extraction (part1) and answering (part2)
PART1, PART2, V2_MANIFEST = "part1_extraction", "part2_answering", "manifest.json"
EXTRAS = "extras.jsonl"  # part2_answering/extras.jsonl: questions Stoa didn't write
CONFLICTS_DIR = "_conflicts"  # under the extraction gold: conflicts.jsonl and extras.jsonl
DEFAULT_GOLDEN = GOLDEN_V2 / PART2 / "questions.jsonl"
EXTRACTION_GOLD = REPO / "data/stoa/extraction_gold"
RUNS_DIR = GOLDEN_DIR / "runs"
SPLIT_MANIFEST = "manifest.json"
EVAL_WARNING = "warning: sealed split: score at milestones only"
RESULTS = Path(__file__).resolve().parents[1] / "results/runs"  # tracked: one file per run
HELSINKI = ZoneInfo("Europe/Helsinki")


def manifest_path(golden: Path) -> Path:
    return golden.with_name(f"{golden.stem}.manifest.json")


def _golden_meta(golden: Path) -> tuple[str, str, str]:
    """(version, questions_sha256, split_manifest_sha256) of a v1 golden file or v2 part2."""
    if golden.parent.name == PART2:
        path = golden.parent.parent / V2_MANIFEST
        v2 = PlansManifest.model_validate_json(path.read_text("utf-8"))
        return v2.params.version, v2.questions_sha256, v2.split_manifest_sha256
    v1 = Manifest.model_validate_json(manifest_path(golden).read_text("utf-8"))
    return v1.params.version, v1.questions_sha256, v1.split_manifest_sha256


def _extras_for(golden: Path) -> Path | None:
    """part2_answering/extras.jsonl next to a v2 questions file, when it exists."""
    path = golden.with_name(EXTRAS)
    return path if golden.parent.name == PART2 and path.exists() else None


def _read_extras(path: Path | None) -> list[ExtraItem]:
    return [line for _, line in read_jsonl(path, ExtraItem)] if path else []


def _extractions(folder: Path) -> dict[str, tuple[Path, Extraction]]:
    """`file` -> (path, parsed) for every *.json under `folder` (none if it is missing); fails on
    an invalid file or two files naming the same drawing. Paths with a part starting "_" (reports,
    overlays) are skipped."""
    found: dict[str, tuple[Path, Extraction]] = {}
    paths = sorted(folder.rglob("*.json")) if folder.is_dir() else []
    for path in paths:
        if any(part.startswith("_") for part in path.relative_to(folder).parts):
            continue
        try:
            extraction = Extraction.model_validate_json(path.read_text("utf-8"))
        except ValidationError as error:
            raise ValueError(f"{path}: {error}") from error
        if extraction.file in found:
            raise ValueError(
                f"{path} and {found[extraction.file][0]} both describe {extraction.file}"
            )
        found[extraction.file] = (path, extraction)
    return found


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
        answers = baselines.oracle(golden, _read_extras(_extras_for(args.golden)))
    else:
        _, _, split_sha256 = _golden_meta(args.golden)
        _split_manifest(args.split_dir)
        if _sha256(args.split_dir / SPLIT_MANIFEST) != split_sha256:
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


def _recorded(args: argparse.Namespace) -> bool:
    """Whether this run is kept in the history (every golden and dev run, unless --no-record).
    Refuses a sealed-split run that is neither a --milestone nor --no-record, and a kept run
    without --name."""
    if args.against in ("eval", "all"):
        print(EVAL_WARNING, file=sys.stderr)
        if not args.milestone and not args.no_record:
            raise ValueError(
                "refused: the sealed eval split is scored as a recorded run with --milestone, or "
                "with --no-record for a look that is not kept"
            )
    if args.no_record:
        return False
    if not args.name:
        raise ValueError(
            "every scored run is recorded: give --name <method> (or --no-record for a scratch "
            "check that is not kept)"
        )
    if args.out:
        raise ValueError(
            "--out is for --no-record; a recorded run's detail goes to --runs-dir/<stem>.json"
        )
    return True


def _detail_path(args: argparse.Namespace, part: Part, default: Path) -> tuple[Path, str | None]:
    """Where the full score JSON goes, and the run's stem when it is recorded."""
    if not args.recorded:
        return args.out or default, None
    stem = run_stem(datetime.now(HELSINKI), part, args.name, [args.results, args.runs_dir])
    return args.runs_dir / f"{stem}.json", stem


def _keep(args: argparse.Namespace, stem: str, record: Record) -> None:
    path = args.results / f"{stem}.json"
    write_record(path, record)
    print(f"recorded {args.name!r} in {path} (commit it with your PR)")


def run_score(args: argparse.Namespace) -> None:
    args.recorded = _recorded(args)
    golden_version: str | None = None
    if args.against == "golden":
        golden = [item for _, item in read_jsonl(args.golden, GoldenItem)]
        golden_version, questions_sha256, _ = _golden_meta(args.golden)
        if args.recorded and golden_version != "v1" and args.reads is None:
            raise ValueError(
                "a recorded golden v2 Part 2 run needs --reads gold-extraction (the answerer read "
                "part1 gold) or --reads pipeline-extraction (it read the pipeline's own JSON)"
            )
        answers = [answer for _, answer in read_jsonl(args.answers, Answer)]
        extras_path = _extras_for(args.golden)
        extras = _read_extras(extras_path)
        extra_ids = {line.id for line in extras}
        base = score(golden, [answer for answer in answers if answer.id not in extra_ids])
        extras_sha256 = _sha256(extras_path) if extras_path else None
        result = score_golden(base, golden, answers, extras, extras_sha256)
        print(format_table(result))
        slices = format_slices(result)
        if slices:
            print(f"\n{slices}")
        out, stem = _detail_path(args, "answering", args.answers.with_suffix(".score.json"))
    else:
        questions_sha256 = _split_manifest(args.split_dir).questions_sha256
        names = SPLIT_NAMES if args.against == "all" else (args.against,)
        answers = load_answers(iter_jsonl(args.answers, Answer))
        questions = (
            (row, name)
            for name in names
            for _, row in iter_jsonl(args.split_dir / f"{name}.jsonl", NumberedQuestion)
        )
        result = score_all(questions, answers)
        print(format_coverage_table(result, args.top))
        default = args.answers.with_suffix(f".score-{args.against}.json")
        out, stem = _detail_path(args, "answering", default)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    if stem is not None:
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
            reads=args.reads if args.against == "golden" else None,
        )
        _keep(args, stem, record)


def run_select_plans(args: argparse.Namespace) -> None:
    """Golden v2 in one go: part1 (files + their extraction gold) and part2 (their questions)."""
    params = PlansParams(seed=args.seed)
    split = _split_manifest(args.split_dir, args.questions)
    sealed = set(split.eval_groups)
    rows = read_jsonl(args.questions, Question)
    stratum_of = strata(question for _, question in rows)
    chosen, counts = pick(stratum_of, sealed, params)
    dataset = args.questions.parent
    for file, part in list(chosen.items()):  # swiss: the PNG of each picked PDF plan too
        sibling = file.removesuffix(".pdf") + ".png"
        if (
            source_of(file) == "swiss_dwellings"
            and sibling != file
            and (dataset / sibling).exists()
        ):
            chosen[sibling], stratum_of[sibling] = part, stratum_of[file]
    gold = _extractions(args.gold)
    missing = sorted(file for file in chosen if file not in gold)
    if missing and not args.allow_missing_gold:
        raise ValueError(
            f"{len(missing)} picked files have no gold JSON in {args.gold} (first: "
            f"{', '.join(missing[:5])}); --allow-missing-gold lists them instead"
        )
    cases: dict[str, tuple[ScaleCase, Split]] = {
        file: (case, extraction.split)
        for file, (_, extraction) in gold.items()
        if (case := case_of(extraction)) is not None
    }
    extra, scale_counts = pick_scale_cases(cases, chosen, params)
    for file, part in extra.items():
        chosen[file], stratum_of[file] = part, "scale"
    conflicts = _conflict_files(args.gold / CONFLICTS_DIR / "conflicts.jsonl", gold, sealed)
    slice_only = {file for file in conflicts if file not in chosen}  # scored only in the slice
    for file in sorted(slice_only):
        chosen[file], stratum_of[file] = conflicts[file][0].split, "conflict"
    wrong_split = [f for f in chosen if f in gold and gold[f][1].split != chosen[f]]
    if wrong_split:
        raise ValueError(f"gold split differs from the sealed split for {sorted(wrong_split)[:5]}")
    unscaled = sorted(f for f in chosen if f in gold and gold[f][1].strict_v2_problems())
    if unscaled and not args.allow_unscaled:
        first = gold[unscaled[0]][1]
        raise ValueError(
            f"{len(unscaled)} picked gold files lack a scale value or room areas (first: "
            f"{first.file}: {'; '.join(first.strict_v2_problems())}); `validate-extraction "
            "--strict-v2` lists them, --allow-unscaled builds anyway and lists them"
        )
    out: Path = args.out_dir
    picked_rows = [  # a file in v2 only for the conflict slice brings no questions
        (line, question)
        for line, question in rows
        if question.path in chosen and stratum_of[question.path] != "conflict"
    ]
    extras = _merged_extras(
        out / PART2 / EXTRAS,
        args.gold / CONFLICTS_DIR / EXTRAS,
        {path for path, split in chosen.items() if split == "dev"},
        {line for line, _ in picked_rows},
    )
    gold_out = out / PART1 / "gold"
    copies: dict[str, Path] = {}
    for file in sorted(chosen):
        if file in gold:
            target = gold_out / gold[file][0].relative_to(args.gold)
            if target in copies.values():
                raise ValueError(f"two picked files map to {target}")
            copies[file] = target
    for stale in sorted(gold_out.rglob("*.json")) if gold_out.is_dir() else []:
        if stale not in copies.values():
            stale.unlink()  # a copy from an earlier select-plans run
    for file, target in copies.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        if file in conflicts:
            target.write_text(_with_conflicts(gold[file][0], conflicts[file][1]), "utf-8")
        else:
            shutil.copyfile(gold[file][0], target)
    files = [
        PlanFile(
            file=file,
            source=source_of(file),
            split=chosen[file],
            truth=gold[file][1].truth if file in gold else None,
            stratum=stratum_of[file],
            scale_case=cases[file][0] if file in cases and file not in slice_only else None,
        )
        for file in sorted(chosen)
    ]
    write_jsonl(out / PART1 / "files.jsonl", files)
    write_jsonl(out / PART2 / "questions.jsonl", annotate(picked_rows, sealed))
    if extras is not None:
        (out / PART2 / EXTRAS).write_text("".join(f"{text}\n" for text in extras), "utf-8")
    written = sorted(path for path in out.rglob("*") if path.is_file() and path.name != V2_MANIFEST)
    manifest = PlansManifest(
        params=params,
        questions_sha256=split.questions_sha256,
        split_manifest_sha256=_sha256(args.split_dir / SPLIT_MANIFEST),
        by_source={
            source: SourceCount(wanted=params.quotas[source], picked=got, available=available)
            for source, (got, available) in counts.items()
        },
        scale_cases={
            case: SourceCount(wanted=params.scale_quota, picked=got, available=available)
            for case, (got, available) in scale_counts.items()
        },
        missing_gold=missing,
        unscaled=unscaled,
        conflict_files=sorted(conflicts),
        files_sha256={path.relative_to(out).as_posix(): _sha256(path) for path in written},
    )
    (out / V2_MANIFEST).write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"{'source':<16} {'wanted':>9} {'picked':>9} {'available':>11}")
    for source, count in manifest.by_source.items():
        print(
            f"{source:<16} {count.wanted[0]:>4}/{count.wanted[1]:<4} {count.picked[0]:>4}/"
            f"{count.picked[1]:<4} {count.available[0]:>5}/{count.available[1]:<5}"
        )
    print(f"{'scale case':<18} {'wanted':>7} {'picked':>9} {'available':>11}")
    for case, count in manifest.scale_cases.items():
        print(
            f"{case:<18} {count.wanted[0]:>3}/{count.wanted[1]:<3} {count.picked[0]:>4}/"
            f"{count.picked[1]:<4} {count.available[0]:>5}/{count.available[1]:<5}"
        )
    print(
        f"{len(files)} files (plans, the PNG of each swiss plan, {len(extra)} scale cases, "
        f"{len(conflicts)} conflict files, {len(slice_only)} of them only for that slice), "
        f"{len(picked_rows)} questions, "
        f"{len(extras or [])} extras lines"
    )
    for file in unscaled:
        print(f"no scale value or room areas yet: {file}")
    for file in missing:
        print(f"no gold yet: {file}")
    print(f"wrote {out}/{PART1}, {out}/{PART2} and {V2_MANIFEST}")


def _conflict_files(
    path: Path, gold: dict[str, tuple[Path, Extraction]], sealed: set[str]
) -> dict[str, tuple[ConflictFile, list[object]]]:
    """file -> its conflicts.jsonl line, parsed and as written; each file has gold and lies in its
    sealed split."""
    found: dict[str, tuple[ConflictFile, list[object]]] = {}
    texts = path.read_text("utf-8").splitlines() if path.exists() else []
    for lineno, text in enumerate(texts, 1):
        if not text.strip():
            continue
        where = f"{path}:{lineno}"
        try:
            line = ConflictFile.model_validate_json(text)
        except ValidationError as error:
            raise ValueError(f"{where}: {error}") from error
        if line.file in found:
            raise ValueError(f"{where}: {line.file} is listed twice")
        if line.file not in gold:
            raise ValueError(f"{where}: {line.file} has no gold JSON")
        if line.split != ("eval" if group_of(line.file) in sealed else "dev"):
            raise ValueError(f"{where}: {line.file} is not in the {line.split} split")
        found[line.file] = line, json.loads(text)["conflicts"]
    return found


def _with_conflicts(source: Path, conflicts: list[object]) -> str:
    """The gold file's text with `conflicts` (as written) added to its own; checked by the model."""
    data = json.loads(source.read_text("utf-8"))
    data["conflicts"] = [*(data.get("conflicts") or []), *conflicts]
    try:
        Extraction.model_validate(data)
    except ValidationError as error:
        raise ValueError(f"{source} with its conflicts.jsonl entries: {error}") from error
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _merged_extras(
    current: Path, conflict_lines: Path, dev_files: set[str], question_ids: set[int]
) -> list[str] | None:
    """The lines of v2's extras.jsonl, by id: review-7's lines as they are (every line outside
    review-10's id range: those came from an earlier merge) and review-10's conflict lines. None
    when neither file exists. Every line is checked first: its file is a dev file of v2, a
    paraphrase's origin is a v2 question (another kind's origin_id is information only: the
    questions of a file in v2 only for the conflict slice are not in v2)."""
    if not current.exists() and not conflict_lines.exists():
        return None
    kept: dict[int, str] = {}
    for path, own in ((current, False), (conflict_lines, True)):
        if not path.exists():
            continue
        for lineno, text in enumerate(path.read_text("utf-8").splitlines(), 1):
            if not text.strip():
                continue
            where = f"{path}:{lineno}"
            try:
                line = ExtraItem.model_validate_json(text)
            except ValidationError as error:
                raise ValueError(f"{where}: {error}") from error
            if own and line.id not in CONFLICT_EXTRA_IDS:
                raise ValueError(f"{where}: id {line.id} is outside {CONFLICT_EXTRA_IDS}")
            if not own and line.id in CONFLICT_EXTRA_IDS:
                continue  # merged by an earlier run: replaced by the current conflict lines
            if line.id in kept:
                raise ValueError(f"{where}: id {line.id} is used twice")
            if line.path not in dev_files:
                raise ValueError(f"{where}: {line.path} is not a dev file of v2")
            if line.kind == "paraphrase" and line.origin_id not in question_ids:
                raise ValueError(f"{where}: origin_id {line.origin_id} is not a v2 question")
            kept[line.id] = text.strip()
    return [kept[key] for key in sorted(kept)]


def run_score_extraction(args: argparse.Namespace) -> None:
    args.recorded = _recorded(args)
    golden_version: str | None = None
    if args.against == "golden":
        manifest = PlansManifest.model_validate_json((args.golden_dir / V2_MANIFEST).read_text())
        golden_version = manifest.params.version
        gold = _extractions(args.golden_dir / PART1 / "gold")
        for path, _ in gold.values():
            key = path.relative_to(args.golden_dir).as_posix()
            if manifest.files_sha256.get(key) != _sha256(path):
                raise ValueError(f"{path} is not the file select-plans wrote: run it again")
        listed = [row for _, row in read_jsonl(args.golden_dir / PART1 / "files.jsonl", PlanFile)]
        chosen = [gold[row.file] for row in listed if row.file in gold]
        slice_only = {row.file for row in listed if row.stratum == "conflict"}
    else:
        gold = _extractions(args.gold)
        chosen = [entry for entry in gold.values() if entry[1].split == args.against]
        slice_only = set[str]()
    if not chosen:
        raise ValueError("no gold files to score against")
    preds = {file: extraction for file, (_, extraction) in _extractions(args.pred_dir).items()}
    golds = [extraction for _, extraction in chosen]
    result = score_extraction(golds, preds, args.multiplicity, slice_only)
    print(format_extraction_table(result))
    default = args.runs_dir / f"{args.pred_dir.name}.extraction-{args.against}.json"
    out, stem = _detail_path(args, "extraction", default)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    if stem is not None:
        digest = hashlib.sha256()
        for path, extraction in sorted(chosen, key=lambda entry: entry[1].file):
            digest.update(f"{extraction.file}\n{_sha256(path)}\n".encode())
        commit, dirty = _git_commit()
        record = make_extraction_record(
            result,
            against=args.against,
            name=args.name,
            note=args.note,
            milestone=args.milestone,
            golden_version=golden_version,
            gold_sha256=digest.hexdigest(),
            score_sha256=_sha256(out),
            commit=commit,
            dirty=dirty,
            now=datetime.now(HELSINKI),
        )
        _keep(args, stem, record)


def run_history(args: argparse.Namespace) -> None:
    extraction = read_extraction_history(args.results, args.against)
    answering = read_history(args.results, args.against)
    if args.part == "answering":
        extraction = []
    if args.part == "extraction":
        answering = []
    if args.progress:
        print(format_progress(answering, extraction))
    else:
        tables = [
            *([format_extraction_history(extraction)] if args.part != "answering" else []),
            *([format_history(answering)] if args.part != "extraction" else []),
        ]
        print("\n\n".join(tables))
    if args.csv:
        if args.part != "extraction":
            write_history_csv(args.csv / "answering.csv", answering)
            print(f"wrote {args.csv / 'answering.csv'}")
        if args.part != "answering":
            write_extraction_csv(args.csv / "extraction.csv", extraction)
            print(f"wrote {args.csv / 'extraction.csv'}")


def run_baseline_extraction(args: argparse.Namespace) -> None:
    """Part 1 baselines: oracle (the gold itself) and empty (nothing found, no scale)."""
    folder = args.golden_dir / PART1 / "gold"
    gold = _extractions(folder)
    if not gold:
        raise ValueError(f"no gold files in {folder}: run select-plans first")
    out: Path = args.out or RUNS_DIR / f"extraction-{args.name}"
    for path, extraction in gold.values():
        target = out / path.relative_to(folder)
        target.parent.mkdir(parents=True, exist_ok=True)
        made = extraction if args.name == "oracle" else baselines.empty_extraction(extraction)
        target.write_text(made.model_dump_json(by_alias=True, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(gold)} {args.name} extraction files to {out}")


def run_validate_extraction(args: argparse.Namespace) -> None:
    """Check extraction_v1 files (or every *.json under given folders); fail if any is invalid.
    With --strict-v2 a file also needs what golden v2 gold needs: a scale value on every image and
    an area on every room with a polygon (Bogdan, 2026-11-13 23:33)."""
    files = sorted(
        file for path in args.paths for file in ([path] if path.is_file() else path.rglob("*.json"))
    )
    bad = 0
    for file in files:
        try:
            extraction = Extraction.model_validate_json(file.read_text("utf-8"))
        except ValidationError as error:
            bad += 1
            print(f"{file}: {error}")
            continue
        problems = extraction.strict_v2_problems() if args.strict_v2 else []
        if problems:
            bad += 1
            print(f"{file}: not golden v2 gold: {'; '.join(problems)}")
    kind = "golden v2 gold" if args.strict_v2 else "extraction_v1"
    print(f"{len(files) - bad} of {len(files)} files are valid {kind}")
    if bad or not files:
        raise ValueError(f"{bad} invalid file(s)" if files else "no .json files found")


def run_schema(args: argparse.Namespace) -> None:
    for name, text in render_schemas().items():
        path = SCHEMA_DIR / name
        if args.check:
            if not path.exists() or path.read_text("utf-8") != text:
                raise ValueError(f"{path} is stale: run `python -m stoa_eval schema`")
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path}")


def _recording_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("--name", help="the method's name; every recorded run needs one")
    command.add_argument("--note", help="a short note kept with the run")
    command.add_argument(
        "--no-record", action="store_true", help="a scratch check: keep nothing in the history"
    )
    command.add_argument("--milestone", action="store_true", help="needed to score the eval split")
    command.add_argument(
        "--results", type=Path, default=RESULTS, help="history folder, one file per run"
    )
    command.add_argument(
        "--runs-dir", type=Path, default=RUNS_DIR, help="where a recorded run's full score goes"
    )


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

    plans = commands.add_parser("select-plans", help="build golden v2 (both parts) by plan")
    plans.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    plans.add_argument("--split-dir", type=Path, default=SPLIT_DIR)
    plans.add_argument("--gold", type=Path, default=EXTRACTION_GOLD)
    plans.add_argument("--out-dir", type=Path, default=GOLDEN_V2)
    plans.add_argument("--seed", type=int, default=PlansParams().seed)
    plans.add_argument(
        "--allow-missing-gold", action="store_true", help="list picked files without gold JSON"
    )
    plans.add_argument(
        "--allow-unscaled",
        action="store_true",
        help="list picked gold files without a scale value or room areas instead of stopping",
    )
    plans.set_defaults(run=run_select_plans)

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
        "--out", type=Path, help="--no-record only; default <answers>.score[-<against>].json"
    )
    _recording_args(scored)
    scored.add_argument(
        "--reads",
        choices=["gold-extraction", "pipeline-extraction"],
        help="what the answerer read; needed to record a golden v2 (Part 2) run",
    )
    scored.set_defaults(run=run_score)

    part1 = commands.add_parser("score-extraction", help="score extraction_v1 files (Part 1)")
    part1.add_argument("pred_dir", type=Path, help="the pipeline's extraction JSON files")
    part1.add_argument("--against", choices=["golden", "dev", "eval"], default="golden")
    part1.add_argument("--golden-dir", type=Path, default=GOLDEN_V2, help="for --against golden")
    part1.add_argument("--gold", type=Path, default=EXTRACTION_GOLD, help="for dev/eval")
    part1.add_argument("--out", type=Path, help="--no-record only")
    part1.add_argument(
        "--multiplicity", action="store_true", help="counts weigh elements by attrs.multiplicity"
    )
    _recording_args(part1)
    part1.set_defaults(run=run_score_extraction)

    floor = commands.add_parser("baseline-extraction", help="write Part 1 baseline extractions")
    floor.add_argument("name", choices=["oracle", "empty"])
    floor.add_argument("--golden-dir", type=Path, default=GOLDEN_V2)
    floor.add_argument("--out", type=Path, help="default: data/stoa/golden/runs/extraction-<name>/")
    floor.set_defaults(run=run_baseline_extraction)

    history = commands.add_parser("history", help="print the recorded runs, oldest first")
    history.add_argument("--against", choices=["golden", "all", "dev", "eval"])
    history.add_argument("--results", type=Path, default=RESULTS)
    history.add_argument(
        "--csv", type=Path, help="folder: write answering.csv and extraction.csv, for a chart"
    )
    history.add_argument("--part", choices=["answering", "extraction"], help="default: both")
    history.add_argument(
        "--progress", action="store_true", help="per method: first vs latest vs best"
    )
    history.set_defaults(run=run_history)

    check = commands.add_parser("validate-extraction", help="check extraction_v1 JSON files")
    check.add_argument("paths", type=Path, nargs="+", help="files, or folders searched for *.json")
    check.add_argument(
        "--strict-v2",
        action="store_true",
        help="also need a scale value on every image and an area on every room with a polygon",
    )
    check.set_defaults(run=run_validate_extraction)

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
