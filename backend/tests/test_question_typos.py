"""Typos in a question (QA R1-3, "how mnay bedroms are ther?" was refused): a misspelt word is
read as the parser's own word when that is unambiguous, and the answer says what was read. Words
that only look like the vocabulary (beds, halls, roofs) stay refused."""

import pytest

from app.adapters.question_templates import TemplateParser
from app.core.answering.model import SEVERAL_THINGS, Query, Unsupported

PARSE = TemplateParser().parse

# (typed, as it should have been typed, what was read)
TYPOS = [
    ("how mnay bedroms are ther?", "how many bedrooms are there?",
     ("'mnay' as 'many'", "'bedroms' as 'bedrooms'")),
    ("How many kitchns are there?", "How many kitchens are there?", ("'kitchns' as 'kitchens'",)),
    ("How many bathroms does the flat have?", "How many bathrooms does the flat have?",
     ("'bathroms' as 'bathrooms'",)),
    ("how many windwos can you see on this floorplan", "how many windows can you see on this "
     "floorplan", ("'windwos' as 'windows'",)),
    ("How many doros are on this floor plan?", "How many doors are on this floor plan?",
     ("'doros' as 'doors'",)),
    ("How mnay toilets are there?", "How many toilets are there?", ("'mnay' as 'many'",)),
    ("How many balcnoies are there?", "How many balconies are there?",
     ("'balcnoies' as 'balconies'",)),
    ("What is the floor aera?", "What is the floor area?", ("'aera' as 'area'",)),
    ("How many showres are there?", "How many showers are there?", ("'showres' as 'showers'",)),
    ("Nubmer of saunas?", "Number of saunas?", ("'Nubmer' as 'number'",)),
    ("how many apartmnets are on this floor?", "how many apartments are on this floor?",
     ("'apartmnets' as 'apartments'",)),
    ("Kuinka mota makuuhuonetta on?", "Kuinka monta makuuhuonetta on?", ("'mota' as 'monta'",)),
    ("Kuinak monta makuuhuonetta on?", "Kuinka monta makuuhuonetta on?",
     ("'Kuinak' as 'kuinka'",)),
    ("Kuinka monta makuhuonetta on?", "Kuinka monta makuuhuonetta on?",
     ("'makuhuonetta' as 'makuuhuonetta'",)),
    ("Kuinka monta keitiötä on?", "Kuinka monta keittiötä on?", ("'keitiötä' as 'keittiötä'",)),
    ("Kuinka monta parvketta on?", "Kuinka monta parveketta on?",
     ("'parvketta' as 'parveketta'",)),
    ("Kuinka monta ikunaa on?", "Kuinka monta ikkunaa on?", ("'ikunaa' as 'ikkunaa'",)),
    ("Kuinka monta suihukua on?", "Kuinka monta suihkua on?", ("'suihukua' as 'suihkua'",)),
    ("Kuinka monta olohunetta on?", "Kuinka monta olohuonetta on?",
     ("'olohunetta' as 'olohuonetta'",)),
    ("Kuinka mnota huoneistoa on?", "Kuinka monta huoneistoa on?", ("'mnota' as 'monta'",)),
    ("Montkao saunaa on?", "Montako saunaa on?", ("'Montkao' as 'montako'",)),
    ("Montako asunota on?", "Montako asuntoa on?", ("'asunota' as 'asuntoa'",)),
]  # fmt: skip

# Questions about things the takeoff has no quantity for, one or two letters from a word it
# knows: refused before, refused now. "beds" is not "bedrooms": a room is not its furniture.
NEAR_MISSES = [
    "how many beds are there?",
    "how many roofs are there?",
    "how many halls are there?",
    "how many walks are there?",
    "how many balls are there?",
    "how many dogs are there?",
    "how many odors are there?",
    "how many cars are in the garage?",
    "how many chairs are there?",
    "how many books are on the shelf?",
    "how many sheds are there?",
    "how many windmills are there?",
    "how many people live here?",
    "How many KHH are there?",
    "Kuinka monta sänkyä on?",
    "Kuinka monta autoa on?",
    "Kuinka monta tuolia on?",
    "Kuinka monta kissaa on?",
    "Kuinka monta kattoa on?",
    "Kuinka monta lamppua on?",
    "Kuinka monta ihmistä asuu täällä?",
    "Kuinka monta kirjaa on?",
]


@pytest.mark.parametrize(("typed", "meant", "read"), TYPOS, ids=[t[0] for t in TYPOS])
def test_a_misspelt_word_is_read_as_the_word_meant(
    typed: str, meant: str, read: tuple[str, ...]
) -> None:
    right = PARSE(meant)
    assert isinstance(right, Query) and right.read_as == ()
    found = PARSE(typed)
    assert isinstance(found, Query)
    assert found.read_as == read
    assert found.model_copy(update={"read_as": ()}) == right


@pytest.mark.parametrize("text", NEAR_MISSES)
def test_a_word_that_only_looks_like_the_vocabulary_stays_refused(text: str) -> None:
    assert isinstance(PARSE(text), Unsupported)


def test_a_question_that_parses_as_typed_is_not_changed() -> None:
    # bathrooms are counted (the first subject); the misspelt second one is not read again
    assert PARSE("Kuinka monta kylpyhuonetta ja makuhuonetta on?") == Query(subject="room:bathroom")
    # Dutch "totale" is one letter from "total": a word of another language, not a typo
    dutch = PARSE("Wat is het totale netto volume van alle vloeren op 'OG'?")
    assert isinstance(dutch, Query) and dutch.read_as == ()


def test_an_unclear_word_is_not_guessed() -> None:
    # "stores" is as near to "storeys" as to "stories": not guessed (and it is a word)
    assert isinstance(PARSE("how many stores are there?"), Unsupported)


@pytest.mark.parametrize(
    "text",
    [
        "how mnay doors and windows are there?",  # refused as typed: no count asked
        "how many doors and windwos are there?",  # parses as doors alone as typed
    ],
)
def test_a_correction_never_hides_a_second_thing_counted(text: str) -> None:
    assert PARSE(text) == Unsupported(reason=SEVERAL_THINGS)


# QA R2-2-1: real words read as a stem with any ending ("autotallia" as "asuntotallia", a garage
# counted as apartments) or as a nearby word (ports, floods, stars, widows) were answered.
REAL_WORDS = [
    "Kuinka monta autotallia on?",
    "How many sanitary fixtures are there?",
    "How many sandwiches are there?",
    "How many automobiles are there?",
    "How many antonyms are there?",
    "How many pavements are there?",
    "How many ports are there?",
    "How many porters are there?",
    "How many floods are there?",
    "How many stars are there?",
    "How many widows are there?",
    "How many barrooms are there?",
]


@pytest.mark.parametrize("text", REAL_WORDS)
def test_a_real_word_is_never_read_as_another(text: str) -> None:
    assert isinstance(PARSE(text), Unsupported)
