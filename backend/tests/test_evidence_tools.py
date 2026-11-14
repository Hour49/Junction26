"""The evidence index as the chat agent sees it (decision 0012, contract v1): `ProjectEvidence`
(search one hit per file, get by passage or file id, the system-prompt paragraph) and the
OpenAI-format tools with their dispatcher, which answers every call with JSON and never raises."""

import json
import sqlite3
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

import app.adapters.evidence.store as store_module
from app.adapters.evidence.project import NOTHING, ProjectEvidence
from app.adapters.evidence.store import SqliteEvidenceIndex
from app.adapters.evidence_tools import (
    EVIDENCE_TOOLS,
    UNAVAILABLE,
    evidence_prompt,
    run_evidence_tool,
)
from app.core.evidence.chunks import passages
from app.core.ingest.model import FileStatus, ProjectStatus

AT = "2026-11-14T00:00:00+00:00"
LONG = " ".join(f"Sentence {n} about the old stone barn and its roof." for n in range(30))


def described(subject: str, detail: str = "", verdict: str | None = None, **extra: Any) -> dict:
    triage: dict[str, Any] = {
        "class": "not_drawing",
        "p_plan": 0.1,
        "method": "test",
        "description": {
            "text": f"{subject}.",
            "subject": subject,
            "model": "test",
            "what_it_is": extra.pop("what_it_is", "photograph"),
            "shows_building": True,
            "visible_text": extra.pop("visible_text", ""),
            "detail": detail,
            "language": extra.pop("language", None),
        },
        **extra,
    }
    if verdict is not None:
        triage["relevance"] = {"verdict": verdict, "why": "", "judge": "test"}
    return triage


def project(*files: tuple[str, dict[str, Any] | None], sha: bool = False) -> ProjectStatus:
    found = [
        FileStatus.model_validate(
            {
                "id": f"f{n}",
                "path": path,
                "size": 10 * n,
                "state": "set_aside",
                **({"sha256": f"{n:064x}"} if sha else {}),
                **({"triage": triage} if triage is not None else {}),
            }
        )
        for n, (path, triage) in enumerate(files, start=1)
    ]
    return ProjectStatus(id="p1", name="site.zip", state="done", created_at=AT, files=tuple(found))


FILES: tuple[tuple[str, dict[str, Any] | None], ...] = (
    (
        "facade.jpg",
        described("south facade of a brick house", "Red brick. Three windows.", "related"),
    ),
    ("barn.jpg", described("old stone barn", LONG, "related")),
    ("cat.jpg", described("a cat on a sofa", "A grey cat sleeping.", "unrelated")),
    (
        "letter.png",
        described(
            "letter to the building office",
            "A typed letter.",
            "unsure",
            what_it_is="text_page",
            visible_text="Rakennusvirasto\nLupahakemus 1962",
            language="fi",
        ),
    ),
    ("plan.png", {"class": "floor_plan", "p_plan": 0.9, "method": "test"}),
)
SITE = project(*FILES)


def open_index(
    tmp_path: Path, status: ProjectStatus = SITE, embedder: Any = None, credits: Any = None
) -> ProjectEvidence:
    store = SqliteEvidenceIndex(tmp_path / "projects", passages, embedder)
    return ProjectEvidence(store, status, credits or (lambda size, sha: None))


def call(index: ProjectEvidence, name: str, arguments: Any) -> dict[str, Any]:
    return json.loads(run_evidence_tool(index, name, arguments))


# ---------------------------------------------------------------- search


def test_search_returns_one_hit_per_file_and_k_counts_files(tmp_path: Path) -> None:
    index = open_index(tmp_path)
    found = index.search("stone barn roof", k=5)
    assert [hit.file for hit in found.hits] == ["barn.jpg"]  # many passages match, one hit
    assert found.indexed_files == 4  # the plan is not in the index
    both = index.search("brick barn", k=1)
    assert len(both.hits) == 1
    assert len(index.search("brick barn", k=5).hits) == 2


def test_a_hit_carries_the_contract_fields(tmp_path: Path) -> None:
    index = open_index(tmp_path)
    (hit,) = index.search("Rakennusvirasto").hits
    assert hit.id == "f4-visible_text-1"
    assert (hit.file_id, hit.file, hit.page, hit.part) == ("f4", "letter.png", 1, "visible_text")
    assert (hit.kind, hit.subject, hit.language, hit.verdict) == (
        "text_page",
        "letter to the building office",
        "fi",
        "unsure",
    )
    assert hit.why.terms == ("rakennusvirasto",)
    assert (hit.why.bm25_rank, hit.why.dense_rank) == (1, None)
    assert hit.credit is None and hit.score > 0
    assert index.search("Rakennusvirasto").method == "BM25 (no embedder model on this machine)"


def test_unrelated_files_are_left_out_and_counted_unless_asked_for(tmp_path: Path) -> None:
    index = open_index(tmp_path)
    found = index.search("cat")
    assert (found.hits, found.unrelated_left_out) == ((), 1)
    asked = index.search("cat", include_unrelated=True)
    assert [hit.file for hit in asked.hits] == ["cat.jpg"]
    assert asked.unrelated_left_out == 0


def test_an_empty_index_says_why_in_a_note(tmp_path: Path) -> None:
    index = open_index(tmp_path, project(("plan.png", None)))
    found = index.search("anything")
    assert (found.indexed_files, found.hits, found.note) == (0, (), NOTHING)
    assert open_index(tmp_path / "b").search("anything").note is None


def test_the_credit_comes_from_the_files_size_and_sha256(tmp_path: Path) -> None:
    asked: list[tuple[int, str]] = []

    def credit(size: int, sha: str) -> str | None:
        asked.append((size, sha))
        return "Photo: A. Person, CC BY 4.0"

    index = open_index(tmp_path, project(*FILES, sha=True), credits=credit)
    (hit,) = index.search("brick").hits
    assert hit.credit == "Photo: A. Person, CC BY 4.0"
    assert asked == [(10, f"{1:064x}")]
    assert open_index(tmp_path / "b", credits=credit).search("brick").hits[0].credit is None


class Letters:
    """Bag of letters, L2-normalised: a stand-in embedder that ranks by spelling."""

    name = "letters-v1"
    label = "letters"

    def embed(self, texts: Sequence[str]) -> NDArray[np.float32]:
        rows = np.zeros((len(texts), 26), np.float32)
        for i, text in enumerate(texts):
            for char in text.lower():
                if "a" <= char <= "z":
                    rows[i, ord(char) - 97] += 1
        norms = np.maximum(np.linalg.norm(rows, axis=1, keepdims=True), 1e-9)
        return (rows / norms).astype(np.float32)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        return self.embed([text])[0]


def test_with_an_embedder_search_is_hybrid_and_reports_both_ranks(tmp_path: Path) -> None:
    index = open_index(tmp_path, embedder=Letters())
    found = index.search("brick", k=4)
    assert found.method == "hybrid: BM25 + letters, reciprocal rank fusion"
    first = found.hits[0]
    assert (first.file, first.why.bm25_rank) == ("facade.jpg", 1)
    assert first.why.dense_rank is not None
    assert len(found.hits) == 3  # dense ranks every kept file; the unrelated cat stays out
    assert [hit.why.bm25_rank for hit in found.hits[1:]] == [None, None]
    assert all(hit.why.terms == () for hit in found.hits[1:])  # found by meaning only


def test_searches_answer_while_another_connection_holds_the_write_lock(tmp_path: Path) -> None:
    """Every tool call and REST request opens the index; with the status unchanged that is a
    read. So while ingest holds the write lock (embedding a project), 8 concurrent searches all
    answer instead of waiting for it and failing with "database is locked" (codecheck B1)."""
    open_index(tmp_path).prompt()  # built
    writer = sqlite3.connect(tmp_path / "projects" / "p1" / "evidence.sqlite", timeout=0)
    writer.execute("begin immediate")  # the write lock, held until every search is back
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            found = list(pool.map(lambda _: open_index(tmp_path).search("brick"), range(8)))
        assert [[hit.file for hit in result.hits] for result in found] == [["facade.jpg"]] * 8
    finally:
        writer.rollback()
        writer.close()


def test_a_file_without_its_schema_reads_as_empty_and_the_next_open_repairs_it(
    tmp_path: Path,
) -> None:
    """codecheck e6: a search between another sync's connect (the file exists) and its schema,
    or after a sync that died there, found no `meta` table and failed every time after."""
    path = tmp_path / "projects" / "p1" / "evidence.sqlite"
    path.parent.mkdir(parents=True)
    sqlite3.connect(path).close()  # the file as a sync's connect leaves it, no tables yet
    found = open_index(tmp_path).search("brick")
    assert [hit.file for hit in found.hits] == ["facade.jpg"]


def test_a_sync_that_fails_after_the_schema_leaves_no_half_made_index(tmp_path: Path) -> None:
    """The schema is written in the same transaction as the rows: a sync that dies rolls both
    back, so a reader never sees tables without their rows."""

    class Dying(SqliteEvidenceIndex):
        def _write(self, db: sqlite3.Connection, project_id: str, current: dict[str, Any]) -> None:
            raise RuntimeError("killed mid-sync")

    with pytest.raises(RuntimeError):
        Dying(tmp_path / "projects", passages, None).update(SITE)
    path = tmp_path / "projects" / "p1" / "evidence.sqlite"
    with sqlite3.connect(path) as db:
        assert db.execute("select name from sqlite_master where type = 'table'").fetchall() == []
    assert [hit.file for hit in open_index(tmp_path).search("brick").hits] == ["facade.jpg"]


def test_an_index_in_step_is_read_through_one_connection_and_never_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_index(tmp_path, embedder=Letters()).prompt()  # built
    statements: list[str] = []
    connect = sqlite3.connect

    def counted(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        db = connect(*args, **kwargs)
        db.set_trace_callback(statements.append)
        statements.append("-- connect")
        return db

    monkeypatch.setattr(store_module.sqlite3, "connect", counted)
    found = open_index(tmp_path, embedder=Letters()).search("brick", k=4)
    assert len(found.hits) == 3  # BM25, dense and three passages read
    assert statements.count("-- connect") == 1
    written = [s for s in statements if s.split()[0].lower() in WRITES or "journal_mode" in s]
    assert written == []  # no schema, no journal pragma, no transaction (FTS5 reads data_version)


WRITES = {"begin", "insert", "update", "delete", "replace", "create", "commit"}


def test_a_page_entry_keeps_its_page_in_search_and_get(tmp_path: Path) -> None:
    index = open_index(
        tmp_path, project(("scans/set#p3.pdf", described("a site map", "", "related")))
    )
    (hit,) = index.search("site map").hits
    assert hit.page == 3
    detail = index.get(hit.id)
    assert detail is not None and detail.page == 3


def test_nothing_indexed_embeds_no_query(tmp_path: Path) -> None:
    class Refusing(Letters):
        def embed_query(self, text: str) -> NDArray[np.float32]:
            raise AssertionError("embedded a query with nothing to search")

    index = open_index(tmp_path, project(("plan.png", None)), embedder=Refusing())
    assert index.search("anything").hits == ()


def test_a_failed_open_is_a_tool_error_and_the_prompt_says_evidence_is_unavailable(
    tmp_path: Path,
) -> None:
    class Broken(SqliteEvidenceIndex):
        def sync(self, status: ProjectStatus, reader: Any) -> None:
            raise sqlite3.OperationalError("database is locked")

    index = ProjectEvidence(Broken(tmp_path, passages, None), SITE, lambda size, sha: None)
    assert call(index, "search_evidence", {"query": "brick"}) == {"error": "internal error"}
    assert call(index, "get_evidence", {"id": "f1"}) == {"error": "internal error"}
    assert evidence_prompt(index) == UNAVAILABLE


# ---------------------------------------------------------------- get


def test_get_by_passage_id_or_file_id(tmp_path: Path) -> None:
    index = open_index(tmp_path)
    by_file = index.get("f1")
    assert by_file is not None and by_file.id == "f1-summary"
    assert by_file.text.startswith("photograph. south facade of a brick house.")
    assert by_file.description.detail == "Red brick. Three windows."
    assert by_file.relevance is not None and by_file.relevance.verdict == "related"
    detail = index.get("f2-detail-2")
    assert detail is not None and (detail.part, detail.file) == ("detail", "barn.jpg")
    body = detail.model_dump(mode="json")
    assert "register" in body and "register_" not in body
    assert "cost_usd" not in body["description"]


def test_get_returns_unrelated_files_and_none_for_what_is_not_there(tmp_path: Path) -> None:
    index = open_index(tmp_path)
    cat = index.get("f3")
    assert cat is not None and cat.verdict == "unrelated"
    for missing in ["f5", "f99", "f2-detail-99", "f1-visible_text-1", "barn.jpg", ""]:
        assert index.get(missing) is None, missing


# ---------------------------------------------------------------- the tools


def test_the_tools_are_openai_function_specs_named_as_the_contract() -> None:
    names = [tool["function"]["name"] for tool in EVIDENCE_TOOLS]
    assert names == ["search_evidence", "get_evidence"]
    for tool in EVIDENCE_TOOLS:
        assert tool["type"] == "function"
        assert tool["function"]["parameters"]["type"] == "object"
    assert EVIDENCE_TOOLS[0]["function"]["parameters"]["required"] == ["query"]
    assert EVIDENCE_TOOLS[1]["function"]["parameters"]["required"] == ["id"]


def test_run_search_and_get_answer_json(tmp_path: Path) -> None:
    index = open_index(tmp_path)
    found = call(index, "search_evidence", {"query": "Lupahakemus", "k": 3})
    assert found["hits"][0]["id"] == "f4-visible_text-1"
    assert found["query"] == "Lupahakemus"
    text = run_evidence_tool(index, "search_evidence", '{"query": "Lupahakemus"}')
    assert "Rakennusvirasto" in text  # Finnish letters stay readable: no \\u escapes
    got = call(index, "get_evidence", {"id": found["hits"][0]["id"]})
    assert got["description"]["language"] == "fi"


def test_arguments_may_come_as_json_text_or_as_a_dict(tmp_path: Path) -> None:
    index = open_index(tmp_path)
    as_text = run_evidence_tool(index, "search_evidence", '{"query": "brick", "k": 2}')
    as_dict = run_evidence_tool(index, "search_evidence", {"query": "brick", "k": 2})
    assert as_text == as_dict and json.loads(as_dict)["hits"][0]["file"] == "facade.jpg"


@pytest.mark.parametrize("k", [5.0, "5"])
def test_k_as_a_whole_float_or_a_numeral_is_taken(tmp_path: Path, k: Any) -> None:
    """A function-call serialiser may write 5 as 5.0 (Gemini's carry doubles); contract v1.1
    forbids unknown arguments, not lax types."""
    found = call(open_index(tmp_path), "search_evidence", {"query": "brick barn letter", "k": k})
    assert len(found["hits"]) == 3


@pytest.mark.parametrize("k", [1, 20])
def test_k_at_the_ends_of_its_range_is_taken(tmp_path: Path, k: int) -> None:
    found = call(open_index(tmp_path), "search_evidence", {"query": "brick barn letter", "k": k})
    assert len(found["hits"]) == min(k, 3)


def test_include_unrelated_must_be_true_to_count(tmp_path: Path) -> None:
    index = open_index(tmp_path)
    assert (
        call(index, "search_evidence", {"query": "cat", "include_unrelated": False})["hits"] == []
    )
    asked = call(index, "search_evidence", {"query": "cat", "include_unrelated": True})
    assert [hit["file"] for hit in asked["hits"]] == ["cat.jpg"]


@pytest.mark.parametrize(
    ("name", "arguments", "says"),
    [
        ("find_photos", "{}", "There is no tool 'find_photos'"),
        ("search_evidence", "{not json", "not valid JSON"),
        ("search_evidence", "[1, 2]", "must be a JSON object"),
        ("search_evidence", "{}", "search_evidence: query: Field required"),
        ("search_evidence", '{"query": "   "}', "query: String should have at least 1 character"),
        ("search_evidence", '{"query": 5}', "query: Input should be a valid string"),
        ("search_evidence", {"query": "x" * 501}, "query: String should have at most 500"),
        (
            "search_evidence",
            {"query": "x", "k": 0},
            "k: Input should be greater than or equal to 1",
        ),
        ("search_evidence", {"query": "x", "k": 21}, "k: Input should be less than or equal to 20"),
        ("search_evidence", {"query": "x", "k": 2.5}, "k: Input should be a valid integer"),
        ("search_evidence", {"query": "x", "k": "two"}, "k: Input should be a valid integer"),
        ("search_evidence", {"query": "x", "include_unrelated": "maybe"}, "include_unrelated"),
        (
            "search_evidence",
            {"query": "x", "kind": "photo"},
            "kind: Extra inputs are not permitted",
        ),
        ("get_evidence", "{}", "get_evidence: id: Field required"),
        ("get_evidence", {"id": "f" * 65}, "id: String should have at most 64"),
        ("get_evidence", '{"id": "f99"}', "No evidence 'f99'"),
    ],
)
def test_a_bad_call_is_an_error_sentence_not_an_exception(
    tmp_path: Path, name: str, arguments: Any, says: str
) -> None:
    answer = call(open_index(tmp_path), name, arguments)
    assert list(answer) == ["error"] and says in answer["error"]


def test_an_unexpected_failure_is_an_internal_error_answer(tmp_path: Path) -> None:
    class Broken(ProjectEvidence):
        def search(self, query: str, k: int = 5, include_unrelated: bool = False) -> Any:
            raise RuntimeError("disk gone")

    store = SqliteEvidenceIndex(tmp_path / "projects", passages, None)
    broken = Broken(store, SITE, lambda size, sha: None)
    assert call(broken, "search_evidence", {"query": "brick"}) == {"error": "internal error"}
    assert run_evidence_tool(broken, "search_evidence", None) is not None  # type: ignore[arg-type]


# ---------------------------------------------------------------- the system prompt


def test_the_prompt_lists_kinds_languages_and_files_or_says_there_is_nothing(
    tmp_path: Path,
) -> None:
    prompt = evidence_prompt(open_index(tmp_path))
    assert prompt.startswith(
        "Project evidence: 4 files or pages that are not floor plans (4 described;"
    )
    assert "3 photograph, 1 text_page" in prompt
    assert "text document" not in prompt and "listed by name" not in prompt  # none of either
    assert "printed text in fi" in prompt
    assert "1 judged unrelated, searched only on request" in prompt
    assert "f2 photograph: old stone barn" in prompt
    assert "Floor plan facts" in prompt
    many = [(f"{n}.jpg", described("a long subject " * 30, "", "related")) for n in range(30)]
    capped = evidence_prompt(open_index(tmp_path / "c", project(*many)))
    assert len(capped) == 6000 and capped.endswith("...")
    empty = evidence_prompt(open_index(tmp_path / "b", project(("plan.png", None))))
    assert empty == f"Project evidence: none. {NOTHING} Do not call search_evidence."
    assert "EVIDENCE_SCOPE" in NOTHING  # the setting that decides, not "triage was off"


def test_an_index_written_before_passage_pages_is_migrated_on_its_next_sync(
    tmp_path: Path,
) -> None:
    """Schema 1 (#235) had no passages.page: the next sync adds it, as a write, and searches
    answer from it (a reader selecting the page would fail on the old file)."""
    SqliteEvidenceIndex(tmp_path / "projects", passages, None).update(SITE)
    path = tmp_path / "projects" / "p1" / "evidence.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("alter table passages drop column page")
        db.execute("delete from meta where key = 'schema'")
    index = open_index(tmp_path)
    assert [hit.file for hit in index.search("brick").hits] == ["facade.jpg"]
    with sqlite3.connect(path) as db:
        columns = {row[1] for row in db.execute("pragma table_info(passages)")}
        schema = db.execute("select value from meta where key = 'schema'").fetchone()
    assert "page" in columns and schema == (store_module.SCHEMA_VERSION,)
