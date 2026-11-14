"""Command line: `python -m stoa_eval <command>` (from eval/): split, select, select-plans,
baseline, baseline-extraction, score, score-extraction, history, series, validate-extraction,
schema, exp-split, ab, gate, leaderboard, annotated-region."""

import argparse
import fnmatch
import hashlib
import json
import multiprocessing
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence, Set
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Literal, cast, get_args
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import backend, baselines
from .ab import (
    AB_SEED,
    BOOTSTRAP_REPS,
    REFERENCE_ARMS,
    AbResult,
    ArmResult,
    Rate,
    arm_result,
    compare,
    count_errors,
    count_keys,
    count_stats,
    format_ab,
    hits_of,
    orientation_label,
    paired,
)
from .coverage import format_coverage_table, load_answers, score_all
from .exp_split import (
    DEFAULT_EXP_SEED,
    DEFAULT_SHARES,
    EXP_PARTS,
    EXP_SOURCE,
    ExpPart,
    ExpPartImages,
    ExpSplit,
    assign_parts,
    check_dev_only,
    totals,
)
from .extraction import Extraction
from .extraction_scoring import format_extraction_table, score_extraction
from .extras_scoring import format_slices, score_golden
from .families import group_of, source_of
from .gate import (
    DELTA,
    G1MAIN,
    GATE_SEED,
    ON_VAL,
    SIGNALS,
    TARGET,
    GateResult,
    SignalFile,
    SignalReport,
    UnionStep,
    Unit,
    apply_gate,
    apply_group,
    calibrate,
    certificate,
    compare_signals,
    family_gates,
    family_keys,
    family_result,
    format_gate,
    g1main_signal,
    gate_policy,
    group_result,
    halves,
    load_signal_file,
    nothing_found_rates,
    pooled_gates,
    signals_of,
)
from .history import (
    Provenance,
    format_extraction_history,
    format_history,
    format_progress,
    format_series_markdown,
    make_extraction_record,
    make_record,
    read_extraction_history,
    read_history,
    series,
    write_extraction_csv,
    write_history_csv,
)
from .jsonl import iter_jsonl, read_jsonl, write_jsonl
from .leaderboard import (
    GROUPS,
    ArmRun,
    Invalid,
    arm_digest,
    best_per_group,
    combo_hits,
    combo_string,
    digest_files,
    eligible,
    failure_images,
    family_policies,
    find_arms,
    format_leaderboard,
    kept_block,
    load_oracles,
    oracle_reason,
    policy_runs,
)
from .models import (
    SCHEMA_DIR,
    SETTING_NAME,
    SETTING_VALUE,
    Answer,
    ExtraItem,
    GoldenItem,
    NumberedQuestion,
    Question,
    TextClaims,
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
    count_scale_cases,
    keep,
    pick,
    pick_scale_cases,
    strata,
)
from .region import REGION_PARTS, AnnotatedRegions, ImageRegion, annotate_file, style_counts
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
TEXT_CLAIMS = "text_claims.jsonl"  # part2_answering/text_claims.jsonl: curated (review-8)
CONFLICTS_DIR = "_conflicts"  # under the extraction gold: conflicts.jsonl and extras.jsonl
DEFAULT_GOLDEN = GOLDEN_V2 / PART2 / "questions.jsonl"
EXTRACTION_GOLD = REPO / "data/stoa/extraction_gold"
RUNS_DIR = GOLDEN_DIR / "runs"
SPLIT_MANIFEST = "manifest.json"
EVAL_WARNING = "warning: sealed split: score at milestones only"
NOT_WRITTEN = "score not written (--no-record; --out <file> keeps it)"
RESULTS = Path(__file__).resolve().parents[1] / "results/runs"  # tracked: one file per run
HELSINKI = ZoneInfo("Europe/Helsinki")
EXP_DIR = REPO / "data/stoa/exp"  # gitignored: the experiment split, A/B results, arms
EXP_PRIOR = REPO / "data/stoa/priors/exp-train.json"  # the prior fit on the train part only
LEADERBOARD = REPO / ".agents/exp/leaderboard.md"  # local: arm names and val numbers only
ORACLES = "oracles.json"  # under the exp dir: globs of arms that read gold at answer time
DATASET = REPO / "data/stoa/full/junction-dataset"  # the drawings, at the paths questions use
REGIONS = EXP_DIR / "labels/annotated_region.json"


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


def _claims_for(golden: Path) -> tuple[list[TextClaims], str | None]:
    """part2_answering/text_claims.jsonl next to a v2 questions file and its sha256, when it
    exists."""
    path = golden.with_name(TEXT_CLAIMS)
    if golden.parent.name != PART2 or not path.exists():
        return [], None
    return [line for _, line in read_jsonl(path, TextClaims)], _sha256(path)


def _v2_gold(golden_dir: Path) -> dict[str, tuple[Path, Extraction]]:
    """Golden v2's Part 1 gold, after checking each file is the one select-plans wrote."""
    manifest = PlansManifest.model_validate_json((golden_dir / V2_MANIFEST).read_text("utf-8"))
    gold = _extractions(golden_dir / PART1 / "gold")
    for path, _ in gold.values():
        key = path.relative_to(golden_dir).as_posix()
        if manifest.files_sha256.get(key) != _sha256(path):
            raise ValueError(f"{path} is not the file select-plans wrote: run it again")
    return gold


def _part1_gold_for(golden: Path) -> dict[str, Extraction] | None:
    """file -> extraction gold of the v2 that a part2 questions file belongs to; None for v1."""
    if golden.parent.name != PART2:
        return None
    return {file: extraction for file, (_, extraction) in _v2_gold(golden.parent.parent).items()}


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


def _git(*args: str) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"can't read the git commit to record the run: {error}") from error
    return done.stdout.strip()


def _git_commit() -> tuple[str, bool]:
    """Short sha of HEAD, and whether tracked files have uncommitted changes."""
    return _git("rev-parse", "--short", "HEAD"), bool(_git("status", "--porcelain", "-uno"))


def _committed_at(commit: str) -> datetime:
    return datetime.fromisoformat(_git("show", "-s", "--format=%cI", commit)).astimezone(HELSINKI)


def _settings(pairs: Sequence[str] | None) -> dict[str, str] | None:
    """`--setting NAME=VALUE` pairs as the record keeps them: names lowercased, plain values."""
    if not pairs:
        return None
    settings: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        name = name.strip().lower()
        if (
            not sep
            or not re.fullmatch(SETTING_NAME, name)
            or not re.fullmatch(SETTING_VALUE, value)
        ):
            raise ValueError(
                f"--setting {pair!r}: give NAME=VALUE with a plain name and value (letters, "
                "digits, _ . : + -; no paths, the record is public)"
            )
        if name in settings:
            raise ValueError(f"--setting {name} is given twice")
        settings[name] = value
    return settings


def _provenance(args: argparse.Namespace) -> Provenance:
    """The code that made the predictions: HEAD of this tree, or with --commit a clean export of
    that commit (dirty false), scored by this tree's HEAD (eval_commit)."""
    head, head_dirty = _git_commit()
    settings = _settings(args.setting)
    if args.commit is None:
        return Provenance(head, head_dirty, _committed_at(head), settings=settings)
    try:
        commit = _git("rev-parse", "--verify", "--short", f"{args.commit}^{{commit}}")
    except ValueError as error:
        raise ValueError(f"--commit {args.commit}: not a commit of this repo") from error
    return Provenance(commit, False, _committed_at(commit), head, head_dirty, settings)


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


def run_exp_split(args: argparse.Namespace) -> None:
    sealed = set(_split_manifest(args.split_dir).eval_groups)
    golden_manifest = args.golden_dir / V2_MANIFEST
    golden_files = {
        row.file for _, row in read_jsonl(args.golden_dir / PART1 / "files.jsonl", PlanFile)
    }
    golden_groups = {group_of(file) for file in golden_files}
    asked: dict[str, list[NumberedQuestion]] = {}
    for _, row in iter_jsonl(args.split_dir / "dev.jsonl", NumberedQuestion):
        if source_of(row.path) == EXP_SOURCE:
            asked.setdefault(row.path, []).append(row)
    excluded = sorted(file for file in asked if group_of(file) in golden_groups)
    files = sorted(set(asked) - set(excluded))
    gold = {
        file: extraction
        for file, (_, extraction) in _extractions(args.gold / EXP_SOURCE).items()
        if file in asked
    }
    check_dev_only(files, sealed, golden_files, {file: gold[file].split for file in gold})
    group_part = assign_parts((group_of(file) for file in files), args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    parts: dict[ExpPart, ExpPartImages] = {}
    for part in EXP_PARTS:
        mine = [file for file in files if group_part[group_of(file)] == part]
        questions = args.out_dir / f"{part}_questions.jsonl"
        rows = sorted((row for file in mine for row in asked[file]), key=lambda row: row.id)
        write_jsonl(questions, rows)
        elements, rooms, plans, per_image = totals(gold[file] for file in mine)
        parts[part] = ExpPartImages(
            files=mine,
            images=len(mine),
            groups=len({group_of(file) for file in mine}),
            questions=sum(len(asked[file]) for file in mine),
            questions_sha256=_sha256(questions),
            elements=dict(sorted(elements.items())),
            rooms=dict(sorted(rooms.items())),
            plans=plans,
            plans_per_image=dict(sorted(per_image.items(), key=lambda item: int(item[0]))),
        )
    split = ExpSplit(
        seed=args.seed,
        shares=DEFAULT_SHARES,
        split_manifest_sha256=_sha256(args.split_dir / SPLIT_MANIFEST),
        golden_manifest_sha256=_sha256(golden_manifest),
        excluded_golden=excluded,
        parts=parts,
    )
    out = args.out_dir / "split.json"
    out.write_text(split.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"{'part':<6} {'images':>6} {'questions':>9} {'plans':>6}  elements / rooms")
    for name, part in split.parts.items():
        print(
            f"{name:<6} {part.images:>6} {part.questions:>9} {part.plans:>6}  "
            f"{part.elements} / {part.rooms}"
        )
    print(f"left out {len(excluded)} golden v2 images; wrote {out} and <part>_questions.jsonl")


CERTIFIED = "test-certified.json"  # under the exp dir: every test run, so test is used once


class CertifiedRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal["ab", "gate"]
    arm: str
    time: str
    result: str = Field(description="the verdict or the certificate sentence")
    result_file: str
    result_sha256: str
    reason: str | None = Field(default=None, description="why a certified arm was run again")


class CertifiedRuns(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[CertifiedRun] = Field(default_factory=list[CertifiedRun])


def _certified(exp_dir: Path) -> CertifiedRuns:
    path = exp_dir / CERTIFIED
    if not path.is_file():
        return CertifiedRuns()
    return CertifiedRuns.model_validate_json(path.read_text("utf-8"))


def _certify_check(args: argparse.Namespace, command: str, arms: Sequence[str]) -> None:
    """Test needs --certify, and an arm already run on test by this command needs a reason."""
    if args.part != "test":
        return
    if not args.certify:
        raise ValueError(
            "test is used once, for the arm we ship: ask the orchestrator, then add --certify"
        )
    done = {
        run.arm: run
        for run in _certified(args.exp_dir).runs
        if run.command == command and run.arm in arms
    }
    if done and not args.recertify_reason:
        run = next(iter(done.values()))
        raise ValueError(
            f"{run.arm} was already run on test with {command} at {run.time}: test is used once; "
            "give --recertify-reason to run it again"
        )


def _certify_record(
    args: argparse.Namespace, command: Literal["ab", "gate"], arms: Sequence[str], result: str,
    out: Path,
) -> None:  # fmt: skip
    if args.part != "test":
        return
    record = _certified(args.exp_dir)
    now = datetime.now(HELSINKI).isoformat(timespec="seconds")
    for arm in arms:
        record.runs.append(
            CertifiedRun(
                command=command,
                arm=arm,
                time=now,
                result=result,
                result_file=str(out),
                result_sha256=_sha256(out),
                reason=args.recertify_reason,
            )
        )
    path = args.exp_dir / CERTIFIED
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"recorded the test run in {path}")


def _exp_part(exp_dir: Path, part: ExpPart) -> tuple[ExpSplit, Path, list[NumberedQuestion]]:
    """The split, the part's questions file and its rows, after checking the file is the one
    exp-split wrote."""
    split_path = exp_dir / "split.json"
    if not split_path.is_file():
        raise ValueError(f"{split_path} is missing: run `python -m stoa_eval exp-split` first")
    split = ExpSplit.model_validate_json(split_path.read_text("utf-8"))
    path = exp_dir / f"{part}_questions.jsonl"
    if _sha256(path) != split.parts[part].questions_sha256:
        raise ValueError(f"{path} is not the file exp-split wrote: run exp-split again")
    return split, path, [row for _, row in read_jsonl(path, NumberedQuestion)]


def _arm_name(arm: str, exp_dir: Path) -> str:
    """A reference arm's name, or the folder under data/stoa/exp joined with "-" (core/yolo ->
    core-yolo), or else the folder's own name."""
    if arm in REFERENCE_ARMS:
        return arm
    folder = Path(arm).resolve()
    if folder.is_relative_to(exp_dir.resolve()):
        return "-".join(folder.relative_to(exp_dir.resolve()).parts)
    return folder.name


def _exp_prior(exp_dir: Path, out: Path) -> Path:
    """Fits the answer prior on the train part's questions only (answer's builder)."""
    backend.run("prior", "--train", str(exp_dir / "train_questions.jsonl"), "--out", str(out))
    return out


def _answer_arm(
    arm: str,
    questions: Path,
    golds: dict[str, Extraction],
    gold_dir: Path,
    prior: Path | None,
    work: Path,
) -> tuple[str, dict[int, Answer], dict[str, Extraction] | None]:
    """(what the arm is, its answers by question id, its extractions of the part's images; None
    for the prior). `work` is a fresh folder for this arm."""
    work.mkdir(parents=True)
    drawings, use_prior, preds = work / "drawings", None, None
    if arm == "gold":
        drawings, preds, what = gold_dir, dict(golds), f"dev gold extraction ({gold_dir})"
    elif arm == "prior":
        if prior is None:
            raise ValueError("the prior arm needs the train prior")
        drawings.mkdir()
        use_prior, preds, what = prior, None, f"train prior ({prior}), no extraction"
    elif arm == "none":
        drawings.mkdir()
        preds = {file: baselines.empty_extraction(gold) for file, gold in golds.items()}
        for n, extraction in enumerate(preds.values()):
            body = extraction.model_dump_json(by_alias=True, exclude_none=True)
            (drawings / f"{n}.json").write_text(body, "utf-8")
        what = "empty extraction: every image read, nothing found"
    else:
        drawings = Path(arm)
        if not drawings.is_dir():
            raise ValueError(f"{arm} is neither a folder nor one of {', '.join(REFERENCE_ARMS)}")
        found = _extractions(drawings)
        preds = {file: found[file][1] for file in golds if file in found}
        what = str(drawings)
    out = work / "answers.jsonl"
    extra = ["--prior", str(use_prior)] if use_prior is not None else []
    backend.run(
        "answer", "--questions", str(questions), "--drawings", str(drawings), "--out", str(out),
        *extra,
    )  # fmt: skip
    answers = {answer.id: answer for _, answer in read_jsonl(out, Answer)}
    return what, answers, preds


ORIENTATION = "orientation.json"  # under the exp dir, written by answer: file -> turn, mirrored


def _orientation(path: Path) -> tuple[dict[str, str] | None, str]:
    """file -> orientation label, and where it came from (None when there is no file)."""
    if not path.is_file():
        return None, f"no {path}: the gold has no orientation, so upright/rotated is not split"
    raw = json.loads(path.read_text("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected an object of file -> orientation")
    entries = cast(dict[str, object], raw)
    return {file: orientation_label(value) for file, value in entries.items()}, f"from {path}"


def _part_golds(
    exp_dir: Path, gold: Path, part: ExpPart
) -> tuple[Path, list[NumberedQuestion], list[str], dict[str, Extraction]]:
    """The part's questions file, its questions, its files and their dev gold."""
    split, questions_path, questions = _exp_part(exp_dir, part)
    files = split.parts[part].files
    wanted = set(files)
    golds = {
        file: extraction
        for file, (_, extraction) in _extractions(gold / EXP_SOURCE).items()
        if file in wanted
    }
    if set(golds) != wanted:
        raise ValueError(f"{len(wanted - set(golds))} images of {part} have no dev gold")
    return questions_path, questions, files, golds


def _families(questions_path: Path, work: Path) -> dict[int, str]:
    """question id -> the backend parser's family."""
    out = work / "families.json"
    backend.run("families", "--questions", str(questions_path), "--out", str(out))
    return {int(k): v for k, v in json.loads(out.read_text("utf-8")).items()}


def _score_arm(
    arm: str,
    name: str,
    part: tuple[Path, list[NumberedQuestion], list[str], dict[str, Extraction]],
    gold_dir: Path,
    families: Mapping[int, str],
    prior: Path | None,
    orientation: Mapping[str, str] | None,
    work: Path,
) -> tuple[ArmResult, dict[int, bool], list[int]]:
    """One arm on a part: its result, its hits by question id and the ids it refused."""
    questions_path, questions, files, golds = part
    what, answers, preds = _answer_arm(arm, questions_path, golds, gold_dir, prior, work)
    hits = hits_of(questions, answers)
    refused = sorted(q.id for q in questions if q.id not in answers or answers[q.id].answer is None)
    keys = count_keys(golds.values())
    counts = None if preds is None else count_stats(golds, preds, keys)
    errors = None if preds is None else count_errors(golds, preds, keys)
    present = files if preds is None else list(preds)
    result = arm_result(
        name, what, questions, hits, families, files, present, counts, orientation, errors
    )
    return result, hits, refused


def run_ab(args: argparse.Namespace) -> None:
    names = [_arm_name(arm, args.exp_dir) for arm in (args.a, args.b)]
    if names[0] == names[1]:
        raise ValueError(f"both arms are named {names[0]}")
    certified = [name for name in names if name not in REFERENCE_ARMS]
    _certify_check(args, "ab", certified)
    part = _part_golds(args.exp_dir, args.gold, args.part)
    questions = part[1]
    orientation, note = _orientation(args.orientation or args.exp_dir / ORIENTATION)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        prior = _exp_prior(args.exp_dir, args.prior) if "prior" in (args.a, args.b) else None
        families = _families(part[0], work)
        arms: list[tuple[ArmResult, dict[int, bool]]] = []
        for label, arm, name in zip(("a", "b"), (args.a, args.b), names, strict=True):
            result, hits, _ = _score_arm(
                arm, name, part, args.gold / EXP_SOURCE, families, prior, orientation, work / label
            )
            arms.append((result, hits))
    overall, by_family, per_image = compare(
        questions, arms[0], arms[1], families, args.seed, args.reps
    )
    result = AbResult(
        part=args.part,
        split_sha256=_sha256(args.exp_dir / "split.json"),
        prior_sha256=_sha256(prior) if prior is not None else None,
        seed=args.seed,
        bootstrap_reps=args.reps,
        orientation=note,
        a=arms[0][0],
        b=arms[1][0],
        paired=overall,
        paired_by_family=by_family,
        per_image=per_image,
    )
    print(format_ab(result))
    out = args.exp_dir / "ab" / f"{names[0]}-vs-{names[1]}-{args.part}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    verdict = f"{overall.verdict}: B - A {overall.diff} [{overall.ci_low}, {overall.ci_high}]"
    _certify_record(args, "ab", certified, verdict, out)


def _units(
    questions: Sequence[NumberedQuestion],
    families: Mapping[int, str],
    answers: Mapping[int, Answer],
    second: Mapping[int, Answer] | None,
    preds: Mapping[str, Extraction],
    steps: Mapping[str, list[tuple[float, float]]],
    extra: Sequence[SignalFile] = (),
    empty: Mapping[str, float] | None = None,
    own: Set[str] = frozenset(),
) -> list[Unit]:
    """One unit per (image, family) the questions ask; unsupported questions are left out.
    `extra`: signal files, each adding its value per answer under its name. `own`: the families
    another arm answers (--family-arm): the built-in signals read the arm's own extraction, so
    they have no value there."""
    looked_up = [(made.name, made.by_answer()) for made in extra]
    hits = hits_of(questions, answers)
    grouped: dict[tuple[str, str], list[NumberedQuestion]] = {}
    for q in questions:
        if families.get(q.id, "unsupported") != "unsupported":
            grouped.setdefault((q.path, families[q.id]), []).append(q)

    def said(replies: Mapping[int, Answer], rows: list[NumberedQuestion]) -> list[object]:
        return [replies[q.id].answer if q.id in replies else None for q in rows]

    units: list[Unit] = []
    for (file, family), rows in sorted(grouped.items()):
        agree = None if second is None else said(answers, rows) == said(second, rows)
        signals = signals_of(preds.get(file), family, steps, agree, empty)
        if family in own:
            signals = dict.fromkeys(signals)
        signals.update((name, values.get((file, family))) for name, values in looked_up)
        if None in said(answers, rows):  # a refused answer is never marked sure
            signals = dict.fromkeys(signals)
        exact = all(hits[q.id] for q in rows)
        units.append(Unit(file=file, family=family, exact=exact, signals=signals))
    return units


def _best_signal(compared: Mapping[str, SignalReport], name: str) -> str:
    """Of the signals with a value, the highest failure AUROC (none when val has only right or
    only wrong answers: the earlier one, built-ins first, then the signal files in order)."""
    order = list(compared)
    usable = [s for s in order if compared[s].scored]
    if not usable:
        raise ValueError(
            f"{name}: no signal has a value (attrs.score, a --second arm or a --signal-file)"
        )
    auroc = {s: -1.0 if compared[s].auroc is None else compared[s].auroc for s in usable}
    return max(usable, key=lambda s: (auroc[s], -order.index(s)))


def _arm_folder(arm: str, exp_dir: Path) -> str:
    """An arm as a signal file names it: its folder under exp_dir (detector/C-yolo26s-v8), else
    its path as given (or the reference arm's name)."""
    if arm in REFERENCE_ARMS:
        return arm
    folder = Path(arm).resolve()
    if folder.is_relative_to(exp_dir.resolve()):
        return folder.relative_to(exp_dir.resolve()).as_posix()
    return arm


def _family_arm_specs(specs: Sequence[str]) -> list[tuple[str, str]]:
    """--family-arm FAMILY=FOLDER (FAMILY may be a pattern: room:*) as (pattern, folder)."""
    parsed: list[tuple[str, str]] = []
    for spec in specs:
        pattern, sep, folder = spec.partition("=")
        if not sep or not pattern or not folder:
            raise ValueError(f"--family-arm {spec!r}: FAMILY=FOLDER, e.g. 'room:*=ocr/G4'")
        parsed.append((pattern, folder))
    return parsed


def _routed(specs: Sequence[tuple[str, str]], asked: Set[str]) -> dict[str, str]:
    """Family -> the folder answering it instead of --arm; each pattern must match a family the
    part asks, and no family may be routed twice."""
    routed: dict[str, str] = {}
    for pattern, folder in specs:
        matched = fnmatch.filter(sorted(asked), pattern)
        if not matched:
            raise ValueError(f"--family-arm {pattern}: no such family asked; {sorted(asked)}")
        for family in matched:
            if family in routed:
                raise ValueError(f"--family-arm: {family} is routed twice")
            routed[family] = folder
    return routed


def _said(
    questions: Sequence[NumberedQuestion],
    families: Mapping[int, str],
    answers: Mapping[int, Answer],
) -> dict[tuple[str, str], list[object]]:
    """(file, family) -> the answers to its questions, None for a refusal."""
    said: dict[tuple[str, str], list[object]] = {}
    for q in questions:
        family = families.get(q.id, "unsupported")
        if family != "unsupported":
            reply = answers.get(q.id)
            said.setdefault((q.path, family), []).append(None if reply is None else reply.answer)
    return said


def _g1main_dists(path: Path) -> dict[str, dict[str, dict[int, float]]]:
    raw = cast(dict[str, dict[str, dict[str, float]]], json.loads(path.read_text("utf-8")))
    return {
        file: {family: {int(k): v for k, v in dist.items()} for family, dist in by.items()}
        for file, by in raw.items()
    }


def _signal_files(
    paths: Sequence[Path], arm: str, families: set[str], exp_dir: Path
) -> list[SignalFile]:
    """The --signal-file files, checked: about this arm (or any arm), known family names,
    distinct names."""
    made = [load_signal_file(path) for path in paths]
    mine = _arm_folder(arm, exp_dir)
    for path, signal in zip(paths, made, strict=True):
        if signal.arm is not None and signal.arm != mine:
            raise ValueError(f"{path}: judges {signal.arm}'s answers, not {mine}'s")
        unknown = sorted({v.family for v in signal.values} - families)
        if unknown:
            raise ValueError(f"{path}: unknown families {unknown}; known: {sorted(families)}")
    names = [signal.name for signal in made]
    if len(set(names)) != len(names):
        raise ValueError(f"two signal files share a name: {names}")
    return made


def run_gate(args: argparse.Namespace) -> None:
    if args.pool and args.part == "test":
        raise ValueError("--pool: val only; test reuses the val gate's groups")
    specs = _family_arm_specs(args.family_arm)
    name = "+".join(
        [
            _arm_name(args.arm, args.exp_dir),
            *sorted({_arm_name(folder, args.exp_dir) for _, folder in specs}),
        ]
    )
    _certify_check(args, "gate", [name])
    split, questions_path, questions = _exp_part(args.exp_dir, args.part)
    files = split.parts[args.part].files
    wanted = set(files)
    golds = {
        file: extraction
        for file, (_, extraction) in _extractions(args.gold / EXP_SOURCE).items()
        if file in wanted
    }
    second_name = None if args.second is None else _arm_name(args.second, args.exp_dir)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        backend.run("families", "--questions", str(questions_path), "--out", str(work / "f.json"))
        families = {int(k): v for k, v in json.loads((work / "f.json").read_text()).items()}
        asked = {families.get(q.id, "unsupported") for q in questions} - {"unsupported"}
        routed = _routed(specs, asked)
        gold_dir = args.gold / EXP_SOURCE
        _, answers, preds = _answer_arm(args.arm, questions_path, golds, gold_dir, None, work / "a")
        for n, folder in enumerate(sorted(set(routed.values()))):
            out = work / f"f{n}"
            _, theirs, _ = _answer_arm(folder, questions_path, golds, gold_dir, None, out)
            for q in questions:
                if routed.get(families.get(q.id, "unsupported")) == folder:
                    answers.pop(q.id, None)
                    if q.id in theirs:
                        answers[q.id] = theirs[q.id]
        second = None
        if args.second is not None:
            _, second, _ = _answer_arm(
                args.second, questions_path, golds, gold_dir, None, work / "b"
            )
        dists = None
        if args.g1main is not None:
            backend.run("g1main", "--replies", str(args.g1main), "--out", str(work / "g1.json"))
            dists = _g1main_dists(work / "g1.json")
    preds = preds or {}
    family_arms = {family: _arm_folder(folder, args.exp_dir) for family, folder in routed.items()}
    extra = _signal_files(args.signal_file, args.arm, asked, args.exp_dir)
    if routed and any(signal.arm is not None for signal in extra):
        raise ValueError(
            "--family-arm: a signal file that judges one arm's answers can't judge a combination; "
            "use --g1main or a file with arm null"
        )
    read_from = {made.name: str(path) for made, path in zip(extra, args.signal_file, strict=True)}
    if dists is not None:
        if G1MAIN in read_from:
            raise ValueError(f"--g1main and a signal file both named {G1MAIN}")
        extra.append(g1main_signal(_said(questions, families, answers), dists))
        read_from[G1MAIN] = str(args.g1main)
    names = [*SIGNALS, *(signal.name for signal in extra)]
    if args.signal is not None and args.signal not in names:
        raise ValueError(f"--signal {args.signal}: not one of {names}")
    if args.part == "val":
        calibration_files, selection_files = halves(files, args.seed)
        keys = {key for family in asked for key in family_keys(family)}
        steps = calibrate(
            {f: golds[f] for f in calibration_files},
            {f: preds[f] for f in calibration_files if f in preds},
            sorted(keys),
        )
        calibration_set = set(calibration_files)
        empty = nothing_found_rates(
            (
                u
                for u in _units(questions, families, answers, second, preds, steps, own=set(routed))
                if u.file in calibration_set
            ),
            preds,
        )
        chosen = set(selection_files)
        thresholds_in: dict[str, float | None] | None = None
        groups_in: dict[str, tuple[list[str], float | None]] = {}
        signal: str | None = args.signal
    else:
        tuned_path = args.thresholds or args.exp_dir / "ab" / f"gate-{name}-val.json"
        tuned = GateResult.model_validate_json(tuned_path.read_text("utf-8"))
        if tuned.part != "val" or tuned.arm != name or tuned.second != second_name:
            raise ValueError(f"{tuned_path} is not the val gate of {name} / {second_name}")
        if tuned.family_arms != family_arms:
            raise ValueError(f"{tuned_path} routed {tuned.family_arms}, not {family_arms}")
        steps, empty, chosen = tuned.calibration, tuned.empty_rates, wanted
        thresholds_in = {family: gate.threshold for family, gate in tuned.families.items()}
        groups_in = {group: (g.families, g.threshold) for group, g in tuned.groups.items()}
        signal = tuned.signal
        if signal not in names:
            raise ValueError(f"the val gate used the signal {signal!r}: give its --signal-file")
    units = [
        u
        for u in _units(
            questions, families, answers, second, preds, steps, extra, empty, set(routed)
        )
        if u.file in chosen
    ]
    compared = compare_signals(units, names)
    if signal is None:
        signal = _best_signal(compared, name)
    label = "test" if args.part == "test" else f"val selection half, {ON_VAL}"
    by_family: dict[str, list[Unit]] = {}
    for u in units:
        by_family.setdefault(u.family, []).append(u)
    union_steps: list[UnionStep] = []
    grouped = {
        group: apply_group([u for f in of for u in by_family.get(f, [])], signal, of, threshold)
        for group, (of, threshold) in groups_in.items()
    }
    if thresholds_in is None and args.pool:
        grouped, picked, union_steps = pooled_gates(
            by_family, GROUPS, signal, args.target, args.delta
        )
    elif thresholds_in is None:
        picked = family_gates(by_family, signal, args.target, args.delta)
    else:
        picked = {f: apply_gate(by_family[f], signal, thresholds_in.get(f)) for f in by_family}
    gates = {family: family_result(picked[family], family, label) for family in sorted(picked)}
    thresholds = {family: gate.threshold for family, gate in gates.items()}
    result = GateResult(
        arm=name,
        second=second_name,
        family_arms=family_arms,
        part=args.part,
        images=len({u.file for u in units}),
        seed=args.seed,
        split_sha256=_sha256(args.exp_dir / "split.json"),
        target=args.target,
        delta=args.delta,
        family_delta=None if grouped else args.delta / max(1, len(by_family)),
        signal=signal,
        signal_files=read_from,
        compared=compared,
        calibration={key: list(value) for key, value in steps.items()},
        empty_rates=empty,
        families=gates,
        groups={group: group_result(gate, group, label) for group, gate in grouped.items()},
        union_steps=union_steps,
        certificate=certificate(units, signal, thresholds, label),
    )
    print(format_gate(result))
    out = args.exp_dir / "ab" / f"gate-{name}-{args.part}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    _certify_record(args, "gate", [name], result.certificate.sentence, out)


def run_gate_policy(args: argparse.Namespace) -> None:
    result = GateResult.model_validate_json(args.gate.read_text("utf-8"))
    generated = datetime.now(HELSINKI).isoformat(timespec="seconds")
    made = gate_policy(result, _repo_path(args.gate), generated)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(made.model_dump_json(by_alias=True, indent=2) + "\n", "utf-8")
    print(f"wrote {args.out}: {len(made.families)} families ({', '.join(made.families) or 'none'})")


def _code_digest() -> str:
    """The code that answers and scores an arm: backend/app, ab_backend.py and stoa_eval."""
    eval_dir = Path(__file__).resolve().parents[1]
    paths = [
        *(REPO / "backend/app").rglob("*.py"),
        eval_dir / "ab_backend.py",
        *(eval_dir / "stoa_eval").glob("*.py"),
    ]
    return digest_files(paths, REPO)


def _modified(folder: Path) -> str:
    times = [path.stat().st_mtime for path in folder.rglob("*.json")]
    when = datetime.fromtimestamp(max(times), HELSINKI) if times else None
    return when.strftime("%Y-%m-%d %H:%M") if when else "-"


def _repo_path(path: Path) -> str:
    """Repo-relative when the path is inside the repo, else absolute."""
    resolved = path.resolve()
    return (resolved.relative_to(REPO) if resolved.is_relative_to(REPO) else resolved).as_posix()


def _first_line(error: Exception) -> str:
    lines = [line.strip() for line in str(error).splitlines() if line.strip()]
    return " / ".join(lines[:3])[:300]


def _golden_folders(exp_dir: Path, names: Sequence[str]) -> dict[str, str]:
    """Arm -> its golden v2 output, the sibling folder `<arm>-golden` with JSON files in it."""
    folders = {name: exp_dir / f"{name}-golden" for name in names}
    return {
        name: _repo_path(folder)
        for name, folder in folders.items()
        if folder.is_dir() and any(folder.rglob("*.json"))
    }


def run_leaderboard(args: argparse.Namespace) -> None:
    part = _part_golds(args.exp_dir, args.gold, "val")
    questions_path, questions, files, _ = part
    gold_dir = args.gold / EXP_SOURCE
    orientation, _ = _orientation(args.exp_dir / ORIENTATION)
    gold_paths = [path for path, _ in _extractions(gold_dir).values()]
    base = hashlib.sha256()
    for piece in (
        _sha256(args.exp_dir / "split.json"),
        digest_files([p for p in gold_paths if p.is_file()], gold_dir),
        _code_digest(),
        _sha256(args.exp_dir / "train_questions.jsonl"),
        json.dumps(orientation, sort_keys=True),
        f"{args.seed}:{args.reps}",
    ):
        base.update(piece.encode())
    deny = load_oracles(args.exp_dir / ORACLES)
    cache = args.exp_dir / "ab" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        families = _families(questions_path, work)
        prior_path = _exp_prior(args.exp_dir, args.prior)

        def scored(arm: str, name: str, digest: str, modified: str) -> ArmRun:
            key = hashlib.sha256(f"{base.hexdigest()}:{name}:{digest}".encode()).hexdigest()
            path = cache / f"{key[:32]}.json"
            if path.is_file():
                run = ArmRun.model_validate_json(path.read_text("utf-8"))
                if run.key == key:
                    return run
            result, hits, refused = _score_arm(
                arm, name, part, gold_dir, families, prior_path, orientation, work / key[:12]
            )
            run = ArmRun(
                key=key, name=name, result=result, hits=hits, refused=refused, modified=modified
            )
            if name != "prior":
                run.against_prior = paired(questions, prior.hits, hits, args.seed, args.reps)
            path.write_text(run.model_dump_json() + "\n", encoding="utf-8")
            return run

        prior = scored("prior", "prior", _sha256(prior_path), "-")
        references = {"prior": prior, "gold": scored("gold", "gold", "", "-")}
        runs: list[ArmRun] = []
        invalid: list[Invalid] = []
        for folder in find_arms(args.exp_dir):
            name = folder.relative_to(args.exp_dir).as_posix()
            try:
                found = _extractions(folder)
            except ValueError as error:
                invalid.append(
                    Invalid(name=name, reason=f"not valid extraction_v1: {_first_line(error)}")
                )
                continue
            covered = sum(file in found for file in files)
            if not covered:
                example = next(iter(found), "nothing")
                invalid.append(
                    Invalid(name=name, reason=f"no val image ({len(found)} files, e.g. {example})")
                )
                continue
            run = scored(str(folder), name, arm_digest(folder), _modified(folder))
            why = oracle_reason(name, folder, args.exp_dir, deny)
            runs.append(run.model_copy(update={"oracle": why}))
    chosen = best_per_group(questions, families, runs, prior)
    combo = combo_hits(questions, families, chosen, prior)
    hits = sum(combo.values())
    folders = {run.name: _repo_path(args.exp_dir / run.name) for run in runs}
    golden = _golden_folders(args.exp_dir, [run.name for run in runs])
    ready, policy = family_policies(
        questions, families, runs, prior, folders, args.seed, args.reps, golden
    )
    per_family = policy_runs(policy, runs)
    family_combo = combo_hits(questions, families, per_family, prior)
    family_hits = sum(family_combo.values())
    family_string = ",".join(f"{family}={run.name}" for family, run in per_family.items())
    ready_combo = combo_hits(questions, families, policy_runs(ready, runs), prior)
    ready_hits = sum(ready_combo.values())
    ready_string = ",".join(
        f"{family}={entry.arm}" for family, entry in ready.items() if entry.arm is not None
    )
    out = args.out
    existing = out.read_text("utf-8") if out.is_file() else ""
    text = format_leaderboard(
        generated=datetime.now(HELSINKI).strftime("%Y-%m-%d %H:%M"),
        questions=questions,
        families=families,
        runs=runs,
        references=references,
        invalid=invalid,
        combo=combo_string(chosen),
        combo_pair=paired(questions, prior.hits, combo, args.seed, args.reps),
        combo_rate=Rate(hits=hits, n=len(combo), rate=hits / len(combo) if combo else None),
        family_combo=f"{family_string or 'prior'} (others: prior)",
        family_pair=paired(questions, prior.hits, family_combo, args.seed, args.reps),
        family_rate=Rate(
            hits=family_hits, n=len(family_combo), rate=family_hits / len(family_combo)
        ),
        ready_combo=f"{ready_string or 'prior'} (others: prior)",
        ready_pair=paired(questions, prior.hits, ready_combo, args.seed, args.reps),
        ready_rate=Rate(hits=ready_hits, n=len(ready_combo), rate=ready_hits / len(ready_combo)),
        failures=failure_images(questions, families, runs),
        kept=kept_block(existing),
        orientation=orientation,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    oracles = {
        run.name: run.oracle or 'its path says "oracle" or "gold"'
        for run in runs
        if not eligible(run)
    }
    summary = {
        "combo": combo_string(chosen),
        "family_combo": {f: e.arm for f, e in ready.items() if e.arm is not None},
        "family_combo_any_arm": {family: run.name for family, run in per_family.items()},
        "arms": {run.name: run.result.overall.rate for run in runs},
        "not_scored": {item.name: item.reason for item in invalid},
        "oracles": oracles,
    }
    (args.exp_dir / "ab" / "leaderboard.json").write_text(json.dumps(summary, indent=2) + "\n")
    policy_file = {
        "schema": "answer_policy_v1",
        "generated": datetime.now(HELSINKI).isoformat(timespec="seconds"),
        "part": "val",
        "split_sha256": _sha256(args.exp_dir / "split.json"),
        "prior": _repo_path(args.prior),
        "rule": "per family, among the arms with golden v2 output (<arm>-golden, so the pipeline "
        "can run them end to end), the best arm on val whose paired 95% bootstrap interval against "
        "the train prior lies above 0, else prior; golden is the folder integ runs",
        "families": {family: entry.model_dump() for family, entry in ready.items()},
        "families_any_arm": {
            "rule": "the same rule over every arm, golden output or not: for information, never "
            "read by the backend",
            "families": {family: entry.model_dump() for family, entry in policy.items()},
        },
        "oracles_never_picked": oracles,
    }
    (args.exp_dir / "policy.json").write_text(json.dumps(policy_file, indent=2) + "\n", "utf-8")
    print(text)
    print(f"wrote {out}, {args.exp_dir / 'ab/leaderboard.json'} and {args.exp_dir / 'policy.json'}")


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
        answers = baselines.oracle(
            golden, _read_extras(_extras_for(args.golden)), _part1_gold_for(args.golden)
        )
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
    args.provenance = _provenance(args)  # before scoring, so a bad --commit or --setting fails fast
    return True


def _detail_path(args: argparse.Namespace, part: Part) -> tuple[Path | None, str | None]:
    """Where the full score JSON goes, and the run's stem when it is recorded. A --no-record run
    writes only to --out: without it, nowhere (None)."""
    if not args.recorded:
        return args.out, None
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
        claims, claims_sha256 = _claims_for(args.golden)
        result = score_golden(
            base,
            golden,
            answers,
            extras,
            extras_sha256,
            part1_gold=_part1_gold_for(args.golden),
            claims=claims,
            claims_sha256=claims_sha256,
        )
        print(format_table(result))
        slices = format_slices(result)
        if slices:
            print(f"\n{slices}")
        out, stem = _detail_path(args, "answering")
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
        out, stem = _detail_path(args, "answering")
    if out is None:
        print(NOT_WRITTEN)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    if stem is not None:
        record = make_record(
            result,
            against=args.against,
            name=args.name,
            note=args.note,
            milestone=args.milestone,
            golden_version=golden_version,
            questions_sha256=questions_sha256,
            score_sha256=_sha256(out),
            provenance=args.provenance,
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
    kept_sha: str | None = None
    if args.keep is None:
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
    else:  # read before anything is written: the kept v2 is usually the one rebuilt
        kept, kept_sha = _kept_files(args.keep)
        chosen, kept_strata, counts = keep(kept, stratum_of, sealed, params)
        stratum_of.update(kept_strata)
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
    if args.keep is None:
        extra, scale_counts = pick_scale_cases(cases, chosen, params)
        for file, part in extra.items():
            chosen[file], stratum_of[file] = part, "scale"
    else:
        scale_counts = count_scale_cases(cases, chosen)
    scale_picks = sum(stratum_of[file] == "scale" for file in chosen)
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
        kept=kept_sha,
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
        f"{len(files)} files ({'kept' if kept_sha else 'picked'}: plans, the PNG of each swiss "
        f"plan, {scale_picks} scale cases; "
        f"{len(conflicts)} conflict files, {len(slice_only)} of them only for that slice), "
        f"{len(picked_rows)} questions, "
        f"{len(extras or [])} extras lines"
    )
    for file in unscaled:
        print(f"no scale value or room areas yet: {file}")
    for file in missing:
        print(f"no gold yet: {file}")
    print(f"wrote {out}/{PART1}, {out}/{PART2} and {V2_MANIFEST}")


def _kept_files(manifest: Path) -> tuple[list[PlanFile], str]:
    """The files.jsonl next to a v2 manifest, and its sha256; fails unless the manifest describes
    that very file."""
    listed = manifest.parent / PART1 / "files.jsonl"
    described = PlansManifest.model_validate_json(manifest.read_text("utf-8")).files_sha256
    sha = _sha256(listed)
    if described.get(listed.relative_to(manifest.parent).as_posix()) != sha:
        raise ValueError(f"{listed} is not the files list its manifest describes ({manifest})")
    return [line for _, line in read_jsonl(listed, PlanFile)], sha


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
        gold = _v2_gold(args.golden_dir)
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
    out, stem = _detail_path(args, "extraction")
    if out is None:
        print(NOT_WRITTEN)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    if stem is not None:
        digest = hashlib.sha256()
        for path, extraction in sorted(chosen, key=lambda entry: entry[1].file):
            digest.update(f"{extraction.file}\n{_sha256(path)}\n".encode())
        record = make_extraction_record(
            result,
            against=args.against,
            name=args.name,
            note=args.note,
            milestone=args.milestone,
            golden_version=golden_version,
            gold_sha256=digest.hexdigest(),
            score_sha256=_sha256(out),
            provenance=args.provenance,
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


def run_series(args: argparse.Namespace) -> None:
    """The method's points on the golden set as a markdown table (Bogdan, 2026-11-13 22:49: "so at
    the end we will be able to show the improvement")."""
    points = series(
        args.name,
        read_history(args.results),
        read_extraction_history(args.results),
        args.golden_version,
    )
    if not points:
        raise ValueError(
            f"no recorded golden {args.golden_version} runs named {args.name!r} in {args.results}"
        )
    print(format_series_markdown(points, args.name, args.golden_version))


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


def run_annotated_region(args: argparse.Namespace) -> None:
    """golden-13 task 1: the region each train and val image's gold annotates, and whether the
    drawing visibly extends beyond it (stoa_eval/region.py)."""
    split_path = args.exp_dir / "split.json"
    if not split_path.is_file():
        raise ValueError(f"{split_path} is missing: run `python -m stoa_eval exp-split` first")
    split = ExpSplit.model_validate_json(split_path.read_text("utf-8"))
    part_of: dict[str, ExpPart] = {
        file: part for file, part in split.part_of().items() if part in REGION_PARTS
    }
    gold = {
        file: extraction
        for file, (_, extraction) in _extractions(args.gold / EXP_SOURCE).items()
        if file in part_of
    }
    sealed = set(_split_manifest(args.split_dir).eval_groups)
    golden_files = {
        row.file for _, row in read_jsonl(args.golden_dir / PART1 / "files.jsonl", PlanFile)
    }
    files = sorted(part_of)
    check_dev_only(files, sealed, golden_files, {file: gold[file].split for file in gold})
    jobs: list[tuple[ExpPart, Extraction, Path]] = [
        (part_of[file], gold[file], args.dataset / file) for file in files
    ]
    if args.workers > 1:
        spawn = multiprocessing.get_context("spawn")  # fork in a threaded process can deadlock
        with ProcessPoolExecutor(args.workers, mp_context=spawn) as pool:
            records = list(pool.map(annotate_file, jobs, chunksize=16))
    else:
        records = [annotate_file(job) for job in jobs]
    images: dict[str, ImageRegion] = dict(zip(files, records, strict=True))
    result = AnnotatedRegions(
        split_sha256=_sha256(split_path), styles=style_counts(images), images=images
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(result.model_dump_json() + "\n", encoding="utf-8")
    print("| style | part | images | extends | share |")
    print("| --- | --- | --- | --- | --- |")
    for style, parts in result.styles.items():
        for part, count in parts.items():
            share = count.extends / count.images
            print(f"| {style} | {part} | {count.images} | {count.extends} | {share:.1%} |")
    print(f"wrote {args.out}")


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
    command.add_argument(
        "--commit",
        help="the predictions came from a clean export (git archive) of this commit: it is "
        "recorded as the run's commit with dirty false, and this tree's HEAD as eval_commit",
    )
    command.add_argument(
        "--setting",
        action="append",
        metavar="NAME=VALUE",
        help="a setting the run used, e.g. EXTRACTOR_VECTOR=pdf; repeat for each",
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
    plans.add_argument(
        "--keep",
        type=Path,
        metavar="MANIFEST",
        help="freeze the file set: keep every file of the v2 this manifest.json describes "
        "(the conflict slice and the scale cases are recomputed)",
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
    scored.add_argument("--out", type=Path, help="--no-record only; without it nothing is written")
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
    part1.add_argument("--out", type=Path, help="--no-record only; without it nothing is written")
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

    points = commands.add_parser("series", help="one method's runs as a markdown table")
    points.add_argument("--name", default="pipeline", help="the method (default: pipeline)")
    points.add_argument("--golden-version", default="v2")
    points.add_argument("--results", type=Path, default=RESULTS)
    points.set_defaults(run=run_series)

    check = commands.add_parser("validate-extraction", help="check extraction_v1 JSON files")
    check.add_argument("paths", type=Path, nargs="+", help="files, or folders searched for *.json")
    check.add_argument(
        "--strict-v2",
        action="store_true",
        help="also need a scale value on every image and an area on every room with a polygon",
    )
    check.set_defaults(run=run_validate_extraction)

    exp = commands.add_parser(
        "exp-split", help="cut CubiCasa dev images into experiment train/val/test"
    )
    exp.add_argument("--split-dir", type=Path, default=SPLIT_DIR)
    exp.add_argument("--golden-dir", type=Path, default=GOLDEN_V2)
    exp.add_argument("--gold", type=Path, default=EXTRACTION_GOLD)
    exp.add_argument("--out-dir", type=Path, default=EXP_DIR)
    exp.add_argument("--seed", type=int, default=DEFAULT_EXP_SEED)
    exp.set_defaults(run=run_exp_split)

    ab = commands.add_parser("ab", help="compare two experiment arms on val (or test)")
    ab.add_argument("--a", required=True, help="an arm folder of extraction_v1, or gold|prior|none")
    ab.add_argument("--b", required=True, help="the challenger, same choices")
    ab.add_argument("--part", choices=["val", "test"], default="val")
    ab.add_argument("--certify", action="store_true", help="needed for test: once, shipped arm")
    ab.add_argument("--recertify-reason", help="why an arm already run on test runs again")
    ab.add_argument("--exp-dir", type=Path, default=EXP_DIR)
    ab.add_argument("--gold", type=Path, default=EXTRACTION_GOLD)
    ab.add_argument("--prior", type=Path, default=EXP_PRIOR, help="where the train prior goes")
    ab.add_argument(
        "--orientation",
        type=Path,
        help="JSON: file -> label or {turn, mirrored}; default: <exp-dir>/orientation.json if any",
    )
    ab.add_argument("--seed", type=int, default=AB_SEED)
    ab.add_argument("--reps", type=int, default=BOOTSTRAP_REPS, help="bootstrap resamples")
    ab.set_defaults(run=run_ab)

    gate = commands.add_parser("gate", help="E5: when may an arm's answer be marked sure")
    gate.add_argument("--arm", required=True, help="an arm folder, extraction_v1 with attrs.score")
    gate.add_argument("--second", help="a second arm, for the agreement signal")
    gate.add_argument("--part", choices=["val", "test"], default="val")
    gate.add_argument(
        "--signal", help=f"{', '.join(SIGNALS)} or a signal file's name; default: best val AUROC"
    )
    gate.add_argument(
        "--signal-file",
        type=Path,
        action="append",
        default=[],
        help="a gate_signal_v1 JSON (a value per family and image); repeat for each",
    )
    gate.add_argument(
        "--family-arm",
        action="append",
        default=[],
        metavar="FAMILY=FOLDER",
        help="answer FAMILY (a pattern: 'room:*') from another arm folder, as a runtime "
        "combination does; repeat for each",
    )
    gate.add_argument(
        "--g1main",
        type=Path,
        help=f"decide's cached G1main replies (data/stoa/exp/decide/G1main-high/raw): adds the "
        f"signal {G1MAIN}, Gemini's probability for each answer (DECISIONS_CONFIDENCE)",
    )
    gate.add_argument("--certify", action="store_true", help="needed for test: once, shipped arm")
    gate.add_argument("--recertify-reason", help="why an arm already certified runs again")
    gate.add_argument(
        "--thresholds", type=Path, help="test: the val run's gate JSON (default: its usual path)"
    )
    gate.add_argument(
        "--pool",
        action="store_true",
        help="val: one threshold per family group (elements, plans, rooms), the plan as the unit, "
        "delta / groups; test reuses the val gate's groups",
    )
    gate.add_argument("--target", type=float, default=TARGET, help="exact share among sure")
    gate.add_argument("--delta", type=float, default=DELTA)
    gate.add_argument("--exp-dir", type=Path, default=EXP_DIR)
    gate.add_argument("--gold", type=Path, default=EXTRACTION_GOLD)
    gate.add_argument("--seed", type=int, default=GATE_SEED)
    gate.set_defaults(run=run_gate)

    policy = commands.add_parser(
        "gate-policy", help="the product's gate file (gate_policy_v1) from a val gate JSON"
    )
    policy.add_argument("--gate", type=Path, required=True, help="data/stoa/exp/ab/gate-*-val.json")
    policy.add_argument("--out", type=Path, default=EXP_DIR / "gate.json")
    policy.set_defaults(run=run_gate_policy)

    board = commands.add_parser("leaderboard", help="every experiment arm on val against prior")
    board.add_argument("--exp-dir", type=Path, default=EXP_DIR)
    board.add_argument("--gold", type=Path, default=EXTRACTION_GOLD)
    board.add_argument("--prior", type=Path, default=EXP_PRIOR, help="where the train prior goes")
    board.add_argument("--out", type=Path, default=LEADERBOARD)
    board.add_argument("--seed", type=int, default=AB_SEED)
    board.add_argument("--reps", type=int, default=BOOTSTRAP_REPS, help="bootstrap resamples")
    board.set_defaults(run=run_leaderboard)

    regions = commands.add_parser(
        "annotated-region", help="the region each train/val image's gold annotates, ink beyond it"
    )
    regions.add_argument("--exp-dir", type=Path, default=EXP_DIR)
    regions.add_argument("--split-dir", type=Path, default=SPLIT_DIR)
    regions.add_argument("--golden-dir", type=Path, default=GOLDEN_V2)
    regions.add_argument("--gold", type=Path, default=EXTRACTION_GOLD)
    regions.add_argument("--dataset", type=Path, default=DATASET, help="where data/... resolves")
    regions.add_argument("--out", type=Path, default=REGIONS)
    regions.add_argument("--workers", type=int, default=1, help="processes reading images")
    regions.set_defaults(run=run_annotated_region)

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
