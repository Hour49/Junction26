"""The measured query set of the law search (decision 0014): questions a designer asks, in English
and the law's language, each with the clause a person expects in the top 5, over the researchers'
real files in app/laws. A pack with no files skips. The expected clause was picked by reading the
clauses, not from what search returned. Known misses are strict xfails: when search finds them,
the test says so and the mark goes."""

from functools import cache

import pytest

from app.adapters.law_index import SqliteLawIndex, load_laws
from app.settings import Settings

TOP = 5


def _miss(why: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(reason=why, strict=True)


QUERIES = [
    ("fi", "minimum bedroom area", "fi-631-2024-4-2"),
    ("fi", "huonekorkeus", "fi-631-2024-4-2"),
    ("fi", "window light opening", "fi-631-2024-5-1"),
    ("fi", "stair width escape", "fi-1007-2017-3-2"),
    ("fi", "kaiteen korkeus", "fi-1007-2017-7-4"),
    ("fi", "guardrail height balcony", "fi-1007-2017-7-4"),
    ("fi", "accessible door clear width", "fi-241-2017-4-1"),
    ("fi", "esteetön oviaukko", "fi-241-2017-4-1"),
    ("fi", "fire compartment area", "fi-848-2017-15-1"),
    ("fi", "escape route marking", "fi-977-2024-3-1"),
    ("fi", "sound insulation between dwellings", "fi-796-2017-4-1"),
    ("fi", "ääneneristys", "fi-796-2017-4-1"),
    ("fi", "wet room waterproofing", "fi-782-2017-28-1"),
    ("fi", "ventilation air flow dwelling", "fi-1009-2017-9-1"),
    ("fi", "crawl space height", "fi-782-2017-20-1"),
    ("fi", "parking accessible", "fi-241-2017-2-3"),
    ("fi", "pelastustie", "fi-848-2017-40-2"),
    ("fi", "building permit documents drawings", "fi-751-2023-61-1"),
    pytest.param(
        "ch-zh",
        "minimum room height",
        "ch-zh-ls-700-1-304-2",
        marks=_miss("the pre-2015 Anhang § 304 clauses fill the top 5"),
    ),
    ("ch-zh", "Raumhöhe Wohnräume", "ch-zh-ls-700-1-304-2"),
    ("ch-zh", "window area floor area", "ch-zh-ls-700-1-302-2"),
    ("ch-zh", "Fensterfläche", "ch-zh-ls-700-1-302-2"),
    ("ch-zh", "escape route width", "ch-zh-ls-700-1-305"),
    ("ch-zh", "Fluchtweg", "ch-zh-ls-700-22-13-2"),
    ("ch-zh", "boundary distance", "ch-zh-ls-700-1-260"),
    ("ch-zh", "Grenzabstand", "ch-zh-ls-700-1-260"),
    ("ch-zh", "parking spaces number", "ch-zh-ls-700-1-242"),
    ("ch-zh", "Abstellplätze", "ch-zh-ls-700-1-242"),
    ("ch-zh", "accessible building wheelchair", "ch-zh-ls-700-1-239a-2"),
    ("ch-zh", "hindernisfrei Wohngebäude", "ch-zh-ls-700-1-239a-2"),
    ("ch-zh", "building permit required", "ch-sr-700-22-1"),
    ("ch-zh", "Baubewilligung", "ch-sr-700-22-1"),
    ("ch-zh", "attic room", "ch-zh-ls-700-1-304-3"),
    ("ch-zh", "stairs railings", "ch-zh-ls-700-21-20"),
    ("ch-zh", "Treppen Geländer", "ch-zh-ls-700-21-20"),
    ("ch-zh", "Lärmschutz", "ch-zh-ls-700-1-300"),
    ("ch-zh", "solar panels permit", "ch-zh-ls-700-6-2a"),
    ("ch-zh", "Abstand Nachbar Pflanzen", "ch-sr-210-688"),
]


@cache
def _index() -> SqliteLawIndex:
    return SqliteLawIndex(load_laws(Settings().laws_dir))


@pytest.mark.parametrize(("pack", "query", "expected"), QUERIES)
def test_the_expected_clause_is_in_the_top_5(pack: str, query: str, expected: str) -> None:
    index = _index()
    if not index.toc(pack):
        pytest.skip(f"no {pack} law files in app/laws")
    index.clause(expected)  # a clause the set expects is still in the files
    found = [hit.id for hit in index.search(pack, query, limit=TOP)]
    assert expected in found, f"{query!r}: {found}"
