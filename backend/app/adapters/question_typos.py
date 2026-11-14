"""Misspelt words of a question read as the template parser's own words (QA R1-3: "how mnay
bedroms are ther?" was refused). A fast typist drops, doubles or swaps letters, or hits the key
next to the one meant; a word that only looks like the vocabulary (beds, halls, roofs) is
another word, and is left as it is.

`corrected(text)` gives the text with each correction and the corrections as "'typed' as
'read'". A word is corrected when all of these hold:

- it has 4 or more letters, has no digit, is not in capitals (a room code: KHH, MH) and is
  outside quotes (a quoted name is read as typed);
- it is not a word of the vocabulary already, nor a form of one (VOCABULARY, and the stems of
  STEMS with any ending: Finnish inflects, "makuuhuonetta");
- it starts with the same letter as the word it becomes, and is at most 1 edit from it (2 for 8
  letters or more). An edit is a letter left out, added, or swapped with its neighbour, or, in
  a word of 6 letters or more, a letter replaced by one on the key next to it (QWERTY with the
  Finnish ö and ä): "walks" is not "walls", "bedroons" is "bedrooms";
- exactly one word of the vocabulary is that near (the nearest, alone): otherwise it is not
  guessed.
"""

import re

# Whole words: the measures' cue words and the subject nouns, English first, then the forms the
# parser's earlier one-edit list knew (de, fr, es, it).
VOCABULARY = frozenset(
    """
    many number count area length volume total floor floors storey storeys story stories
    bedroom bedrooms kitchen kitchens bathroom bathrooms washroom washrooms balcony balconies
    toilet toilets shower showers bathtub bathtubs sink sinks washbasin washbasins window
    windows door doors doorway doorways wall walls column columns beam beams stair stairs
    staircase staircases slab slabs room rooms space spaces apartment apartments sauna saunas
    living
    kuinka monta montako
    türen portes porte deuren puertas fenster fenêtres finestre ventanas duschen douches docce
    badewannen baignoires wohnungen wände räume pièces lavabos
    """.split()  # noqa: SIM905 (a word list reads better as text)
)
# Finnish stems: any ending makes a form of the word ("makuuhuone" + "tta").
STEMS = (
    "makuuhuone", "keittiö", "kylpyhuone", "kylpyamme", "pesuhuone", "parveke", "olohuone",
    "huoneisto", "asunto", "ikkuna", "suihku", "kerros", "huone", "sauna",
)  # fmt: skip
ROWS = ("qwertyuiopå", "asdfghjklöä", "zxcvbnm")
NEAR_KEYS = {
    key: {
        ROWS[row + dr][col + dc]
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        if (dr, dc) != (0, 0) and 0 <= row + dr < len(ROWS) and 0 <= col + dc < len(ROWS[row + dr])
    }
    for row, keys in enumerate(ROWS)
    for col, key in enumerate(keys)
}
WORD = re.compile(r"[^\W\d_]+")
TOO_FAR = 3


def corrected(text: str, protected: list[tuple[int, int]]) -> tuple[str, tuple[str, ...]]:
    """`text` with its misspelt words read as the vocabulary's, and what was read; the spans in
    `protected` (quoted names) are left as typed."""
    out: list[str] = []
    read: list[str] = []
    at = 0
    for match in WORD.finditer(text):
        word = match.group()
        if any(start <= match.start() < end for start, end in protected):
            continue
        meant = _meant(word)
        if meant is not None:
            out.append(text[at : match.start()] + meant)
            at = match.end()
            read.append(f"'{word}' as '{meant}'")
    return "".join(out) + text[at:], tuple(read)


def _meant(word: str) -> str | None:
    lower = word.casefold()
    if len(lower) < 4 or (word.isupper() and len(word) > 1) or _known(lower):
        return None
    limit = 1 if len(lower) < 8 else 2
    best: dict[str, tuple[int, str]] = {}  # vocabulary word or stem: (edits, the form read)
    for known in VOCABULARY:
        if known[0] == lower[0]:
            best[known] = (_distance(lower, known), known)
    for stem in STEMS:
        if stem[0] != lower[0]:
            continue
        for cut in range(max(1, len(stem) - limit), min(len(lower), len(stem) + limit) + 1):
            cost = _distance(lower[:cut], stem)  # equal: the longer stem part, shorter ending
            if cost <= best.get(stem, (TOO_FAR, ""))[0]:
                best[stem] = (cost, stem + lower[cut:])
    near = min((cost for cost, _ in best.values()), default=TOO_FAR)
    found = [form for cost, form in best.values() if cost == near]
    return found[0] if near <= limit and len(found) == 1 else None


def _known(word: str) -> bool:
    return word in VOCABULARY or word.startswith(STEMS)


def _distance(a: str, b: str) -> int:
    """Edits from `a` (typed) to `b`: a letter left out, added or swapped with its neighbour
    costs 1; a letter replaced by its neighbour on the keyboard costs 1 in a word of 6 letters
    or more; any other replacement is TOO_FAR. Capped at TOO_FAR."""
    near_key = len(a) >= 6
    rows = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        rows[i][0] = i
    for j in range(len(b) + 1):
        rows[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                swap = 0
            elif near_key and b[j - 1] in NEAR_KEYS.get(a[i - 1], ()):
                swap = 1
            else:
                swap = TOO_FAR
            cost = min(rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + swap)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cost = min(cost, rows[i - 2][j - 2] + 1)
            rows[i][j] = cost
    return min(rows[-1][-1], TOO_FAR)
