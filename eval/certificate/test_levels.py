"""confidence section Z, step 2 (eval side): the levels test_scores.py wrote, joined with the truth.
Prints no row. Per cut: per level the share and the exact rate with Wilson 95% intervals, pooled and per
family, next to the val numbers (cross-fit on the gate halves from schemes.json, in-sample from
levels-val-insample*.json); wrong answers per level; one pooled row with the build plan's guard (window
gets no Medium); the High row as integ's certificate counts it (per question).

A unit is a (page, family) pair, as on val: its questions (en/fi) share answer, truth and level, so
shares and exact rates are the per-question ones and the intervals are not narrowed by the pairs.

Run from an eval checkout (cd <export>/eval; PYTHONPATH=.:<repo>/prototypes/confidence):
    uv run --locked python <repo>/prototypes/confidence/test_levels.py --truth <questions with truth .jsonl> \
        --run <run dir> --levels <levels.jsonl> --out <dir>
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from stats import wilson
from stoa_eval.ab import hits_of
from stoa_eval.models import Answer, NumberedQuestion

REPO = Path(__file__).resolve().parents[2]  # the repo root (the run had the checkout's absolute path here)
VAL = REPO / "data/stoa/exp/confidence"
LEVELS = ("High", "Medium", "Low")
CUTS = {"020": ("0.20", "B P(wrong) <= 0.20", "levels-val-insample.json"),
        "010": ("0.10", "B P(wrong) <= 0.10", "levels-val-insample-c010.json"),
        # the backend's own level with the committed policy (window never Medium, held answers Low)
        "shipped": ("0.20, shipped rule", "B P(wrong) <= 0.20", "levels-val-insample.json")}  # fmt: skip

Cells = dict[str, dict[str, list[int]]]  # family -> level -> [n, exact]


def cell(c: list[int] | None, total: int) -> str:
    if not c or not c[0]:
        return "0"
    n, k = c
    lo, hi = wilson(k, n)
    return f"{n / total:.1%} ({n}), {k / n:.1%} [{lo:.1%}, {hi:.1%}]"


def short(c: list[int] | None, total: int) -> str:
    if not c or not c[0]:
        return "0"
    return f"{c[0] / total:.1%}, {c[1] / c[0]:.1%}"


def tally(units: list[tuple[str, str, bool]]) -> Cells:
    by: Cells = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for family, level, exact in units:
        for fam in (family, "pooled"):
            by[fam][level][0] += 1
            by[fam][level][1] += exact
    return by


def main() -> None:
    args = argparse.ArgumentParser()
    for name in ("--truth", "--run", "--levels", "--out"):
        args.add_argument(name, type=Path, required=True)
    args.add_argument("--answers", type=Path)  # the answers to judge; default: the run's
    args.add_argument("--cuts", default="020,010")
    a = args.parse_args()
    rows = [json.loads(line) for line in a.levels.read_text().splitlines() if line.strip()]
    ids = {r["id"] for r in rows}
    questions = [NumberedQuestion.model_validate(q) for q in map(json.loads, a.truth.read_text().splitlines())
                 if q["id"] in ids]  # fmt: skip
    assert len(questions) == len(rows), f"{len(questions)} truths for {len(rows)} rows"
    answers = {x.id: x for x in (Answer.model_validate_json(line)
                                 for line in (a.answers or a.run / "answers.jsonl").read_text().splitlines())}  # fmt: skip
    exact = hits_of(questions, answers)
    rated = [r for r in rows if r["certified"] is not None]
    crossfit = json.loads((VAL / "schemes.json").read_text())["gate_halves"]["by"]
    made: dict = {"questions": len(rows), "rated": len(rated), "not_rated": len(rows) - len(rated),
                  "mismatch": sum(r["mismatch"] for r in rows)}  # fmt: skip
    text = [f"{len(rows)} questions, {len(rated)} rated, {len(rows) - len(rated)} not rated (refusals), "
            f"{made['mismatch']} mismatch (kept), {sum(r['score'] is None for r in rated)} rated without a score "
            f"(Low unless certified)."]  # fmt: skip
    # the High row as integ's certificate counts it: per question
    wrong = [r for r in rated if not exact[r["id"]]]
    flagged = [r for r in rated if not r["certified"]]
    unflagged = [r for r in rated if r["certified"]]
    caught = sum(not r["certified"] for r in wrong)
    made["certificate"] = {"rated": len(rated), "wrong": len(wrong), "flagged": len(flagged), "caught": caught,
                           "unflagged": len(unflagged), "unflagged_exact": sum(exact[r["id"]] for r in unflagged)}  # fmt: skip
    text.append(
        f"Check against integ's certificate (per question): {len(rated)} rated, {len(wrong)} wrong, "
        f"flagged {len(flagged) / len(rated):.1%}, wrong flagged {caught}/{len(wrong)} "
        f"({caught / max(1, len(wrong)):.1%}), unflagged exact "
        f"{sum(exact[r['id']] for r in unflagged) / max(1, len(unflagged)):.1%} ({len(unflagged)})."
    )
    cuts = a.cuts.split(",")
    if {"020", "shipped"} <= set(cuts):
        moved = Counter((r["family"], r["level_020"], r["level_shipped"]) for r in rated
                        if r["level_020"] != r["level_shipped"])  # fmt: skip
        made["shipped_vs_020"] = {" / ".join(k): n for k, n in sorted(moved.items())}
        text.append(f"Questions whose shipped level is not the pre-registered rule's: {sum(moved.values())} "
                    f"(family / pre-registered / shipped: {made['shipped_vs_020']}).")  # fmt: skip
    for cut in cuts:
        label, scheme, insample_name = CUTS[cut]
        key = f"level_{cut}"
        seen = {(r["file"], r["family"], r[key], exact[r["id"]]) for r in rated}
        pages = {(f, fam) for f, fam, _, _ in seen}
        units = [(fam, level, ok) for _, fam, level, ok in seen]
        by = tally(units)
        guard = tally([(fam, "Low" if fam == "window" and level == "Medium" else level, ok) for fam, level, ok in units])
        val = crossfit[scheme]
        val = {f: {lv: [c["n"], c["exact"]] for lv, c in levels.items()} for f, levels in val.items()}
        insample = json.loads((VAL / insample_name).read_text())
        made[cut] = {"units": len(units), "split_units": len(units) - len(pages),
                     "by": by, "guard_pooled": guard["pooled"]}  # fmt: skip
        total = len(units)
        text += ["", f"### Cut {label}: Medium = asks and P(wrong) <= {label}", "",
                 f"{total} (page, family) units; {len(units) - len(pages)} units split because a page's questions "
                 "of one family differ in level or exactness.", "",
                 "| level | test: share (units), exact [95%] | wrong on test | val cross-fit: share (units), exact [95%] | "
                 "val in-sample |", "| --- | --- | --- | --- | --- |"]  # fmt: skip
        vt, it = sum(c[0] for c in val["pooled"].values()), sum(c[0] for c in insample["pooled"].values())
        for lv in LEVELS:
            c = by["pooled"].get(lv, [0, 0])
            text.append(f"| {lv} | {cell(c, total)} | {c[0] - c[1]} | {cell(val['pooled'].get(lv), vt)} | "
                        f"{short(insample['pooled'].get(lv), it)} |")  # fmt: skip
        g = guard["pooled"]
        text += ["", "With the build plan's guard (window gets no Medium): "
                 + "; ".join(f"{lv} {cell(g.get(lv), total)}" for lv in LEVELS) + ".", "",
                 "Per family, test (first line of a cell) and val cross-fit (after the slash):", "",
                 "| family | units | High | Medium | Low |", "| --- | --- | --- | --- | --- |"]  # fmt: skip
        for fam in sorted(f for f in by if f != "pooled"):
            n = sum(c[0] for c in by[fam].values())
            vn = sum(c[0] for c in val.get(fam, {}).values())
            text.append(f"| {fam} | {n} | " + " | ".join(
                f"{cell(by[fam].get(lv), n)} / val {short(val.get(fam, {}).get(lv), vn or 1)}" for lv in LEVELS) + " |")  # fmt: skip
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "levels-table.json").write_text(json.dumps(made, indent=1), "utf-8")
    (a.out / "levels-table.md").write_text("\n".join(text) + "\n", "utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main()
