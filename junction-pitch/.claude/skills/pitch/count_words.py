#!/usr/bin/env python3
"""Count spoken words per timed section of a /pitch script and warn when it runs over time.

Usage: python3 count_words.py <script.md> [--wpm 140]

Format it reads (see templates.md):
  ## HOOK [0:00-0:15] budget 30w      <- timed section; "budget Nw" is optional
  Spoken text on plain lines. [CLICK] [DEMO] [PAUSE] are not counted.
  > Stage notes start with ">" and are not counted.
  ## Notes                            <- a heading without [m:ss-m:ss] stops counting
Lines starting with "|", "-" or "<!--" are never counted.
"""
import re
import sys

CUE = re.compile(r"\[(CLICK|DEMO|PAUSE)\]")
TIMED = re.compile(r"^##\s+(.*?)\s*\[(\d+):(\d\d)\s*[-–]\s*(\d+):(\d\d)\]\s*(?:budget\s+(\d+)\s*w)?", re.I)
SAFE_WPM_SLACK = 0.9  # leave 10% of the time for clicks, laughs, applause (pitching.md §1)
HARD_WPM = 150        # absolute ceiling: about the slowest 2025 finalists (145-200 wpm)


def parse(lines):
    sections, cur = [], None
    for line in lines:
        s = line.strip()
        if s.startswith("#"):
            m = TIMED.match(s)
            if m:
                name, m1, s1, m2, s2, budget = m.groups()
                start, end = int(m1) * 60 + int(s1), int(m2) * 60 + int(s2)
                cur = {"name": name, "start": start, "end": end,
                       "budget": int(budget) if budget else None, "words": 0}
                sections.append(cur)
            elif s.startswith("## "):
                cur = None
            continue
        if cur is None or not s or s.startswith((">", "|", "-", "<!--")):
            continue
        cur["words"] += len(CUE.sub(" ", s).split())
    return sections


def fmt(sec):
    return f"{sec // 60}:{sec % 60:02d}"


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    wpm = 140
    if "--wpm" in argv:
        wpm = int(argv[argv.index("--wpm") + 1])
    with open(argv[0], encoding="utf-8") as f:
        lines = f.readlines()
    sections = parse(lines)
    todos = sum(line.count("<TODO") for line in lines)
    if not sections:
        print("ERROR: no timed sections found (headings like '## HOOK [0:00-0:15]').")
        return 2
    status = 0
    print(f"{'section':32} {'time':>11} {'words':>6} {'budget':>7}")
    for s in sections:
        budget = s["budget"] or round((s["end"] - s["start"]) * wpm / 60)
        flag = ""
        if s["words"] > budget * 1.1:
            flag, status = "  OVER", 1
        print(f"{s['name'][:32]:32} {fmt(s['start']):>5}-{fmt(s['end']):<5} {s['words']:>6} {budget:>7}{flag}")
    total = sum(s["words"] for s in sections)
    length = sections[-1]["end"]
    safe = round(length * wpm / 60 * SAFE_WPM_SLACK)
    hard = round(length * HARD_WPM / 60)
    secs = round(total / wpm * 60)
    print(f"\nTOTAL {total} words = about {fmt(secs)} at {wpm} wpm. Slot {fmt(length)}. "
          f"Target <= {safe} (10% slack), hard limit {hard}.")
    if total > hard:
        print(f"WARNING: OVER TIME. Cut at least {total - safe} words.")
        status = 1
    elif total > safe:
        print(f"WARNING: no slack left. Cut {total - safe} words to be safe.")
        status = 1
    elif total < safe * 0.7:
        print(f"OK, but short: room for about {safe - total} more words (fill TODOs or add content).")
    else:
        print("OK: fits the time with slack.")
    if todos:
        print(f"NOTE: {todos} <TODO> placeholder(s) left; the count changes when they are filled.")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
