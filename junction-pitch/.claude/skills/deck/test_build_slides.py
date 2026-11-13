#!/usr/bin/env python3
"""Offline test for build_slides.py: build, simulate a teammate edit, change the outline, merge.

Run: ~/.cache/deck-venv/bin/python .claude/skills/deck/test_build_slides.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from pptx import Presentation

HERE = Path(__file__).resolve().parent
PY, TOOL = sys.executable, str(HERE / "build_slides.py")

OUTLINE = """# Deck outline: Test

## Slide 1: Hook
- Cut: both
- Seconds: 90 / 150
- Layout: hook
- On screen: Old hook line.
- Notes:
  Old hook notes.

## Slide 2: Problem
- Cut: both
- Seconds: 90 / 150
- Layout: big-number
- On screen: of people have it
- Number: 3 in 10
- Source: Test source, 2024, reported
- Notes:
  Problem notes.

## Slide 3: Story
- Cut: both
- Seconds: 0 / 0
- Layout: statement
- On screen: Story line.
- Notes:
  Story notes.
"""


def run(*args):
    r = subprocess.run([PY, TOOL, *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def slide_texts(path, i):
    s = Presentation(path).slides[i]
    return [sh.text_frame.text for sh in s.shapes if sh.has_text_frame], s.notes_slide.notes_text_frame.text


def main():
    d = Path(tempfile.mkdtemp())
    o1, o2 = d / "outline.md", d / "outline-v2.md"
    o1.write_text(OUTLINE)
    run("build", str(o1), "--out", str(d / "v1.pptx"))
    t, n = slide_texts(d / "v1.pptx", 1)
    assert "3 in 10" in t and "Problem notes." in n

    # A teammate edits slide 2's line and slide 3's notes in "Slides".
    p = Presentation(d / "v1.pptx")
    for sh in p.slides[1].shapes:
        if sh.has_text_frame and sh.text_frame.text == "of people have it":
            sh.text_frame.paragraphs[0].runs[0].text = "of shoppers (teammate)"
    p.slides[2].notes_slide.notes_text_frame.text = "Teammate notes."
    p.save(d / "live.pptx")

    # New outline: changes slide 1 text, slide 2 text, slide 3 notes, adds slide 4.
    o2.write_text(OUTLINE.replace("Old hook line.", "New hook line.")
                  .replace("of people have it", "of people hit it")
                  .replace("Story notes.", "New story notes.")
                  + "\n## Slide 4: Close\n- Cut: both\n- Seconds: 0 / 0\n- Layout: close\n- On screen: Bye.\n"
                    "- Notes:\n  Thanks.\n")
    out = run("merge", str(o2), "--current", str(d / "live.pptx"), "--state", str(d / "v1.state.json"),
              "--out", str(d / "v2.pptx"))
    plan = json.loads(out.split("PLAN ", 1)[1].splitlines()[0])
    assert '"notes": "edited by a person: proposed"' in out, out
    assert plan == {"update": 1, "human": 1, "same": 1, "new": 1}, (plan, out)

    t1, _ = slide_texts(d / "v2.pptx", 0)
    assert "New hook line." in t1, t1                        # untouched slide -> updated
    t2, n2 = slide_texts(d / "v2.pptx", 1)
    assert "of shoppers (teammate)" in t2, t2                 # human edit kept
    assert "of people hit it" not in t2 and "Proposed" in n2 and "of people hit it" in n2
    _, n3 = slide_texts(d / "v2.pptx", 2)
    assert n3.startswith("Teammate notes.") and "Proposed notes" in n3   # human notes kept
    t4, _ = slide_texts(d / "v2.pptx", 3)
    assert "Bye." in t4                                       # new slide appended
    assert len(Presentation(d / "v2.pptx").slides) == 4
    print("ok", d)


if __name__ == "__main__":
    main()
