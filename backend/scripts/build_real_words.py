"""Rebuild app/adapters/real_words.txt: the real English words the typo reader
(app/adapters/question_typos.py) would otherwise read as one of its own words (QA R2-2-1:
"ports" as "portes", "sanitary" as a sauna). Source: SCOWL's american-english list (Debian's
wamerican, /usr/share/dict/american-english). Run after changing the reader's vocabulary:

    uv run python scripts/build_real_words.py [/usr/share/dict/american-english]
"""

import sys
from pathlib import Path

from app.adapters import question_typos

NOTICE = """# Real English words the typo reader leaves as typed (scripts/build_real_words.py).
# Derived from SCOWL (Spell Checker Oriented Word Lists), american-english:
#   Copyright 2000-2011 by Kevin Atkinson
#   Permission to use, copy, modify, distribute and sell these word
#   lists, the associated scripts, the output created from the scripts,
#   and its documentation for any purpose is hereby granted without fee,
#   provided that the above copyright notice appears in all copies and
#   that both that copyright notice and this permission notice appear in
#   supporting documentation. Kevin Atkinson makes no representations
#   about the suitability of this array for any purpose. It is provided
#   "as is" without express or implied warranty.
"""


def main() -> None:
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "/usr/share/dict/american-english")
    words = {line.strip().casefold() for line in source.read_text(encoding="utf-8").splitlines()}
    question_typos.REAL_WORDS = frozenset()  # what the rules alone would read as another word
    near = sorted(w for w in words if w.isalpha() and question_typos._meant(w) is not None)
    out = Path(question_typos.__file__).with_name("real_words.txt")
    out.write_text(NOTICE + "".join(f"{w}\n" for w in near), encoding="utf-8")
    print(f"{len(near)} real words near the vocabulary -> {out}")


if __name__ == "__main__":
    main()
