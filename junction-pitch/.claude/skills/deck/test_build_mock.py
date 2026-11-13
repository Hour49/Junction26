#!/usr/bin/env python3
"""Offline test for build_mock.py timing checks (2026 rule: the stage deck is 3 min only).

Run: python3 .claude/skills/deck/test_build_mock.py  -> prints "ok"
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_mock  # noqa: E402

text = (HERE / "outline-format.md").read_text(encoding="utf-8")
skeleton = re.search(r"```markdown\n(.*?)```", text, re.S).group(1)

# 1. The 3-min skeleton: 180 s, and no warning about a missing 5-min cut.
meta, slides = build_mock.parse(skeleton)
out, warns, core, _ = build_mock.build(meta, slides)
assert core == 180, core
assert not any("5-min" in w for w in warns), warns
assert not any("3-min cut totals" in w for w in warns), warns

# 2. An optional 5-min version that is too short still warns.
long_outline = skeleton.replace("## Backup D: Edge case (for Q&A)",
                                "## Slide 11: Edge case\n- Cut: 5-min\n- Seconds: 0 / 40", 1)
meta, slides = build_mock.parse(long_outline)
_, warns, _, total_long = build_mock.build(meta, slides)
assert any("5-min cut totals" in w for w in warns), (total_long, warns)

print("ok")
