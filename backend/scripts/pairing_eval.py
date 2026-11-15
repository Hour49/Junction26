"""W4 pairing eval: how often W1's pair() pairs a plan with the right discipline picture, refuses,
or pairs wrong.

Pre-registered in .agents/research/pairing-eval/prereg.md (local) before any run; the bar applies to
the product condition (plan storey None, file names kept). Inputs stay local (data/ is gitignored):

    uv run python scripts/pairing_eval.py \
        --plans ../data/stoa/bench/pairing-eval/plans \
        --pictures ../data/stoa/bench/pairing-eval/digitalhub/clean-150 \
        --scans ../data/ext/real-services --floors floors.json --out <dir>

--plans: one extraction_v1 JSON per plan PDF (GET /api/drawings/<id>/model). --pictures: the bench
renderer's <name>.png + <name>.json truth. --floors: {"<plan file>": "<truth storey words>"},
written before the run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

DISCIPLINE_WORDS = {
    "heating": ("heating", "hot water"),
    "plumbing": ("plumbing", "sanitary"),
    "ventilation": ("ventilat", "air conditioning"),
    "electrical": ("electrical", "switchgear"),
}
FLOOR_WORDS = re.compile(
    r"\b(first|second|third|ground|basement|attic|typical|roof)(?: floor)?\b|\bboiler room\b", re.I
)


def hidden(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:8] + Path(name).suffix


def plan_sheet(model: dict[str, Any], key: str, names: bool) -> dict[str, Any]:
    """As service_tools._sheet builds an architectural plan: no storey, size from the read scale."""
    page = model["pages"][0]
    m = model["scale"]["m_per_unit"]
    rooms = tuple(
        (r["label"], ((r["box"][0] + r["box"][2]) / 2, (r["box"][1] + r["box"][3]) / 2))
        for r in model["rooms"]
        if r.get("label") and r.get("page", 1) == page["page"]
    )
    file = model["file"] if isinstance(model["file"], str) else model["file"]["path"]
    return {
        "drawing_id": key,
        "page": page["page"],
        "storey": None,
        "size_m": (page["width"] * m, page["height"] * m) if m else None,
        "rooms": rooms,
        "name": file if names else hidden(file),
        "sheet_number": None,
        "disciplines": (),
    }


def picture_sheet(truth: dict[str, Any], names: bool) -> dict[str, Any]:
    """A rendered discipline picture as read: its title's storey, its scale, no rooms."""
    w, h = truth["size_px"]
    return {
        "drawing_id": Path(truth["picture"]).stem,
        "page": 1,
        "storey": truth["storey"],
        "size_m": (w / truth["px_per_m"], h / truth["px_per_m"]),
        "rooms": (),
        "name": truth["picture"] if names else hidden(truth["picture"]),
        "sheet_number": None,
        "disciplines": (truth["discipline"],),
    }


def scan_sheet(key: str, title: str, size_m: Any, names: bool) -> dict[str, Any]:
    """A real scan of another building, worst case: the plan's size, so only words refuse it."""
    low = title.lower()
    floor = FLOOR_WORDS.search(title)
    name = f"{title.removeprefix('File:')}" if title else f"{key}.png"
    return {
        "drawing_id": f"scan:{key}",
        "page": 1,
        "storey": floor.group(0) if floor else None,
        "size_m": size_m,
        "rooms": (),
        "name": name if names else hidden(name),
        "sheet_number": None,
        "disciplines": tuple(
            d for d, words in DISCIPLINE_WORDS.items() if any(w in low for w in words)
        ),
    }


def units(
    plans: dict[str, dict[str, Any]],
    floors: dict[str, str],
    pictures: list[dict[str, Any]],
    scans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Positive and negative units: (plan, discipline), its discipline's pictures + scans."""
    out = []
    for key, plan in plans.items():
        floor = floors[key]
        for d in sorted({p["disciplines"][0] for p in pictures}):
            mine = [p for p in pictures if p["disciplines"] == (d,)]
            right = {p["drawing_id"] for p in mine if p["storey"] == floor}
            if not right:
                continue
            for negative in (False, True):
                cands = [p for p in mine if not (negative and p["drawing_id"] in right)] + scans
                out.append(
                    {
                        "plan": key,
                        "floor": floor,
                        "discipline": d,
                        "negative": negative,
                        "right": sorted(right) if not negative else [],
                        "plan_sheet": plan,
                        "candidates": cands,
                    }
                )
    return out


def score(unit: dict[str, Any], results: Sequence[Any], is_refusal: Callable[[Any], bool]) -> dict:
    """right / refused / wrong for one unit; at most one pairing wins, the highest score."""
    paired = [(c, r) for c, r in zip(unit["candidates"], results, strict=True) if not is_refusal(r)]
    if not paired:
        outcome, picked = ("right" if unit["negative"] else "refused"), None
    else:
        c, r = max(paired, key=lambda cr: getattr(cr[1], "score", None) or 1.0)
        picked = (c["drawing_id"], getattr(r, "reason", str(r)))
        ok = not unit["negative"] and c["drawing_id"] in unit["right"]
        outcome = "right" if ok else "wrong"
    scan_hits = [c["drawing_id"] for c, _ in paired if c["drawing_id"].startswith("scan:")]
    return {"outcome": outcome, "picked": picked, "paired": len(paired), "scan_hits": scan_hits}


def bars(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The pre-registered bar on one condition's rows."""
    pos = [r for r in rows if not r["negative"]]
    neg = [r for r in rows if r["negative"]]
    wrong = sum(r["outcome"] == "wrong" for r in rows)
    right_pos = sum(r["outcome"] == "right" for r in pos)
    refused_neg = sum(r["outcome"] == "right" for r in neg)
    scans = sum(len(r["scan_hits"]) for r in rows)
    return {
        "counts": dict(
            Counter(
                f"{'negative' if r['negative'] else 'positive'} {r['outcome']}" for r in rows
            ).most_common()
        ),
        "1 wrong <= 2%": (wrong, len(rows), wrong <= 0.02 * len(rows)),
        "2 right on positives >= 80%": (right_pos, len(pos), right_pos >= 0.8 * len(pos)),
        "3 negatives refused >= 95%": (refused_neg, len(neg), refused_neg >= 0.95 * len(neg)),
        "4 no scan paired": (scans, 0, scans == 0),
    }


def _self_check() -> None:
    plan = {"drawing_id": "p", "disciplines": ()}
    a = {"drawing_id": "a", "storey": "E00", "disciplines": ("heating",)}
    b = {"drawing_id": "b", "storey": "E01", "disciplines": ("heating",)}
    s = {"drawing_id": "scan:x", "storey": None, "disciplines": ("heating",)}
    us = units({"p": plan}, {"p": "E00"}, [a, b], [s])
    assert [(u["negative"], [c["drawing_id"] for c in u["candidates"]]) for u in us] == [
        (False, ["a", "b", "scan:x"]),
        (True, ["b", "scan:x"]),
    ]
    refusal = lambda r: isinstance(r, str)  # noqa: E731
    assert score(us[0], ["ok", "no", "no"], refusal)["outcome"] == "refused"  # strs only
    assert score(us[0], [object(), "no", "no"], refusal)["outcome"] == "right"
    assert score(us[0], ["no", object(), "no"], refusal)["outcome"] == "wrong"
    assert score(us[1], ["no", "no"], refusal)["outcome"] == "right"
    hit = score(us[1], ["no", object()], refusal)
    assert hit["outcome"] == "wrong" and hit["scan_hits"] == ["scan:x"]


def main() -> None:
    _self_check()
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", type=Path, required=True)
    ap.add_argument("--pictures", type=Path, required=True)
    ap.add_argument("--scans", type=Path, required=True)
    ap.add_argument("--floors", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    from app.core.services.pairing import pair  # W1 (pics/pairing)

    from app.core.services.picture_follow import Sheet

    floors = json.loads(args.floors.read_text())
    models = {f.stem.split(".")[0]: json.loads(f.read_text()) for f in args.plans.glob("*.json")}
    truths = [json.loads(f.read_text()) for f in sorted(args.pictures.glob("*.json"))]
    scan_list = json.loads((args.scans / "files.json").read_text())
    titles = {d["key"]: d["title"] for d in scan_list if "key" in d}
    keys = sorted(p.stem for p in (args.scans / "png").glob("*.png"))
    plan_file = {
        k: m["file"] if isinstance(m["file"], str) else m["file"]["path"] for k, m in models.items()
    }

    report: dict[str, Any] = {}
    for cond, names, storey_from in (
        ("product: P0, names kept", True, None),
        ("P0, names hidden", False, None),
        ("P1 (plan storey = truth floor), names kept", True, "truth"),
    ):
        rows = []
        for key, model in models.items():
            plan = plan_sheet(model, key, names)
            if storey_from == "truth":
                plan["storey"] = floors[plan_file[key]]
            pics = [picture_sheet(t, names) for t in truths]
            scans = [scan_sheet(k, titles.get(k, ""), plan["size_m"], names) for k in keys]
            for u in units({key: plan}, {key: floors[plan_file[key]]}, pics, scans):
                results = pair(Sheet(**u["plan_sheet"]), [Sheet(**c) for c in u["candidates"]])
                row = {k: u[k] for k in ("plan", "floor", "discipline", "negative", "right")}
                row |= score(u, results, lambda r: isinstance(r, str))
                row["reasons"] = [r if isinstance(r, str) else r.reason for r in results]
                rows.append(row)
        report[cond] = {"bars": bars(rows), "rows": rows}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "pairing_eval.json").write_text(json.dumps(report, indent=1, default=str))
    for cond, r in report.items():
        print(cond, json.dumps(r["bars"], default=str))


if __name__ == "__main__":
    main()
