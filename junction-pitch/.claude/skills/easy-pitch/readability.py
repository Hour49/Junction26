#!/usr/bin/env python3
"""Rough readability check for spoken pitch text. Standard library only.

Usage:
  python3 readability.py FILE          # checks spoken lines only (lines starting with ">")
  python3 readability.py FILE --all    # checks every non-heading, non-table line
  python3 readability.py - < text.txt  # read from stdin (all lines)

Reports, per "## " section and overall:
  - average sentence length (words)          target <= 12
  - long-word share (3+ syllables)           target <= 10 %
  - Flesch-Kincaid grade (rough)             target 6-8
Then lists long sentences (> 15 words) and jargon from plain-words.md.
Numbers, [DEMO]/[0:10] cues, (notes in round brackets) and markdown are ignored.
Spoken lines may also be list items: "1. > ..." or "- > ...". Syllables are a heuristic,
so treat the grade as +/- 1.
"""
import os
import re
import sys

TARGET_SENT = 12
TARGET_LONG = 10.0
TARGET_GRADE = (6, 8)
LONG_SENT = 15

HERE = os.path.dirname(os.path.abspath(__file__))


def syllables(word):
    w = word.lower().strip("'")
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def load_jargon():
    path = os.path.join(HERE, "plain-words.md")
    terms = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
                if m and not set(m.group(1)) <= set("-: ") and m.group(1).lower() != "jargon":
                    terms.append((m.group(1).lower(), m.group(2)))
    except OSError:
        pass
    return terms


def clean(line):
    line = re.sub(r"^\s*(?:[-*]|\d+[.)])?\s*>\s?", "", line)  # "> ", "1. > ", "- > "
    line = re.sub(r"\([^)]*\)", " ", line)            # (notes in brackets are not spoken)
    line = re.sub(r"\[[^\]]*\]", " ", line)          # [DEMO], [0:10], [link]
    line = re.sub(r"[*_`#]", "", line)
    return line.strip()


def collect(lines, all_lines):
    """Return list of (section, text)."""
    section, out = "(top)", []
    for raw in lines:
        if raw.startswith("## "):
            section = raw[3:].strip()
            continue
        if raw.startswith("#") or raw.startswith("- Date") or raw.startswith("- Based on"):
            continue
        if raw.lstrip().startswith("|"):  # table: keep only cells that start with ">"
            for cell in raw.strip().strip("|").split("|"):
                if cell.strip().startswith(">"):
                    text = clean(cell.strip())
                    if text:
                        out.append((section, text))
            continue
        if not all_lines and not re.match(r"^\s*(?:[-*]|\d+[.)])?\s*>", raw):
            continue
        text = clean(raw)
        if text:
            out.append((section, text))
    return out


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\s+[—–]\s+(?=[A-Z])", text)
    return [p for p in parts if re.search(r"[A-Za-z]", p)]


def words(sentence):
    return re.findall(r"[A-Za-z][A-Za-z'’-]*", sentence)


def stats(texts):
    sents = [s for t in texts for s in sentences(t)]
    ws = [w for s in sents for w in words(s)]
    if not sents or not ws:
        return None
    syl = [syllables(w) for w in ws]
    avg = len(ws) / len(sents)
    long_share = 100.0 * sum(1 for n in syl if n >= 3) / len(ws)
    grade = 0.39 * avg + 11.8 * (sum(syl) / len(ws)) - 15.59
    return {"sentences": len(sents), "words": len(ws), "avg": avg, "long": long_share, "grade": grade, "sents": sents}


def verdict(st):
    ok = st["avg"] <= TARGET_SENT and st["long"] <= TARGET_LONG and st["grade"] <= TARGET_GRADE[1]
    return "OK" if ok else "SIMPLIFY"


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    all_lines = "--all" in args or args[0] == "-"
    src = args[0]
    lines = sys.stdin.read().splitlines() if src == "-" else open(src, encoding="utf-8").read().splitlines()
    items = collect(lines, all_lines)
    if not items:
        print("No spoken lines found. Spoken lines must start with '>' (or use --all).")
        return 1

    order, by_sec = [], {}
    for sec, t in items:
        if sec not in by_sec:
            order.append(sec)
            by_sec[sec] = []
        by_sec[sec].append(t)

    print(f"Targets: avg sentence <= {TARGET_SENT} words, long words <= {TARGET_LONG:.0f}%, grade <= {TARGET_GRADE[1]} (aim {TARGET_GRADE[0]}-{TARGET_GRADE[1]}; lower is fine for speech)\n")
    print(f"{'section':42} {'sent':>4} {'words':>5} {'avg':>5} {'long%':>6} {'grade':>5}  verdict")
    for sec in order:
        st = stats(by_sec[sec])
        if st:
            print(f"{sec[:42]:42} {st['sentences']:>4} {st['words']:>5} {st['avg']:>5.1f} {st['long']:>6.1f} {st['grade']:>5.1f}  {verdict(st)}")
    total = stats([t for _, t in items])
    print(f"{'OVERALL':42} {total['sentences']:>4} {total['words']:>5} {total['avg']:>5.1f} {total['long']:>6.1f} {total['grade']:>5.1f}  {verdict(total)}")

    longs = [s for s in total["sents"] if len(words(s)) > LONG_SENT]
    if longs:
        print(f"\nLong sentences (> {LONG_SENT} words): split them")
        for s in longs:
            print(f"  [{len(words(s))}] {s}")

    hard = sorted({w.lower() for s in total["sents"] for w in words(s) if syllables(w) >= 4})
    if hard:
        print("\nVery long words (4+ syllables): swap if a shorter word works")
        print("  " + ", ".join(hard))

    text = " ".join(t for _, t in items).lower()
    hits = [(j, p) for j, p in load_jargon() if re.search(r"(?<![a-z])" + re.escape(j) + r"(?![a-z])", text)]
    if hits:
        print("\nJargon found (from plain-words.md): replace it")
        for j, p in hits:
            print(f"  {j} -> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
