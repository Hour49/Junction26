#!/usr/bin/env python3
"""Deck outline -> .pptx for Google Slides, and a safe merge for re-runs.

Needs python-pptx (not stdlib). Use the deck venv:
  python3 -m venv ~/.cache/deck-venv && ~/.cache/deck-venv/bin/pip install python-pptx   # once
  ~/.cache/deck-venv/bin/python build_slides.py ...

Commands:
  build OUTLINE.md --out DECK.pptx [--assets DIR]
      First run. A 16:9 .pptx, one slide per '## Slide' / '## Backup' section, speaker notes.
      Also writes DECK.state.json: the exact text we put in every box (the "last pushed" state).

  merge OUTLINE.md --current CURRENT.pptx --state STATE.json --out NEW.pptx [--assets DIR] [--dry-run]
      Re-run. CURRENT.pptx = the live Google Slides deck exported as .pptx (Drive
      download_file_content). For every slide it compares what is in Slides now with what we
      pushed last time (state) and with the new outline:
        same    nothing changed -> slide left as it is
        update  outline changed, nobody touched the slide -> the changed boxes get the new text
                (formatting of the box is kept)
        human   a person edited the slide -> slide left exactly as they made it; the new outline
                text goes into the speaker notes as "Proposed: ..."
        new     slide in the outline but not in the deck -> added at the end
        extra   slide in the deck we did not make or no longer in the outline -> left alone
      Writes NEW.pptx + NEW.state.json and prints the plan. --dry-run prints the plan only.
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_mock import parse, build as check  # noqa: E402  (same parser + checks as the HTML mock)

from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.dml import MSO_LINE_DASH_STYLE  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR  # noqa: E402
from pptx.util import Inches, Pt, Emu  # noqa: E402

INK, MUTED, ACCENT, NEED = "111111", "666666", "C8102E", "B26B00"
W_IN, H_IN = 13.333, 7.5


def load_outline(path):
    meta, raw = parse(Path(path).read_text(encoding="utf-8"))
    if not raw:
        sys.exit(f"ERROR: no '## Slide N: Title' sections in {path}")
    slides, warns, tc, tl = check(meta, raw)
    return meta, slides, warns, tc, tl


def key(s):
    return f"{s['kind']}-{s['id']}"


def norm(t):
    t = (t or "").replace("\u000b", "\n")
    return re.sub(r"\s+", " ", t).strip().lower()


def screen_text(s):
    """Text boxes on a slide (box name -> text). This is what the state file stores."""
    boxes = {"kicker": s["title"]}
    if s["badge"]:
        boxes["badge"] = s["badge"]
    if s["number"]:
        boxes["number"] = s["number"]
    boxes["on"] = s["on"]
    if s["layout"] == "team" and s["team"]:
        boxes["team"] = "\n".join(p.strip() for p in s["team"].split(";") if p.strip())
    if s["source"]:
        boxes["source"] = "Source: " + s["source"]
    return boxes


def notes_text(s):
    head = ("BACKUP slide" if s["kind"] == "backup" else
            f"Cut: {s['cut']} · Seconds: {s['core']} (3-min) / {s['long']} (5-min)")
    parts = [head, "", s["notes"]]
    if s["extra"]:
        parts += ["", "Extra for 5-min: " + s["extra"]]
    if s["visual"]:
        parts += ["", "Visual: " + s["visual"]]
    media = [x for x in (s["video"], s["fallback"]) if x]
    if media:
        parts += ["Media to insert by hand: " + ", ".join(media)]
    return "\n".join(parts).strip()


# ---------- drawing ----------

def write_runs(tf, text, size, color, bold, align, font="Arial"):
    tf.clear()
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        if align is not None:
            p.alignment = align
        r = p.add_run()
        r.text = line
        if size:
            r.font.size = size
        r.font.bold, r.font.name = bold, font
        r.font.color.rgb = RGBColor.from_string(NEED if "[[" in line else color)


def box(sl, x, y, w, h, text, size, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    write_runs(tf, text, Pt(size), color, bold, align)
    return tb


def media(sl, assets, rel, x, y, w, h):
    f = assets / rel if rel else None
    if f and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif") and f.exists():
        pic = sl.shapes.add_picture(str(f), Inches(x), Inches(y))  # native size, then fit
        k = min(Inches(w) / pic.width, Inches(h) / pic.height)
        pic.width, pic.height = int(pic.width * k), int(pic.height * k)
        pic.left = Inches(x) + (Inches(w) - pic.width) // 2
        pic.top = Inches(y) + (Inches(h) - pic.height) // 2
        return
    r = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.background()
    r.line.color.rgb = RGBColor.from_string("999999")
    r.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    r.text_frame.word_wrap = True
    write_runs(r.text_frame, f"insert: {rel or 'image'}", Pt(14), MUTED, False, PP_ALIGN.CENTER)


# Where each box goes, per layout: (x, y, w, h, size, color, bold, align, anchor)
def geometry(s, b):
    lay = s["layout"]
    big_num = b.get("number") and "[[" not in b["number"]
    g = {"kicker": (0.6, 0.35, 9, 0.5, 14, MUTED, True, PP_ALIGN.LEFT, MSO_ANCHOR.TOP),
         "badge": (9.7, 0.35, 3.0, 0.5, 14, ACCENT, True, PP_ALIGN.RIGHT, MSO_ANCHOR.TOP),
         "source": (0.6, 6.75, 10.8, 0.4, 10, MUTED, False, PP_ALIGN.LEFT, MSO_ANCHOR.TOP)}
    if lay == "team" or lay in ("image", "demo") or (lay == "hook" and s["image"]):
        g["on"] = (0.6, 1.0, 12.1, 1.2, 32, INK, True, PP_ALIGN.LEFT, MSO_ANCHOR.TOP)
        g["team"] = (0.6, 2.5, 12.1, 3.8, 20, INK, False, PP_ALIGN.LEFT, MSO_ANCHOR.TOP)
    elif lay == "close":
        g["on"] = (0.6, 1.5, 8.2, 3.5, 48, INK, True, PP_ALIGN.LEFT, MSO_ANCHOR.MIDDLE)
    elif "number" in b:
        g["number"] = (0.6, 1.2, 12.1, 2.4, 110 if big_num else 28, ACCENT, True, PP_ALIGN.LEFT,
                       MSO_ANCHOR.BOTTOM)
        g["on"] = (0.6, 3.8, 12.1, 1.6, 32, INK, True, PP_ALIGN.LEFT, MSO_ANCHOR.TOP)
    else:
        g["on"] = (0.6, 1.4, 12.1, 4.4, 48 if lay == "hook" else 40, INK, True, PP_ALIGN.LEFT,
                   MSO_ANCHOR.MIDDLE)
    return g


def add_box(sl, s, b, name):
    x, y, w, h, size, color, bold, align, anchor = geometry(s, b)[name]
    return box(sl, x, y, w, h, b[name], size, color, bold, align, anchor)


def draw_slide(prs, s, n, assets):
    sl = prs.slides.add_slide(prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[-1])
    b = screen_text(s)
    for name in b:
        if name in geometry(s, b):
            add_box(sl, s, b, name)
    lay = s["layout"]
    if lay == "close":
        media(sl, assets, s["image"] or "assets/qr.png", 9.3, 1.75, 3.0, 3.0)
    elif lay != "team" and (lay in ("image", "demo") or (lay == "hook" and s["image"])):
        media(sl, assets, s["image"] or s["fallback"] or s["video"], 0.6, 2.4, 12.1, 4.1)
    box(sl, 11.7, 6.75, 1.0, 0.4, str(n), 10, MUTED, align=PP_ALIGN.RIGHT)
    sl.notes_slide.notes_text_frame.text = notes_text(s)
    return sl, b


# ---------- build ----------

def cmd_build(a):
    meta, slides, warns, tc, tl = load_outline(a.outline)
    assets = Path(a.assets) if a.assets else Path(a.outline).parent / "mock"
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W_IN), Inches(H_IN)
    state = {"outline": str(a.outline), "order": [], "slides": {}, "notes": {}}
    for n, s in enumerate(slides, 1):
        _, b = draw_slide(prs, s, n, assets)
        state["order"].append(key(s))
        state["slides"][key(s)] = b
        state["notes"][key(s)] = notes_text(s)
    save(prs, state, a.out)
    print(f"  3-min cut {tc} s, 5-min cut {tl} s")
    for w in warns:
        print("WARN", w)


def save(prs, state, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    sp = out.with_suffix(".state.json")
    sp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out} ({len(prs.slides)} slides) and {sp}")


# ---------- merge ----------

def texts(slide):
    """Text shapes on a slide, without the slide-number box and our dashed 'insert: <file>' boxes."""
    out = []
    for sh in slide.shapes:
        t = sh.text_frame.text.strip() if sh.has_text_frame else ""
        if t and not re.fullmatch(r"\d+", t) and not t.startswith("insert: "):
            out.append(sh)
    return out


def match_slides(prs, state):
    """Map state key -> live slide. By position first, checked by the kicker text; else by kicker."""
    live = list(prs.slides)
    found = {}
    for i, k in enumerate(state["order"]):
        kick = norm(state["slides"][k].get("kicker"))
        cand = [live[i]] if i < len(live) else []
        cand += live
        for sl in cand:
            if sl in found.values():
                continue
            if any(norm(sh.text_frame.text) == kick for sh in texts(sl)):
                found[k] = sl
                break
    return found


def classify(sl, pushed, new):
    live = [norm(sh.text_frame.text) for sh in texts(sl)]
    ours = [norm(v) for v in pushed.values() if norm(v)]
    missing = [b for b, v in pushed.items() if norm(v) and norm(v) not in live]
    added = [t for t in live if t not in ours]
    if missing or added:
        return "human", {"changed_boxes": missing, "added_text": added}
    if {b: norm(v) for b, v in pushed.items()} == {b: norm(v) for b, v in new.items()}:
        return "same", {}
    return "update", {"boxes": sorted(b for b in set(pushed) | set(new) if norm(pushed.get(b)) != norm(new.get(b)))}


def set_text_keep_style(sh, text):
    tf = sh.text_frame
    r0 = next((r for p in tf.paragraphs for r in p.runs), None)
    size = r0.font.size if r0 else None
    bold = r0.font.bold if r0 else False
    font = (r0.font.name if r0 else None) or "Arial"
    try:
        color = str(r0.font.color.rgb) if r0 and r0.font.color and r0.font.color.type else INK
    except AttributeError:
        color = INK
    if color == NEED:
        color = INK
    align = tf.paragraphs[0].alignment
    write_runs(tf, text, size, color, bold, align, font)


def cmd_merge(a):
    meta, slides, warns, tc, tl = load_outline(a.outline)
    assets = Path(a.assets) if a.assets else Path(a.outline).parent / "mock"
    state = json.loads(Path(a.state).read_text(encoding="utf-8"))
    prs = Presentation(a.current)
    found = match_slides(prs, state)
    plan = {}
    new_state = {"outline": str(a.outline), "order": list(state["order"]),
                 "slides": dict(state["slides"]), "notes": dict(state.get("notes", {}))}
    for s in slides:
        k, new = key(s), screen_text(s)
        if k not in state["slides"] or k not in found:
            plan[k] = ("new", {})
            continue
        sl, pushed = found[k], state["slides"][k]
        status, info = classify(sl, pushed, new)
        plan[k] = (status, info)
        if a.dry_run:
            continue
        if status == "update":
            shapes = {norm(sh.text_frame.text): sh for sh in texts(sl)}
            for b in info["boxes"]:
                old, val = pushed.get(b, ""), new.get(b, "")
                sh = shapes.get(norm(old)) if norm(old) else None
                if sh is not None and val:
                    set_text_keep_style(sh, val)
                elif sh is not None:  # box dropped from the outline: empty it (never delete shapes)
                    sh.text_frame.clear()
                elif val and b in geometry(s, new):
                    add_box(sl, s, new, b)
            new_state["slides"][k] = new
        elif status == "human":
            nt = sl.notes_slide.notes_text_frame
            prop = "\n".join(f"  {b}: {v}" for b, v in new.items() if norm(v) != norm(pushed.get(b)))
            if prop:
                nt.text = (nt.text.rstrip() + "\n\nProposed (outline " + Path(a.outline).name +
                           "; not applied because someone edited this slide):\n" + prop)
            # state keeps what we pushed before, so the slide stays protected on the next run
        # Notes: replace only if nobody edited them since our last push; else propose
        nt, want = sl.notes_slide.notes_text_frame, notes_text(s)
        pushed_notes = state.get("notes", {}).get(k, "")
        if status != "human" and norm(want) != norm(pushed_notes):
            if norm(nt.text) == norm(pushed_notes):
                nt.text = want
                new_state["notes"][k] = want
                info["notes"] = "updated"
                plan[k] = (status, info)
            else:
                nt.text = nt.text.rstrip() + "\n\nProposed notes (not applied, notes were edited):\n" + want
                info["notes"] = "edited by a person: proposed"
                plan[k] = (status, info)
    outline_keys = {key(s) for s in slides}
    for k in state["order"]:
        if k not in outline_keys:
            plan[k] = ("extra", {"note": "not in the new outline; left in the deck"})
    if not a.dry_run:
        n = len(prs.slides)
        for s in slides:
            if plan[key(s)][0] == "new":
                n += 1
                _, b = draw_slide(prs, s, n, assets)
                new_state["order"].append(key(s))
                new_state["slides"][key(s)] = b
                new_state["notes"][key(s)] = notes_text(s)
        save(prs, new_state, a.out)
    counts = {}
    for st, _ in plan.values():
        counts[st] = counts.get(st, 0) + 1
    print("PLAN", json.dumps(counts))
    for k, (st, info) in plan.items():
        if st != "same" or info:
            print(f"  {k}: {st} {json.dumps(info, ensure_ascii=False) if info else ''}")
    for w in warns:
        print("WARN", w)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("outline")
    b.add_argument("--out", required=True)
    b.add_argument("--assets", help="folder that holds assets/ (default: <outline dir>/mock)")
    m = sub.add_parser("merge")
    m.add_argument("outline")
    m.add_argument("--current", required=True, help="live deck exported as .pptx")
    m.add_argument("--state", required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--assets")
    m.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return cmd_build(a) if a.cmd == "build" else cmd_merge(a)


if __name__ == "__main__":
    sys.exit(main())
