"""The experiment leaderboard (`stoa_eval leaderboard`, brief golden-12): every arm under
`data/stoa/exp/<track>/.../<arm>/` scored on val against the train prior with `ab`'s machinery,
the best arm per family and per family group, a best-of combo for integ, and the val images most
arms get wrong.

An arm is a folder whose own *.json files include one that looks like extraction_v1 (a `schema`
key, or `file` with `pages`); folders under a part starting "_" and `ab/` are skipped. An arm that
does not validate, or has no val image, is listed with the reason. Each arm's scoring is cached
under `data/stoa/exp/ab/cache/` by a hash of its files, the split, the gold, the prior and the
code that answers and scores, so a rerun only scores what changed.

An oracle arm reads gold at answer time (gold rooms, gold exemplars, the gold annotated region):
it is scored and shown, but never picked for a combo, the policy or as a failure judge. An arm is
an oracle when its folder or a parent below the exp dir holds an `ORACLE` file (its text says what
gold it reads), when a glob in `data/stoa/exp/oracles.json` matches its name, or when its path
says "oracle" or "gold" ("golden" excepted).
"""

import fnmatch
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .ab import ArmResult, Paired, Rate, paired, style_of
from .models import NumberedQuestion

GROUPS: dict[str, tuple[str, ...]] = {
    "elements": ("door", "window", "toilet", "sink", "shower+bathtub"),
    "plans": ("plan",),
    "rooms": (
        "sauna",
        "room:kitchen",
        "room:bedroom",
        "room:bathroom",
        "room:wc",
        "room:balcony",
    ),
}
SKIP = {"ab"}  # data/stoa/exp/ab holds results, not arms
FAILURES = 20
TAGS_BEGIN, TAGS_END = "<!-- failure-analysis:begin -->", "<!-- failure-analysis:end -->"


ORACLE_MARKER = "ORACLE"  # a text file in an arm folder or a parent: what gold the arm reads


class OracleList(BaseModel):
    """oracle_arms_v1 (data/stoa/exp/oracles.json): arms that read gold at answer time."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal["oracle_arms_v1"] = Field(alias="schema")
    arms: dict[str, str] = Field(description="glob on track/arm -> what gold it reads")


def load_oracles(path: Path) -> dict[str, str]:
    """The deny list's globs; none when the file is missing."""
    if not path.is_file():
        return {}
    return OracleList.model_validate_json(path.read_text("utf-8")).arms


def oracle_name(name: str) -> bool:
    """The path says "oracle" or "gold" (cvx/A-oracle, region/oracle-gold, photo/val-hard/gold);
    "golden" is the golden v2 test set, not gold at answer time."""
    lowered = name.lower()
    return "oracle" in lowered or "gold" in lowered.replace("golden", "")


def oracle_reason(name: str, folder: Path, exp_dir: Path, deny: Mapping[str, str]) -> str | None:
    """Why the arm reads gold at answer time, or None (see the module docstring)."""
    root, here = exp_dir.resolve(), folder.resolve()
    for parent in (here, *here.parents):
        if parent == root or not parent.is_relative_to(root):
            break
        marker = parent / ORACLE_MARKER
        if marker.is_file():
            why = " ".join(marker.read_text("utf-8").split())[:160]
            return f"{ORACLE_MARKER} file in {parent.relative_to(root).as_posix()}: {why}"
    for pattern, why in deny.items():
        if fnmatch.fnmatchcase(name, pattern):
            return f"oracles.json {pattern}: {why}"
    if oracle_name(name):
        return 'its path says "oracle" or "gold"'
    return None


def eligible(run: "ArmRun") -> bool:
    """Not an oracle: may be picked for a combo, the policy or as a failure judge."""
    return run.oracle is None and not oracle_name(run.name)


def group_of_family(family: str) -> str | None:
    for group, families in GROUPS.items():
        if family in families:
            return group
    return None


def _looks_like_extraction(path: Path) -> bool:
    try:
        body = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(body, dict) and ("schema" in body or ("file" in body and "pages" in body))


def find_arms(exp_dir: Path) -> list[Path]:
    """Folders under exp_dir that hold extraction_v1-like JSON files of their own."""
    arms: list[Path] = []
    for folder in sorted(p for p in exp_dir.rglob("*") if p.is_dir()):
        parts = folder.relative_to(exp_dir).parts
        if parts[0] in SKIP or any(part.startswith("_") for part in parts):
            continue
        if any(_looks_like_extraction(path) for path in sorted(folder.glob("*.json"))[:5]):
            arms.append(folder)
    return arms


def digest_files(paths: Iterable[Path], root: Path) -> str:
    """sha256 over (path relative to root, sha256 of the bytes), in path order."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def arm_digest(folder: Path) -> str:
    """What `ab` reads of an arm: every *.json under it, except under a part starting "_"."""
    paths = [
        p
        for p in folder.rglob("*.json")
        if not any(part.startswith("_") for part in p.relative_to(folder).parts)
    ]
    return digest_files(paths, folder)


class ArmRun(BaseModel):
    """One arm scored on val: what the cache keeps."""

    model_config = ConfigDict(extra="forbid")

    key: str
    name: str = Field(description="track/arm, as in the combo string")
    result: ArmResult
    hits: dict[int, bool]
    refused: list[int]
    against_prior: Paired | None = None
    modified: str = Field(description="newest file time of the arm, Europe/Helsinki")
    oracle: str | None = Field(
        default=None, description="why it reads gold at answer time (set on each run, not cached)"
    )


class Invalid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    reason: str


def group_rate(
    questions: Sequence[NumberedQuestion], hits: Mapping[int, bool], families: Mapping[int, str]
) -> dict[str, Rate]:
    tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for q in questions:
        group = group_of_family(families.get(q.id, ""))
        if group is not None:
            tally[group][0] += hits[q.id]
            tally[group][1] += 1
    return {
        group: Rate(hits=h, n=n, rate=h / n if n else None)
        for group in GROUPS
        for h, n in [tally[group]]
    }


def best_by(runs: Sequence[ArmRun], family: str) -> tuple[ArmRun | None, float | None]:
    """The run with the highest exact rate on a family; ties go to the earlier name."""
    best: tuple[ArmRun | None, float | None] = (None, None)
    for run in sorted(filter(eligible, runs), key=lambda r: r.name):
        rate = run.result.by_family.get(family)
        value = rate.rate if rate is not None else None
        if value is not None and (best[1] is None or value > best[1]):
            best = (run, value)
    return best


def best_per_group(
    questions: Sequence[NumberedQuestion],
    families: Mapping[int, str],
    runs: Sequence[ArmRun],
    prior: ArmRun,
) -> dict[str, ArmRun]:
    """Per group, the run with the highest exact rate on the group's questions, if it beats the
    prior there (ties go to the earlier name)."""
    floor = group_rate(questions, prior.hits, families)
    chosen: dict[str, ArmRun] = {}
    for group in GROUPS:
        best_rate = floor[group].rate or 0.0
        for run in sorted(filter(eligible, runs), key=lambda r: r.name):
            rate = group_rate(questions, run.hits, families)[group].rate
            if rate is not None and rate > best_rate:
                chosen[group], best_rate = run, rate
    return chosen


def combo_string(chosen: Mapping[str, ArmRun]) -> str:
    return ",".join(
        f"{group}={chosen[group].name if group in chosen else 'prior'}" for group in GROUPS
    )


def orientation_rates(
    questions: Sequence[NumberedQuestion], hits: Mapping[int, bool], orientation: Mapping[str, str]
) -> tuple[Rate, Rate]:
    """(upright, every other orientation) exact rates; images without an entry are left out."""
    tally = {True: [0, 0], False: [0, 0]}
    for q in questions:
        label = orientation.get(q.path)
        if label is not None:
            tally[label == "upright"][0] += hits[q.id]
            tally[label == "upright"][1] += 1
    (up_hits, up_n), (other_hits, other_n) = tally[True], tally[False]
    return (
        Rate(hits=up_hits, n=up_n, rate=up_hits / up_n if up_n else None),
        Rate(hits=other_hits, n=other_n, rate=other_hits / other_n if other_n else None),
    )


def combo_hits(
    questions: Sequence[NumberedQuestion],
    families: Mapping[int, str],
    chosen: Mapping[str, ArmRun],
    prior: ArmRun,
) -> dict[int, bool]:
    """Each question answered by the arm chosen for its family, else for its group, else the
    prior."""
    hits: dict[int, bool] = {}
    for q in questions:
        family = families.get(q.id, "")
        group = group_of_family(family) or ""
        hits[q.id] = chosen.get(family, chosen.get(group, prior)).hits[q.id]
    return hits


class FailureImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    style: str
    score: float = Field(description="sum over questions of the share of tracks that get it wrong")
    questions: int
    families: list[str] = Field(description="families most tracks get wrong (share >= 0.5)")
    tracks: int = Field(description="tracks that answered something on the image")


def track_of(run: ArmRun) -> str:
    return run.name.split("/", 1)[0]


def family_judges(runs: Sequence[ArmRun]) -> dict[str, list[ArmRun]]:
    """Per family, each track's best arm on it, if that arm covers at least half of val and gets
    some of the family right (so an arm that only writes 0 for a family it doesn't read, or a
    smoke run on a few images, does not count)."""
    judges: dict[str, list[ArmRun]] = defaultdict(list)
    serious = [
        r
        for r in runs
        if eligible(r) and (r.result.images - r.result.missing_images) * 2 >= r.result.images
    ]
    for family in (f for fams in GROUPS.values() for f in fams):
        by_track: dict[str, tuple[float, ArmRun]] = {}
        for run in sorted(serious, key=lambda r: r.name):
            rate = run.result.by_family.get(family)
            value = rate.rate if rate is not None and rate.rate is not None else 0.0
            if value > 0 and value > by_track.get(track_of(run), (0.0, run))[0]:
                by_track[track_of(run)] = (value, run)
        judges[family] = [run for _, run in by_track.values()]
    return judges


def failure_images(
    questions: Sequence[NumberedQuestion],
    families: Mapping[int, str],
    runs: Sequence[ArmRun],
    top: int = FAILURES,
) -> list[FailureImage]:
    """The images most tracks get wrong: per question, the share of the family's judges
    (`family_judges`) that answer it wrongly (a refusal is not an answer); an image's score is
    the sum over its questions."""
    judges = family_judges(runs)
    refused = {run.name: set(run.refused) for run in runs}
    score: dict[str, float] = defaultdict(float)
    asked: dict[str, int] = defaultdict(int)
    wrong_families: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    answering: dict[str, set[str]] = defaultdict(set)
    for q in questions:
        family = families.get(q.id, "unsupported")
        tried = [run for run in judges.get(family, []) if q.id not in refused[run.name]]
        asked[q.path] += 1
        if tried:
            share = sum(not run.hits[q.id] for run in tried) / len(tried)
            score[q.path] += share
            wrong_families[q.path][family].append(share)
            answering[q.path] |= {track_of(run) for run in tried}
    order = sorted(asked, key=lambda f: (-score[f], f))[:top]
    return [
        FailureImage(
            file=file,
            style=style_of(file),
            score=round(score[file], 3),
            questions=asked[file],
            families=sorted(
                fam for fam, values in wrong_families[file].items() if max(values) >= 0.5
            ),
            tracks=len(answering[file]),
        )
        for file in order
    ]


class PolicyEntry(BaseModel):
    """One family's source in policy.json: an arm, or the prior when no arm beats it on val by
    an interval that excludes 0."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="the arm folder (repo-relative), or prior")
    arm: str | None = Field(description="track/arm, null for the prior")
    questions: int
    val_exact: float | None
    prior_exact: float | None
    diff: float | None = Field(description="arm minus prior on the family's val questions")
    ci_low: float | None
    ci_high: float | None
    golden: str | None = Field(
        default=None,
        description="the arm's golden v2 output (its folder + -golden); null for the prior or "
        "when the arm has none",
    )


def family_policy(
    questions: Sequence[NumberedQuestion],
    families: Mapping[int, str],
    runs: Sequence[ArmRun],
    prior: ArmRun,
    folders: Mapping[str, str],
    seed: int,
    reps: int,
    golden: Mapping[str, str] | None = None,
) -> dict[str, PolicyEntry]:
    """Per family, the arm with the best val exact rate whose paired bootstrap interval against
    the prior (images as the unit, the family's questions only) lies above 0; else the prior.
    Arms are tried best first, and only those whose rate beats the prior's. `golden`: arm ->
    its golden v2 folder, noted on the entry."""
    policy: dict[str, PolicyEntry] = {}
    for family in (f for fams in GROUPS.values() for f in fams):
        mine = [q for q in questions if families.get(q.id) == family]
        floor = prior.result.by_family.get(family)
        floor_rate = floor.rate if floor is not None else None
        candidates = sorted(
            (
                (rate.rate, run.name, run)
                for run in runs
                if eligible(run)
                and (rate := run.result.by_family.get(family)) is not None
                and rate.rate is not None
                and rate.rate > (floor_rate or 0.0)
            ),
            key=lambda item: (-item[0], item[1]),
        )
        entry = PolicyEntry(
            source="prior", arm=None, questions=len(mine), val_exact=floor_rate,
            prior_exact=floor_rate, diff=None, ci_low=None, ci_high=None,
        )  # fmt: skip
        for rate, name, run in candidates:
            pair = paired(mine, prior.hits, run.hits, seed, reps)
            if pair.ci_low is not None and pair.ci_low > 0:
                entry = PolicyEntry(
                    source=folders[name], arm=name, questions=len(mine), val_exact=rate,
                    prior_exact=floor_rate, diff=pair.diff, ci_low=pair.ci_low,
                    ci_high=pair.ci_high, golden=(golden or {}).get(name),
                )  # fmt: skip
                break
        policy[family] = entry
    return policy


def family_policies(
    questions: Sequence[NumberedQuestion],
    families: Mapping[int, str],
    runs: Sequence[ArmRun],
    prior: ArmRun,
    folders: Mapping[str, str],
    seed: int,
    reps: int,
    golden: Mapping[str, str],
) -> tuple[dict[str, PolicyEntry], dict[str, PolicyEntry]]:
    """(shipped, any arm): the family policy over the arms with golden v2 output (`golden`: arm
    -> folder), which the pipeline can run end to end, and over every arm, for information."""
    ready = [run for run in runs if run.name in golden]
    shipped = family_policy(questions, families, ready, prior, folders, seed, reps, golden)
    any_arm = family_policy(questions, families, runs, prior, folders, seed, reps, golden)
    return shipped, any_arm


def policy_runs(policy: Mapping[str, PolicyEntry], runs: Sequence[ArmRun]) -> dict[str, ArmRun]:
    """family -> the run the policy picks (families on the prior are left out)."""
    by_name = {run.name: run for run in runs}
    return {f: by_name[e.arm] for f, e in policy.items() if e.arm is not None}


def _pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate:.1%}"


def _pp(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:+.1f}"


def format_leaderboard(
    *,
    generated: str,
    questions: Sequence[NumberedQuestion],
    families: Mapping[int, str],
    runs: Sequence[ArmRun],
    references: Mapping[str, ArmRun],
    invalid: Sequence[Invalid],
    combo: str,
    combo_pair: Paired,
    combo_rate: Rate,
    family_combo: str,
    family_pair: Paired,
    family_rate: Rate,
    ready_combo: str,
    ready_pair: Paired,
    ready_rate: Rate,
    failures: Sequence[FailureImage],
    kept: str,
    orientation: Mapping[str, str] | None = None,
) -> str:
    prior = references["prior"]
    images = len({q.path for q in questions})
    lines = [
        "# Experiment leaderboard (val)",
        "",
        f"Generated {generated} by `cd eval && uv run python -m stoa_eval leaderboard` (golden). "
        f"Val: {images} images, {len(questions)} questions. Every arm is answered by the backend's "
        "templates parser and takeoff and judged by Stoa's rule (`stoa_eval ab`); a missing image "
        "is wrong. Delta = arm minus the train prior, with the 95% bootstrap interval over images "
        "(10,000 resamples): only an interval above 0 is a win.",
        "",
        "Groups: elements = door, window, toilet, sink, shower+bathtub; plans = floors; rooms = "
        "sauna, kitchen, bedroom, bathroom, wc, balcony.",
        "",
        "Orientation (exact on upright / turned images): "
        + ("from data/stoa/exp/orientation.json." if orientation else "no orientation file yet."),
        "",
        "| arm | val images | exact | elements | plans | rooms | upright / turned "
        "| vs prior (pp) [95%] | verdict | arm files as of |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    ordered = sorted(runs, key=lambda r: (-(r.result.overall.rate or 0.0), r.name))
    for run in [*ordered, *references.values()]:
        groups = group_rate(questions, run.hits, families)
        pair = run.against_prior
        delta = (
            f"{_pp(pair.diff)} [{_pp(pair.ci_low)}, {_pp(pair.ci_high)}]"
            if pair is not None
            else "-"
        )
        verdict = (
            "-"
            if pair is None
            else pair.verdict.replace("B better", "better").replace("A better", "worse")
        )
        covered = run.result.images - run.result.missing_images
        name = run.name if run.name not in references else f"*{run.name}* (reference)"
        if run.name not in references and not eligible(run):
            why = (run.oracle or "its name").replace("|", "/")
            name += f" (reads gold at answer time, never picked: {why})"
        turned = "-"
        if orientation:
            up, other = orientation_rates(questions, run.hits, orientation)
            turned = f"{_pct(up.rate)} / {_pct(other.rate)}"
        lines.append(
            f"| {name} | {covered}/{run.result.images} | {_pct(run.result.overall.rate)} "
            f"| {_pct(groups['elements'].rate)} | {_pct(groups['plans'].rate)} "
            f"| {_pct(groups['rooms'].rate)} | {turned} | {delta} | {verdict} | {run.modified} |"
        )
    lines += [
        "",
        "## Best arm per family",
        "",
        "| family | questions | best arm | its exact | prior | gold |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for family in [f for fams in GROUPS.values() for f in fams]:
        best, value = best_by(runs, family)
        n = prior.result.by_family.get(family)
        gold = references["gold"].result.by_family.get(family)
        lines.append(
            f"| {family} | {n.n if n else 0} | {best.name if best else '-'} | {_pct(value)} "
            f"| {_pct(n.rate if n else None)} | {_pct(gold.rate if gold else None)} |"
        )
    lines += [
        "",
        "## Best-of combo (for integ)",
        "",
        f"`{combo}`",
        "",
        "Per group, the arm with the highest exact rate on that group's val questions; `prior` "
        "when no arm beats the prior there. Answering each question from its group's arm gives "
        f"{_pct(combo_rate.rate)} ({combo_rate.hits}/{combo_rate.n}) on val, "
        f"{_pp(combo_pair.diff)} pp against the prior [{_pp(combo_pair.ci_low)}, "
        f"{_pp(combo_pair.ci_high)}]. The arms were picked on val, so this is optimistic; integ's "
        "golden run is the honest number.",
        "",
        "Per family instead of per group, over every arm: the best arm on each family whose "
        "interval against the prior lies above 0, else the prior (`families_any_arm` in "
        "`data/stoa/exp/policy.json`, for information; nothing reads it):",
        "",
        f"`{family_combo}`",
        "",
        f"{_pct(family_rate.rate)} ({family_rate.hits}/{family_rate.n}) on val, "
        f"{_pp(family_pair.diff)} pp against the prior [{_pp(family_pair.ci_low)}, "
        f"{_pp(family_pair.ci_high)}], equally optimistic.",
        "",
        "The same rule over the arms that have golden v2 output (a folder `<arm>-golden`), the "
        "arms the pipeline can run end to end: `families` in policy.json, which ANSWER_POLICY "
        "reads and integ runs on golden (each family names its golden folder):",
        "",
        f"`{ready_combo}`",
        "",
        f"{_pct(ready_rate.rate)} ({ready_rate.hits}/{ready_rate.n}) on val, "
        f"{_pp(ready_pair.diff)} pp against the prior [{_pp(ready_pair.ci_low)}, "
        f"{_pp(ready_pair.ci_high)}].",
        "",
        "## Arms not scored",
        "",
    ]
    lines += [f"- {item.name}: {item.reason}" for item in invalid] or ["- none"]
    lines += [
        "",
        f"## The {len(failures)} val images most tracks get wrong",
        "",
        "Judges: per family, each track's best arm on it among arms that cover at least half of "
        "val and get some of that family right. Score: per question, the share of judges that "
        "answer it wrongly (refusals left out), summed over the image's questions.",
        "",
        "| image | style | score | questions | tracks | families most tracks miss |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for image in failures:
        lines.append(
            f"| {image.file} | {image.style} | {image.score:.2f} | {image.questions} "
            f"| {image.tracks} | {', '.join(image.families)} |"
        )
    lines += ["", TAGS_BEGIN, kept.strip() or "(failure tags not written yet)", TAGS_END, ""]
    return "\n".join(lines)


def kept_block(existing: str) -> str:
    """The hand-written failure analysis between the markers of the previous file."""
    if TAGS_BEGIN in existing and TAGS_END in existing:
        return existing.split(TAGS_BEGIN, 1)[1].split(TAGS_END, 1)[0]
    return ""


def against_prior(
    questions: Sequence[NumberedQuestion], run: ArmRun, prior: ArmRun, seed: int, reps: int
) -> Paired:
    return paired(questions, prior.hits, run.hits, seed, reps)
