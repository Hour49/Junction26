"""What a question is about, beyond its type: source, template, language and drawing group.

Tuned to the Stoa dataset of 2026-11-06 (questions.jsonl, 127,044 lines): on it every template gets
a language and none is left "und". A new language or naming scheme needs a line here.
"""

import re
from pathlib import PurePosixPath

UNDETERMINED = "und"

# Quoted names: 'x' (an apostrophe inside a word, as in d'escalier, doesn't open or close), „x“,
# „x”, «x», “x” and x in single curly quotes (U+2018, U+2019).
_QUOTED = re.compile(r"(?<!\w)'.+?'(?!\w)|„[^“”]*[“”]|«[^»]*»|“[^”]*”|‘[^’]*’")  # noqa: RUF001
_APARTMENT_LETTER = re.compile(r"\b(apartment|Wohnung|appartement|appartamento)\s+[A-Z]\b")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_WORD = re.compile(r"[^\W\d_]+")

# Words that mark a language in this dataset's question templates. A template gets the language
# with the most marker words; a tie or no marker at all gives "und".
_MARKERS: dict[str, frozenset[str]] = {
    code: frozenset(words.split())
    for code, words in {
        "en": "how many what which the this are is shown drawn there total could provide list "
        "available have does with and were used",
        "fi": "kuinka monta pohjapiirustuksessa pohjapiirustukseen ja on",
        "de": "wie viele gross groß sind ist gibt dieses diesem aller im des der das mit enthält",
        "fr": "quelle quel combien est la les des cet cette ce sur pièce pièces de",
        "it": "qual quanti quante è il della del nel nella questo questa locale locali numero di "
        "dell netta",
        "es": "cuál es el la del en número planta locales útil",
        "da": "hvad hvor mange er af på den det samlede vist plantegningen alle modellen",
        "nl": "wat hoeveel is de het van op staan er totale alle bevat",
        "et": "kui suur mitu on korruse korrusel plaanil näidatud ruumi kõigi kokku mudelis",
        "pl": "jaka jest ile na kondygnacji pomieszczenia powierzchnia pokazano rzucie łączna "
        "wszystkich znajduje się modelu",
        "ro": "care este numărul de pe planul nivelului din modelul",
    }.items()
}


def source_of(path: str) -> str:
    """`data/<source>/...` -> `<source>`."""
    parts = PurePosixPath(path).parts
    if len(parts) < 3 or parts[0] != "data":
        raise ValueError(f"expected data/<source>/<file>, got {path!r}")
    return parts[1]


def quoted_names(question: str) -> list[str]:
    """The quoted names in a question, in order, without their quote marks."""
    return [match[1:-1] for match in _QUOTED.findall(question)]


def template_of(question: str) -> str:
    """The question with quoted names, apartment letters and numbers masked."""
    masked = _QUOTED.sub("<Q>", question)
    masked = _APARTMENT_LETTER.sub(r"\1 <L>", masked)
    return _NUMBER.sub("<N>", masked)


def language_of(template: str) -> str:
    """Language code of a template (from `template_of`), or "und"."""
    words = [w.casefold() for w in _WORD.findall(re.sub(r"<[QLN]>", " ", template))]
    scores = {code: sum(w in markers for w in words) for code, markers in _MARKERS.items()}
    best = max(scores.values())
    leaders = [code for code, score in scores.items() if score == best]
    return leaders[0] if best > 0 and len(leaders) == 1 else UNDETERMINED


def group_of(path: str) -> str:
    """The drawing or building a file belongs to. Questions about one group share a split, so a
    translation, another format or another level of the same building can't leak into holdout."""
    file = PurePosixPath(path)
    source = source_of(path)
    if len(file.parts) > 3:  # data/<source>/<project>/.../<sheet>: one drawing set
        return f"{source}/{file.parts[2]}"
    stem = file.stem  # same name, other extension: the same drawing (dataset README)
    if source == "ifc_models":  # <building>_<model>[_plan-<level>]: plans rendered from the model
        stem = stem.split("_", 1)[0]
    elif source == "ifc_bench":  # <building>_<discipline>, e.g. sixty5_arc and sixty5_str
        stem = stem.rsplit("_", 1)[0]
    return f"{source}/{stem}"
