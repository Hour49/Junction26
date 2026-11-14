"""Score chat runs (run.py's JSONL) side by side, record a row, check a pre-registered A/B line.

  python3 -m chat.score <runs>/a.jsonl <runs>/b.jsonl --chats <env>/data/projects [--turns]
  python3 -m chat.score <run> --chats ... --record <name> --commit <sha> --note "..."
  python3 -m chat.score <base run> <new run> --chats ... --ab "steps shown" [--only ...]

Per turn: right (truth given: the value the judge sees equals the truth or lies in its range;
'refuse': the turn refused), answered (not a refusal), on topic (the text names the subject),
level kept (asked if it is sure, the reply claims no other level than the card it was asked
about), level changed (that turn brings a card at another level),
grounded (every number in the text is backed by a value of the chat's tool results, the reply or the
user's message: a whole number exactly, a decimal at its places, ids and geometry not counting;
ask mode is grounded by construction), refusal offers, steps shown, view (the turn puts a plan on
screen), latency, USD. --ab passes when right, grounded and (when both runs have such turns)
level kept do not drop and the named metric goes up (latency and USD: down); it refuses (exit 2)
two runs that do not cover the same turns.
"""

import argparse
import datetime as dt
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Any

Json = dict[str, Any]
Score = dict[str, Any]  # a fraction is [k, n]; the rest are numbers
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
CITE = re.compile(r"\[\d+\]|\b[A-Za-z]+_?\d+\b")
REFUSED = {"refusal", "dont_know"}
LOWER_IS_BETTER = {"http errors", "latency p50 s", "latency max s", "USD/turn", "USD total"}
RESULTS = Path(__file__).resolve().parents[1] / "results" / "chat"


def num(s: str) -> Decimal | None:
    try:
        return Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None


def shown_value(r: Json) -> float | None:
    """The value the judge reads: the card's total, else the first number in the text."""
    if r.get("value") is not None:
        return float(r["value"])
    found = NUMBER.findall(CITE.sub(" ", r.get("text", "")))
    return float(found[0].replace(",", ".")) if found else None


def right(r: Json) -> bool | None:
    truth = r["truth"]
    if truth is None:
        return None
    if truth == "refuse":
        return r["kind"] in REFUSED
    if r["kind"] in REFUSED:
        return False
    v = shown_value(r)
    if v is None:
        return False
    if isinstance(truth, list):
        return truth[0] <= v <= truth[1]
    return v == truth


# Fields that are not facts a reply may quote (ids, geometry, timings, cost, enums): nothing under
# them counts, not their numbers, the numbers in their strings or their lists' lengths.
NOT_VALUES = {"id", "ids", "n", "ev", "turn", "page", "box", "bbox", "polygon", "quad", "points",
              "rotated", "deskew_deg", "exif", "score", "cost_usd",
              "latency_s", "usd", "url", "colour", "color", "unit", "kind", "status",
              "model"}  # fmt: skip
# a number standing alone in a string ("Bagno 1.01", "631/2024"), not digits inside a word or id
STANDALONE = re.compile(r"(?<![A-Za-z0-9_])\d+(?:[.,]\d+)?(?![A-Za-z0-9_])")
PAGE = re.compile(r"\bpages?\s+\d+|\d+-page\b", re.IGNORECASE)


def _quotable(key: str | None) -> bool:
    return key not in NOT_VALUES and not (key or "").endswith(("_id", "_ids", "_usd", "_s"))


def _known(found: Any, key: str | None, values: set[Decimal], tokens: set[str]) -> None:
    """The quotable numbers in a tool result or reply: numeric values, the length of a list of
    things (a reply may count the parts or rooms it got), and numbers standing alone in strings
    (labels, file names, clause numbers), which match only as written; nothing under NOT_VALUES."""
    if not _quotable(key):
        return
    if isinstance(found, dict):
        for k, v in found.items():  # pyright: ignore[reportUnknownVariableType]
            _known(v, str(k), values, tokens)  # pyright: ignore[reportUnknownArgumentType]
    elif isinstance(found, list):
        if found and all(isinstance(v, dict) for v in found):  # pyright: ignore[reportUnknownVariableType]
            values.add(Decimal(len(found)))  # pyright: ignore[reportUnknownArgumentType]
        for v in found:  # pyright: ignore[reportUnknownVariableType]
            _known(v, key, values, tokens)
    elif isinstance(found, str):
        tokens.update(STANDALONE.findall(found))
    elif isinstance(found, int | float) and not isinstance(found, bool):
        values.add(Decimal(str(found)))


def embedded(text: str) -> list[Any]:
    """The JSON objects inside a message's text: a tool message is one; the server may also add a
    tool's result to the user's message ("review_answer result (...): {...}")."""
    found: list[Any] = []
    decoder = json.JSONDecoder()
    at = text.find("{")
    while at != -1:
        try:
            obj, end = decoder.raw_decode(text, at)
        except ValueError:
            at = text.find("{", at + 1)
            continue
        found.append(obj)
        at = text.find("{", end)
    return found


def grounded(r: Json, chats: list[Path]) -> bool:
    """Every number in the text is backed: a whole number by an equal value (5.8 does not back
    "6"), a decimal by a value that rounds to it at the text's places, either by the same token
    in a string; values from the reply, the user's message and the chat's tool results (its
    stored file under one of `chats`, the env's projects dirs), ids, geometry and timings left
    out (NOT_VALUES). Page numbers in the text ("page 1", "1-page") are not checked."""
    if r["mode"] == "ask":
        return True
    raw = dict(r.get("raw") or {})
    text = raw.pop("text", "") or r.get("text", "")
    stored = [f for d in chats for f in d.glob(f"*/chats/{raw.get('chat_id')}.json")]
    chat: Json = json.loads(stored[0].read_text()) if stored else {}
    added = [
        obj
        for m in chat.get("messages", [])
        if m.get("role") in ("user", "tool") and isinstance(m.get("content"), str)
        for obj in embedded(m["content"])
    ]
    values: set[Decimal] = set()
    tokens: set[str] = set(NUMBER.findall(r["msg"]))
    for found in [
        raw,
        *chat.get("results", []),
        *added,
    ]:  # not the lengths of these wrappers: no reply counts them
        _known(found, None, values, tokens)
    for n in STANDALONE.findall(PAGE.sub(" ", CITE.sub(" ", text))):
        d = num(n)
        if d is None:
            return False
        if n in tokens:
            continue
        exponent = d.as_tuple().exponent
        places = -exponent if isinstance(exponent, int) and exponent < 0 else 0
        if not any(round(v, places) == d if places else v == d for v in values):
            return False
    return True


# the user asks whether the chat is sure of its answer, not any message with "sure" in it
SURE_ASK = re.compile(
    r"\b(are|r)\s+(you|u)\s+(really\s+|quite\s+)?(sure|certain|confident)\b"
    r"|\bhow\s+(sure|certain|confident)\b|\b(sure|certain)\s+about\b",
    re.IGNORECASE,
)
LEVELS = ("low", "medium", "high")
BELOW_HIGH = frozenset({"low", "medium"})
# a level named as the answer's confidence ("medium confidence", "confidence is low"), unless denied
NAMED = re.compile(
    r"(?<!not )(?<!no )\b(high|medium|low)[- ](?:confidence|certainty)\b"
    r"|\b(?:confidence|certainty)\s+(?:is|was|stays|remains|of|:)?\s*(high|medium|low)\b",
    re.IGNORECASE,
)
CERTAIN = re.compile(r"^\W*yes\b|(?<!not )\b(i am|i'm) (sure|certain|confident)\b", re.IGNORECASE)
UNSURE = re.compile(
    r"\b(not (sure|certain|confident)|can't say|cannot say|can't be sure|cannot be sure)\b",
    re.IGNORECASE,
)


def claimed(text: str) -> set[str]:
    """The levels a reply claims for the answer: those it names as its confidence; else "yes" or
    "I'm sure" claims high and "not sure" claims below high; else none."""
    named = {(m[1] or m[2]).lower() for m in NAMED.finditer(text)}
    if named:
        return named
    if UNSURE.search(text):
        return set(BELOW_HIGH)
    return {"high"} if CERTAIN.search(text) else set()


def level_kept(rows: list[Json]) -> list[tuple[bool, bool]]:
    """Per turn that asks whether the chat is sure, after an answer card with a level: (kept,
    changed). kept: every level the reply claims (`claimed`) is the level of the card before this
    turn, the answer the user asks about (claiming none keeps it; "not sure" keeps low or medium
    and drops high). changed: the turn brings a new card at another level."""
    out: list[tuple[bool, bool]] = []
    level: dict[str, str] = {}
    for r in sorted(rows, key=lambda r: (r["script"], r["turn"])):
        before = level.get(r["script"])
        now = str(r["level"]).lower() if r.get("level") else None
        if now:
            level[r["script"]] = now
        if not SURE_ASK.search(r["msg"]) or before not in LEVELS:
            continue
        said = claimed(r.get("text") or "")
        kept = before in said if said == BELOW_HIGH else said <= {before}
        out.append((kept, now is not None and now != before))
    return out


def score(rows: list[Json], chats: list[Path]) -> Score:
    truth = [r for r in rows if r["truth"] is not None]
    firsts = [r for r in rows if r["turn"] == 1]
    follow = [r for r in rows if r["turn"] > 1]
    refusals = [r for r in rows if r["kind"] in REFUSED]
    lat = [r["latency_s"] for r in rows]
    usd = [r.get("cost_usd") or 0.0 for r in rows]
    sure = level_kept(rows)

    def on(r: Json) -> bool:
        return any(m.lower() in (r.get("text") or "").lower() for m in r["mentions"])

    return {
        "turns": len(rows),
        "right": [sum(bool(right(r)) for r in truth), len(truth)],
        "answered 1st": [sum(r["kind"] not in REFUSED for r in firsts), len(firsts)],
        "answered follow-up": [sum(r["kind"] not in REFUSED for r in follow), len(follow)],
        "on topic": [sum(on(r) for r in rows), len(rows)],
        "grounded": [sum(grounded(r, chats) for r in rows), len(rows)],
        "refusal offers": [sum((r.get("options") or 0) > 0 for r in refusals), len(refusals)],
        "steps shown": [sum((r.get("steps") or 0) > 0 for r in rows), len(rows)],
        "view shown": [sum(bool(r.get("view")) for r in rows), len(rows)],
        "level kept": [sum(k for k, _ in sure), len(sure)],
        "level changed": [sum(c for _, c in sure), len(sure)],
        "http errors": sum(r["status"] != 200 for r in rows),
        "latency p50 s": round(median(lat), 2) if lat else 0.0,
        "latency max s": round(max(lat), 2) if lat else 0.0,
        "USD/turn": round(sum(usd) / len(usd), 4) if usd else 0.0,
        "USD total": round(sum(usd), 4),
    }


def _value(v: Any) -> float:
    """A fraction's share (k/n), else the number."""
    if isinstance(v, list):
        k, n = v
        return k / n if n else 0.0
    return float(v)


def ab(base: Score, new: Score, metric: str) -> tuple[bool, list[str]]:
    """The pre-registered line: right and grounded do not drop, `metric` improves."""
    lines: list[str] = []
    ok = True
    # level kept guards too when both runs asked whether the chat is sure
    measured = base.get("level kept", [0, 0])[1] and new.get("level kept", [0, 0])[1]
    for guard in ("right", "grounded", *(["level kept"] if measured else [])):
        held = new[guard][0] >= base[guard][0] and _value(new[guard]) >= _value(base[guard])
        lines.append(
            f"{guard}: {_show(base[guard])} -> {_show(new[guard])} {'ok' if held else 'DROP'}"
        )
        ok = ok and held
    lower = metric in LOWER_IS_BETTER
    b, n = _value(base[metric]), _value(new[metric])
    better = n < b if lower else n > b
    lines.append(f"{metric}: {_show(base[metric])} -> {_show(new[metric])} "
                 f"{'better' if better else 'NOT better'}")  # fmt: skip
    return ok and better, lines


def turns_differ(base: list[Json], new: list[Json]) -> list[str]:
    """Why two runs cannot be compared turn for turn: turns one has and the other lacks, or a
    turn repeated (a run appended twice); empty when they cover the same turns once each."""
    why: list[str] = []
    for name, rows in (("base", base), ("new", new)):
        keys = [(r["script"], r["turn"], r["msg"]) for r in rows]
        if len(set(keys)) != len(keys):
            why.append(f"{name} has {len(keys) - len(set(keys))} repeated turns")
    a = {(r["script"], r["turn"], r["msg"]) for r in base}
    b = {(r["script"], r["turn"], r["msg"]) for r in new}
    if a - b:
        why.append(f"{len(a - b)} turns only in base, e.g. {sorted(a - b)[0][:2]}")
    if b - a:
        why.append(f"{len(b - a)} turns only in new, e.g. {sorted(b - a)[0][:2]}")
    return why


def _show(v: Any) -> str:
    return f"{v[0]}/{v[1]}" if isinstance(v, list) else str(v)


def load(path: Path, only: set[str]) -> list[Json]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [r for r in rows if not only or r["script"] in only]


def record(name: str, commit: str, note: str, run: Path, rows: list[Json], got: Score) -> Path:
    """A committed row: numbers only (the turns carry partner-drawing text and stay in data/)."""
    now = dt.datetime.now().astimezone()
    models = sorted({str(r.get("model")) for r in rows if r.get("model")})
    row = {
        "recorded_at": now.isoformat(timespec="seconds"),
        "name": name,
        "commit": commit,
        "note": note,
        "run_file": run.name,
        "turns_sha256": hashlib.sha256(
            json.dumps([[r["script"], r["turn"], r["msg"]] for r in rows]).encode()
        ).hexdigest(),
        "models": models,
        "score": got,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{now:%Y%m%d-%H%M%S}-{name}.json"
    out.write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--turns", action="store_true", help="print each turn's verdicts")
    ap.add_argument("--only", default="", help="script ids, comma separated")
    ap.add_argument("--chats", nargs="*", type=Path, default=[], help="the envs' projects dirs")
    ap.add_argument("--record", metavar="NAME", help="write eval/results/chat/<time>-NAME.json")
    ap.add_argument("--commit", default="", help="the build the run tested (with --record)")
    ap.add_argument("--note", default="")
    ap.add_argument("--ab", metavar="METRIC", help="base run, new run: the pre-registered check")
    args = ap.parse_args()
    only = {s for s in args.only.split(",") if s}
    table: dict[str, Score] = {}
    loaded: dict[str, list[Json]] = {}
    for path in args.runs:
        rows = load(path, only)
        loaded[path.stem] = rows
        table[path.stem] = score(rows, args.chats)
        if args.turns:
            for r in rows:
                print(f"{path.stem:8} {r['script']:14} t{r['turn']} right={right(r)!s:5} "
                      f"grounded={grounded(r, args.chats)!s:5} {r['kind']!s:9} "
                      f"{(r.get('text') or '')[:100]!r}")  # fmt: skip
    keys = list(next(iter(table.values())))
    print(f"{'':22}" + "".join(f"{name[:16]:>17}" for name in table))
    for k in keys:
        print(f"{k:22}" + "".join(f"{_show(table[name][k]):>17}" for name in table))
    if args.record:
        if len(args.runs) != 1 or not args.commit:
            ap.error("--record takes one run and --commit")
        path = args.runs[0]
        out = record(args.record, args.commit, args.note, path, loaded[path.stem], table[path.stem])
        print(f"recorded {out}")
    if args.ab:
        if len(args.runs) != 2:
            ap.error("--ab takes two runs: base, new")
        why = turns_differ(*(loaded[p.stem] for p in args.runs))
        if why:
            print("A/B REFUSED: the runs do not cover the same turns (use --only):", "; ".join(why))
            raise SystemExit(2)
        base, new = (table[p.stem] for p in args.runs)
        ok, lines = ab(base, new, args.ab)
        print("\n".join(lines))
        print(f"A/B {'PASS' if ok else 'FAIL'}")
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
