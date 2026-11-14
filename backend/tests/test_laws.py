"""The building-law knowledge base (decision 0011): the loader refuses a law file that breaks the
format, naming the file; search finds clauses across case, accents and word endings, in one pack,
and treats the query as words only; the tools and the prompt's table of contents. On the made-up
laws of tests/fixtures/laws."""

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.adapters.law_index import SqliteLawIndex, load_laws
from app.adapters.law_tools import TOOLS, law_prompt, run_tool
from app.core.errors import InvalidInputError, NotFoundError
from app.core.laws.model import Law
from app.core.laws.search import match_query
from app.settings import Settings

LAWS = Path(__file__).parent / "fixtures" / "laws"
BACKEND = Path(__file__).parent.parent


def fi_law() -> dict[str, Any]:
    return json.loads((LAWS / "fi" / "fi-test-1.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def index() -> SqliteLawIndex:
    return SqliteLawIndex(load_laws(LAWS))


# The model: every rule of the format


def test_the_fixture_laws_validate() -> None:
    laws = load_laws(LAWS)
    assert [law.id for law in laws] == ["ch-zh-test-1", "fi-test-1"]


def clause_change(**change: Any) -> Callable[[dict[str, Any]], None]:
    return lambda law: law["clauses"][0].update(change)


BROKEN: dict[str, Callable[[dict[str, Any]], None]] = {
    "http url": lambda law: law.update(url="http://www.finlex.fi/x"),
    "unknown pack": lambda law: law.update(pack="de"),
    "jurisdiction of another pack": lambda law: law.update(jurisdiction="CH"),
    "unknown language": lambda law: law.update(language="es"),
    "bad date": lambda law: law.update(checked="14.11.2026"),
    "no clause": lambda law: law.update(clauses=[]),
    "unknown field": lambda law: law.update(source="x"),
    "clause id of another law": clause_change(id="fi-other-4-2"),
    "empty text": clause_change(text=""),
    "no translation of a Finnish text": clause_change(text_en=None),
    "empty summary": clause_change(summary_en=" "),
    "two keywords": clause_change(keywords=["a", "b"]),
    "thirteen keywords": clause_change(keywords=[str(n) for n in range(13)]),
    "no topic": clause_change(topics=[]),
    "unknown topic": clause_change(topics=["tax"]),
    "unknown comparison": clause_change(
        limits=[{"what": "area", "comparison": "~", "value": 7, "unit": "m2"}]
    ),
    "repeated clause id": lambda law: law["clauses"].append(law["clauses"][0]),
}


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_the_model_refuses_a_broken_law(name: str) -> None:
    law = fi_law()
    BROKEN[name](law)
    with pytest.raises(ValidationError):
        Law.model_validate(law)


def test_a_law_in_english_needs_no_translation() -> None:
    law = fi_law()
    law["language"] = "en"
    law["clauses"][0]["text_en"] = None
    assert Law.model_validate(law).clauses[0].text_en is None


def test_swiss_federal_law_goes_in_the_zurich_pack() -> None:
    law = json.loads((LAWS / "ch-zh" / "ch-zh-test-1.json").read_text(encoding="utf-8"))
    assert Law.model_validate({**law, "jurisdiction": "CH"}).jurisdiction == "CH"


# The loader: a bad file stops the start, naming the file


def write(folder: Path, pack: str, name: str, law: dict[str, Any]) -> None:
    (folder / pack).mkdir(parents=True, exist_ok=True)
    (folder / pack / f"{name}.json").write_text(json.dumps(law), encoding="utf-8")


def test_a_file_that_does_not_validate_is_named(tmp_path: Path) -> None:
    law = fi_law()
    law["url"] = "ftp://x"
    write(tmp_path, "fi", "fi-test-1", law)
    with pytest.raises(InvalidInputError, match=r"fi/fi-test-1.json"):
        load_laws(tmp_path)


def test_a_file_that_is_not_json_is_named(tmp_path: Path) -> None:
    (tmp_path / "fi").mkdir()
    (tmp_path / "fi" / "fi-x.json").write_text("{", encoding="utf-8")
    with pytest.raises(InvalidInputError, match=r"fi/fi-x.json"):
        load_laws(tmp_path)


def test_the_id_is_the_file_name(tmp_path: Path) -> None:
    write(tmp_path, "fi", "fi-test-2", fi_law())
    with pytest.raises(InvalidInputError, match=r"fi-test-2.json: its id is 'fi-test-1'"):
        load_laws(tmp_path)


def test_the_pack_is_the_folder(tmp_path: Path) -> None:
    write(tmp_path, "ch-zh", "fi-test-1", fi_law())
    with pytest.raises(InvalidInputError, match="its pack is 'fi'"):
        load_laws(tmp_path)


def test_clause_ids_are_unique_across_files(tmp_path: Path) -> None:
    law = fi_law()
    write(tmp_path, "fi", "fi-test-1", law)
    other = {**law, "id": "fi-test"}  # its clause ids still start with "fi-test-"
    write(tmp_path, "fi", "fi-test", other)
    with pytest.raises(InvalidInputError, match=r"fi-test-1-4-2.*twice"):
        load_laws(tmp_path)


def test_a_missing_or_empty_folder_has_no_laws(tmp_path: Path) -> None:
    assert load_laws(tmp_path / "none") == ()
    (tmp_path / "fi").mkdir()
    assert load_laws(tmp_path) == ()


def test_the_shipped_laws_validate() -> None:
    """The researchers' files in app/laws (none yet is fine): what the app loads at start."""
    laws = load_laws(Settings().laws_dir)
    SqliteLawIndex(laws)


def test_the_validate_command_reports_counts_and_fails_on_a_bad_file(tmp_path: Path) -> None:
    command = [sys.executable, "-m", "app.adapters.law_index", "validate"]
    good = subprocess.run([*command, str(LAWS)], cwd=BACKEND, capture_output=True, text=True)
    assert good.returncode == 0, good.stderr
    assert "fi: 1 laws, 2 clauses" in good.stdout
    assert "ch-zh: 1 laws, 1 clauses" in good.stdout
    write(tmp_path, "fi", "fi-test-2", fi_law())
    bad = subprocess.run([*command, str(tmp_path)], cwd=BACKEND, capture_output=True, text=True)
    assert bad.returncode == 1
    assert "fi-test-2.json" in bad.stderr


# Search


def ids(hits: list[Any]) -> list[str]:
    return [hit.id for hit in hits]


def test_search_ranks_the_matching_clause_first(index: SqliteLawIndex) -> None:
    hits = index.search("fi", "minimum bedroom area")
    assert ids(hits)[0] == "fi-test-1-4-2"
    first = hits[0]
    assert (first.law_id, first.ref, first.title_en) == (
        "fi-test-1",
        "4 § 2 mom.",
        "Test decree on residential spaces",
    )
    assert first.url == "https://www.finlex.fi/fi/lainsaadanto/2026/1"
    assert first.score > 0


def test_search_finds_word_endings_case_and_accents(index: SqliteLawIndex) -> None:
    assert ids(index.search("ch-zh", "Fluchtweg")) == ["ch-zh-test-1-12-1"]
    assert ids(index.search("ch-zh", "GEBAUDE")) == ["ch-zh-test-1-12-1"]
    assert ids(index.search("fi", "uloskaytava"))[0] == "fi-test-1-9-1"


def test_search_stays_in_its_pack(index: SqliteLawIndex) -> None:
    assert index.search("fi", "Fluchtwege") == []
    assert ids(index.search("ch-zh", "escape route")) == ["ch-zh-test-1-12-1"]


def test_search_filters_by_topic_and_limits(index: SqliteLawIndex) -> None:
    assert ids(index.search("fi", "room exit", topic="fire")) == ["fi-test-1-9-1"]
    assert len(index.search("fi", "room exit")) == 2
    assert len(index.search("fi", "room exit", limit=1)) == 1


@pytest.mark.parametrize(
    "query", ['"', "*", 'room" OR "x', "NEAR(room exit)", "-room", "room AND", "^x", ":", ""]
)
def test_the_query_is_words_only(index: SqliteLawIndex, query: str) -> None:
    index.search("fi", query)  # never an FTS5 syntax error


def test_match_query_quotes_every_word() -> None:
    assert match_query('NEAR("x" -y*) Fluchtweg') == '"NEAR"* OR "x"* OR "y"* OR "Fluchtweg"*'
    assert match_query("  ") is None


def test_an_unknown_pack_is_not_found(index: SqliteLawIndex) -> None:
    with pytest.raises(NotFoundError, match="no law pack 'xx'"):
        index.search("xx", "room")


# Clause and table of contents


def test_a_clause_comes_with_its_law(index: SqliteLawIndex) -> None:
    clause = index.clause("fi-test-1-9-1")
    assert clause.text.startswith("Asuinrakennuksessa")
    assert (clause.law_id, clause.law_number, clause.law_title_en) == (
        "fi-test-1",
        "1/2026",
        "Test decree on residential spaces",
    )
    assert (clause.url, clause.language, clause.checked) == (
        "https://www.finlex.fi/fi/lainsaadanto/2026/1",
        "fi",
        "2026-11-14",
    )
    with pytest.raises(NotFoundError):
        index.clause("fi-none")


def test_the_toc_lists_each_law_of_a_pack(index: SqliteLawIndex) -> None:
    (entry,) = index.toc("fi")
    assert entry.model_dump() == {
        "law_id": "fi-test-1",
        "number": "1/2026",
        "title_en": "Test decree on residential spaces",
        "clauses": 2,
        "topics": ["rooms", "fire", "escape-routes"],
    }
    assert index.packs() == ("fi", "ch-zh")


# Tools


def test_the_tools_are_openai_functions() -> None:
    names = [tool["function"]["name"] for tool in TOOLS]
    assert names == ["search_law", "get_clause"]
    for tool in TOOLS:
        assert tool["type"] == "function"
        assert tool["function"]["parameters"]["type"] == "object"
    search = TOOLS[0]["function"]
    assert search["parameters"]["required"] == ["pack", "query"]
    assert "cite" in search["description"] and "url" in search["description"]


def test_run_tool_searches_and_reads(index: SqliteLawIndex) -> None:
    found = json.loads(run_tool(index, "search_law", '{"pack": "fi", "query": "bedroom area"}'))
    assert found["hits"][0]["id"] == "fi-test-1-4-2"
    clause = json.loads(run_tool(index, "get_clause", {"clause_id": "fi-test-1-4-2"}))
    assert clause["ref"] == "4 § 2 mom." and clause["url"].startswith("https://")


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("delete_law", {}),
        ("search_law", "{not json"),
        ("search_law", {"pack": "fi"}),
        ("search_law", {"pack": "xx", "query": "room"}),
        ("search_law", {"pack": "fi", "query": "room", "topic": "tax"}),
        ("get_clause", {"clause_id": "fi-none"}),
        ("get_clause", ["fi-test-1-4-2"]),
    ],
)
def test_a_bad_call_is_an_error_the_model_can_read(
    index: SqliteLawIndex, name: str, arguments: Any
) -> None:
    assert set(json.loads(run_tool(index, name, arguments))) == {"error"}


def test_the_prompt_names_the_laws_and_the_tools(index: SqliteLawIndex) -> None:
    text = law_prompt(index, "fi")
    assert "fi-test-1" in text and "1/2026" in text and "search_law" in text
    assert "Fluchtwege" not in text


def test_the_prompt_stays_under_its_budget_on_30_laws(tmp_path: Path) -> None:
    base = fi_law()
    for n in range(30):
        law = json.loads(json.dumps(base).replace("fi-test-1", f"fi-test-{n:02d}"))
        law["title_en"] = f"Ministry of the Environment Decree on a long subject number {n} " * 3
        write(tmp_path, "fi", f"fi-test-{n:02d}", law)
    text = law_prompt(SqliteLawIndex(load_laws(tmp_path)), "fi")
    assert len(text) / 4 <= 1500  # ~4 characters a token
    assert "fi-test-29" in text


def test_the_prompt_says_what_it_left_out_past_the_budget(tmp_path: Path) -> None:
    base = fi_law()
    for n in range(80):
        law = json.loads(json.dumps(base).replace("fi-test-1", f"fi-test-{n:02d}"))
        write(tmp_path, "fi", f"fi-test-{n:02d}", law)
    text = law_prompt(SqliteLawIndex(load_laws(tmp_path)), "fi")
    assert len(text) / 4 <= 1500
    assert "more laws" in text
