#!/usr/bin/env python3
"""Build the HTML slideshow mock-up from a deck outline (Python 3 stdlib only).

Usage:
  python3 build_mock.py OUTLINE.md [--out FILE.html] [--google-fonts] [--strict]
  python3 build_mock.py --next DECK_DIR      # print the next free outline file name

Default output: <outline dir>/mock/index<suffix>.html, where outline-v2.md gives
index-v2.html. Outline format: outline-format.md in this folder.
Prints warnings (word limits, timing, missing sources, [[...]] placeholders).
--strict exits 1 when there are warnings.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WPS = 140 / 60  # speaking speed, words per second (playbook: 130-140 wpm)
CUTS = {"both", "5-min", "backup"}
# One "number" = 1,062 · 17:00 · 3 in 10 · 4-5 · €2k · 30% (a ratio or range counts once)
NUM_RE = re.compile(r"[€$£]?\d+(?:[.,:]\d+)*(?:\s?(?:in|of|out of|/|-|–)\s?\d+(?:[.,:]\d+)*)?"
                    r"(?:\s?(?:%|(?:x|k|m|bn|h|min|s)\b))?", re.I)


def parse(text):
    """Return (meta dict, list of slide dicts)."""
    meta, slides, cur, key = {"title": "Deck"}, [], None, None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("# ") and not slides and cur is None:
            meta["title"] = re.sub(r"^Deck outline:\s*", "", line[2:]).strip()
            continue
        m = re.match(r"^##\s+(Slide|Backup)\s+([\w.]+)\s*:\s*(.+)$", line)
        if m:
            cur = {"kind": m.group(1).lower(), "id": m.group(2), "title": m.group(3).strip(),
                   "fields": {}}
            slides.append(cur)
            key = None
            continue
        if line.startswith("## "):  # other section (e.g. "## Checks"): stop collecting
            cur, key = None, None
            continue
        fm = re.match(r"^-\s+([A-Za-z0-9 -]+?):\s*(.*)$", line)
        if fm and (cur is None or not raw.startswith(" ")):
            k, v = fm.group(1).strip().lower(), fm.group(2).strip()
            if cur is None:
                meta[k] = v
            else:
                cur["fields"][k] = v
                key = k
            continue
        if cur is not None and key and line.strip():  # continuation line
            prev = cur["fields"].get(key, "")
            cur["fields"][key] = (prev + "\n" + line.strip()).strip()
    return meta, slides


def seconds(field):
    """'12 / 15' -> (12, 15); '- / 30' -> (0, 30)."""
    parts = [p.strip() for p in (field or "").split("/")]
    vals = []
    for p in parts[:2]:
        vals.append(int(p) if p.isdigit() else 0)
    while len(vals) < 2:
        vals.append(vals[0] if vals else 0)
    return vals[0], vals[1]


def build(meta, slides):
    """Normalise slides and collect warnings."""
    warns, out = [], []
    tot_core = tot_long = 0
    for s in slides:
        f = s["fields"]
        label = f"{s['kind'].title()} {s['id']} ({s['title']})"
        cut = "backup" if s["kind"] == "backup" else (f.get("cut") or "both").lower()
        if cut not in CUTS:
            warns.append(f"{label}: Cut '{cut}' unknown, use both / 5-min / backup")
            cut = "both"
        core, long_ = seconds(f.get("seconds"))
        if cut == "5-min":
            core = 0
        if cut == "backup":
            core = long_ = 0
        tot_core += core
        tot_long += long_
        on = f.get("on screen", "")
        words = len(re.sub(r"\[\[.*?\]\]", "X", on).split())
        if words > 12:
            warns.append(f"{label}: {words} words on screen (max 12)")
        shown = re.sub(r"\[\[.*?\]\]", "", on + " " + f.get("number", ""))
        nums = set(n.group(0).strip() for n in NUM_RE.finditer(shown))
        if len(nums) > 1 and cut != "backup":
            warns.append(f"{label}: more than one number on screen {sorted(nums)}")
        if f.get("number") and not f.get("source"):
            warns.append(f"{label}: number without Source line")
        nw = len(f.get("notes", "").split())
        xw = len(f.get("extra for 5-min", "").split())
        if core and nw > core * WPS * 1.1:
            warns.append(f"{label}: notes {nw} words, too long for {core} s (~{int(core * WPS)} words)")
        if long_ and nw + xw > long_ * WPS * 1.1:
            warns.append(f"{label}: notes+extra {nw + xw} words, too long for {long_} s")
        todo = sum(len(re.findall(r"\[\[.*?\]\]", v)) for v in f.values())
        if todo:
            warns.append(f"{label}: {todo} [[placeholder]] to fill")
        out.append({
            "id": s["id"], "kind": s["kind"], "title": s["title"], "cut": cut,
            "core": core, "long": long_,
            "layout": (f.get("layout") or "statement").lower(),
            "on": on, "number": f.get("number", ""), "visual": f.get("visual", ""),
            "image": f.get("image", ""), "video": f.get("video", ""),
            "fallback": f.get("fallback", ""), "badge": f.get("badge", ""),
            "source": f.get("source", ""), "team": f.get("team", ""),
            "notes": f.get("notes", ""), "extra": f.get("extra for 5-min", ""),
        })
    layouts = {s["layout"] for s in out}
    for need in ("demo", "team"):
        if need not in layouts:
            warns.append(f"deck: no slide with Layout: {need}")
    if abs(tot_core - 180) > 5:
        warns.append(f"deck: 3-min cut totals {tot_core} s (target 180)")
    has_long = any(s["cut"] == "5-min" or s["extra"] for s in out)
    if has_long and abs(tot_long - 300) > 5:
        warns.append(f"deck: 5-min cut totals {tot_long} s (target 300)")
    return out, warns, tot_core, tot_long


def default_out(outline):
    m = re.match(r"outline(-v\d+)?$", outline.stem)
    suffix = (m.group(1) or "") if m else "-" + outline.stem
    return outline.parent / "mock" / f"index{suffix}.html"


def next_version(deck_dir):
    deck_dir = Path(deck_dir)
    if not (deck_dir / "outline.md").exists():
        return deck_dir / "outline.md"
    n = 2
    while (deck_dir / f"outline-v{n}.md").exists():
        n += 1
    return deck_dir / f"outline-v{n}.md"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outline", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--next", metavar="DECK_DIR")
    ap.add_argument("--google-fonts", action="store_true", help="load Michroma/Space Mono (needs internet)")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    if a.next:
        print(next_version(a.next))
        return 0
    if not a.outline:
        ap.error("give an outline file or --next DECK_DIR")
    src = Path(a.outline)
    meta, slides = parse(src.read_text(encoding="utf-8"))
    if not slides:
        print(f"ERROR: no '## Slide N: Title' sections found in {src}", file=sys.stderr)
        return 1
    data, warns, tc, tl = build(meta, slides)
    out = Path(a.out) if a.out else default_out(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "assets").mkdir(exist_ok=True)
    payload = json.dumps({"meta": meta, "slides": data, "source": src.name}, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")  # keep </script> out of the JSON
    fonts = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
             'family=Michroma&family=Space+Mono:wght@400;700&display=swap">') if a.google_fonts else ""
    page = (HERE / "mock-template.html").read_text(encoding="utf-8")
    page = (page.replace("{{TITLE}}", html.escape(meta.get("title", "Deck")))
                .replace("{{FONTS}}", fonts)
                .replace("{{DATA}}", payload))
    out.write_text(page, encoding="utf-8")
    long_txt = f", 5-min cut {tl} s" if any(s["cut"] == "5-min" or s["extra"] for s in data) else ""
    print(f"wrote {out}  ({len(data)} slides; 3-min cut {tc} s{long_txt})")
    for w in warns:
        print("WARN", w)
    return 1 if (a.strict and warns) else 0


if __name__ == "__main__":
    sys.exit(main())
