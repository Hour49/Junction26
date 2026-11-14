"""The evidence index's plumbing (decision 0012): which files are sources, reciprocal rank fusion,
and the per-project SQLite store (incremental update, BM25, cosine, verdict filter, lookup)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from app.adapters.evidence.store import FILE, SqliteEvidenceIndex, fts_query
from app.core.evidence.fusion import POOL, RRF_K, fused
from app.core.evidence.model import EvidenceSource, Passage, sources
from app.core.ingest.model import FileStatus, ProjectStatus

ALL = frozenset({"related", "unrelated", "unsure", None})
KEPT = frozenset({"related", "unsure", None})
AT = "2026-11-14T00:00:00+00:00"


def described(
    subject: str,
    detail: str = "",
    what_it_is: str = "photograph",
    cls: str = "not_drawing",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "class": cls,
        "p_plan": 0.1,
        "method": "test",
        "description": {
            "text": f"{subject}.",
            "subject": subject,
            "model": "test",
            "what_it_is": what_it_is,
            "shows_building": True,
            "visible_text": "",
            "detail": detail,
        },
        **extra,
    }


def project(*files: tuple[str, dict[str, Any] | None], pid: str = "p1") -> ProjectStatus:
    found = [
        FileStatus.model_validate(
            {
                "id": f"f{n}",
                "path": path,
                "size": 1,
                "state": "set_aside",
                **({"triage": triage} if triage is not None else {}),
            }
        )
        for n, (path, triage) in enumerate(files, start=1)
    ]
    return ProjectStatus(
        id=pid,
        name="site.zip",
        state="done",
        created_at="2026-11-14T00:00:00+00:00",
        files=tuple(found),
    )


def relevance(verdict: str) -> dict[str, Any]:
    return {"verdict": verdict, "why": "test", "judge": "test"}


# ---------------------------------------------------------------- sources


def test_sources_are_the_described_non_plans_and_nothing_else() -> None:
    register = {
        "kind": "elevation",
        "has_floor_plan": False,
        "photo_of_sheet": False,
        "scale_shown": "bar",
        "quality": "good",
        "method": "test",
    }
    status = project(
        ("plan.pdf", None),  # not triaged (a vector plan)
        ("scan.png", {"class": "floor_plan", "p_plan": 0.9, "method": "t"}),  # a plan
        ("photo.jpg", described("the south facade")),
        ("elev.png", described("an elevation", "", "drawing", "other_drawing", register=register)),
        ("undescribed.jpg", {"class": "not_drawing", "p_plan": 0.1, "method": "t"}),
        ("sheets#p2.pdf", described("a text page", what_it_is="text_page")),
        ("asked.png", described("a scan", read_as_plan={"by": "a person", "at": AT})),
    )
    found = {source.path: source for source in sources(status)}
    assert list(found) == ["photo.jpg", "elev.png", "sheets#p2.pdf"]
    assert found["elev.png"].kind == "elevation"  # the register's kind
    assert found["photo.jpg"].kind == "photograph"  # else what_it_is
    assert found["sheets#p2.pdf"].page == 2
    assert found["photo.jpg"].page == 1


def test_a_persons_overrule_is_the_verdict_and_does_not_change_the_content() -> None:
    judged = described("a cat", relevance=relevance("unrelated"))
    overruled = judged | {"overruled": {"verdict": "related", "by": "a person", "at": AT}}
    (before,) = sources(project(("cat.jpg", judged)))
    (after,) = sources(project(("cat.jpg", overruled)))
    assert (before.verdict, after.verdict) == ("unrelated", "related")
    assert before.content == after.content


def test_the_judges_why_is_not_content_so_judging_again_re_embeds_nothing() -> None:
    (first,) = sources(project(("cat.jpg", described("a cat", relevance=relevance("unrelated")))))
    rejudged = described(
        "a cat", relevance={"verdict": "unsure", "why": "Other words.", "judge": "t"}
    )
    (second,) = sources(project(("cat.jpg", rejudged)))
    assert first.content == second.content


# ---------------------------------------------------------------- fusion


def test_rrf_sums_one_over_k_plus_rank_and_keeps_first_seen_order_on_ties() -> None:
    bm25 = [("a", "a-summary"), ("b", "b-detail-3"), ("c", "c-summary")]
    dense = [("b", "b-summary"), ("d", "d-summary")]
    found = fused([bm25, dense])
    assert [file_id for file_id, _, _ in found] == ["b", "a", "d", "c"]
    scores = {file_id: score for file_id, _, score in found}
    assert scores["b"] == pytest.approx(1 / (RRF_K + 2) + 1 / (RRF_K + 1))
    assert scores["a"] == pytest.approx(1 / (RRF_K + 1))
    tie = fused(
        [[("x", "x-summary"), ("y", "y-summary")], [("y", "y-summary"), ("x", "x-summary")]]
    )
    assert [file_id for file_id, _, _ in tie] == ["x", "y"]
    assert fused([]) == []


def test_a_fused_file_keeps_the_passage_of_the_ranking_that_put_it_highest() -> None:
    bm25 = [("a", "a-summary"), ("b", "b-detail-3")]
    dense = [("b", "b-visible_text-1"), ("a", "a-detail-1")]
    passages = {file_id: passage for file_id, passage, _ in fused([bm25, dense])}
    assert passages == {"a": "a-summary", "b": "b-visible_text-1"}
    same = fused([[("c", "c-detail-1")], [("c", "c-summary")]])
    assert same[0][1] == "c-detail-1"  # equal ranks: the earlier ranking's passage


def test_a_file_one_retriever_puts_first_beats_one_both_rank_tenth() -> None:
    """Why k=5 (decision 0012): a sheet BM25 finds first by its printed number and the embedder
    doesn't rank must not sink below a file both rank around tenth (with k=60 it does)."""
    filler = [(f"x{n}", f"x{n}-summary") for n in range(1, 10)]
    bm25 = [("number", "number-visible_text-1"), *filler, ("both", "both-summary")]
    dense = [*[(f"y{n}", f"y{n}-summary") for n in range(1, 10)], ("both", "both-summary")]
    order = [file_id for file_id, _, _ in fused([bm25, dense])]
    assert order.index("number") < order.index("both")
    assert [f for f, _, _ in fused([bm25, dense], k=60)].index("both") == 0


def test_only_the_first_pool_files_of_each_ranking_count() -> None:
    long = [(f"f{n}", f"f{n}-summary") for n in range(1, 61)]
    assert len(fused([long])) == POOL
    assert [file_id for file_id, _, _ in fused([long], pool=2)] == ["f1", "f2"]


# ---------------------------------------------------------------- the store


def chunker(source: EvidenceSource) -> list[Passage]:
    found = [Passage(part="summary", n=1, text=source.description.subject)]
    found += [
        Passage(part="detail", n=n, text=text)
        for n, text in enumerate(source.description.detail.split("\n\n"), start=1)
    ]
    return found


@dataclass
class Embedder:
    """Bag of letters, L2-normalised: similar words, similar vectors. Counts what it embeds."""

    name: str = "letters-v1"
    label: str = "letters"
    embedded: list[str] = field(default_factory=list[str])

    def embed(self, texts: Sequence[str]) -> NDArray[np.float32]:
        self.embedded += texts
        rows = np.zeros((len(texts), 26), np.float32)
        for i, text in enumerate(texts):
            for char in text.lower():
                if "a" <= char <= "z":
                    rows[i, ord(char) - 97] += 1
        norms = np.maximum(np.linalg.norm(rows, axis=1, keepdims=True), 1e-9)
        return (rows / norms).astype(np.float32)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        return self.embed([text])[0]


def index(tmp_path: Path, embedder: Embedder | None = None) -> SqliteEvidenceIndex:
    return SqliteEvidenceIndex(tmp_path / "projects", chunker, embedder)


SITE = project(
    (
        "facade.jpg",
        described(
            "south facade photo",
            "Red brick wall.\n\nThree windows upstairs.",
            relevance=relevance("related"),
        ),
    ),
    ("cat.jpg", described("a cat on a sofa", "A grey cat.", relevance=relevance("unrelated"))),
    (
        "letter.png",
        described("kirje rakennusvirastolle", "Lupahakemus vuodelta 1962.", what_it_is="text_page"),
    ),
)


def test_update_writes_one_sqlite_file_per_project_and_bm25_finds_words(tmp_path: Path) -> None:
    store = index(tmp_path)
    store.update(SITE)
    assert (tmp_path / "projects" / "p1" / FILE).is_file()
    ((_, best), *_) = store.bm25("p1", "brick facade", KEPT)
    found = store.passage("p1", best)
    assert found is not None
    assert found[1].path == "facade.jpg"
    assert store.bm25("p1", "rakennusvirastolle", KEPT) != []  # Finnish, as printed
    assert store.bm25("p1", "nothing-like-this", KEPT) == []
    assert store.bm25("other", "brick", KEPT) == []  # no index yet: no hits, no file made
    assert not (tmp_path / "projects" / "other").exists()


def test_unrelated_files_are_left_out_unless_asked_for(tmp_path: Path) -> None:
    store = index(tmp_path)
    store.update(SITE)
    assert store.bm25("p1", "cat", KEPT) == []
    ((_, hit), *_) = store.bm25("p1", "cat", ALL)
    found = store.passage("p1", hit)
    assert found is not None and found[1].path == "cat.jpg"


def test_a_query_with_quotes_or_fts_operators_is_words_not_syntax(tmp_path: Path) -> None:
    store = index(tmp_path)
    store.update(SITE)
    for query in ['"brick', "brick AND", "NEAR(brick", "brick*", "-brick", "brick OR"]:
        assert store.bm25("p1", query, KEPT) != [], query
    assert fts_query("  ?! ") is None
    assert fts_query("Brick brick wall") == '"brick" OR "wall"'


def test_bm25_folds_diacritics_both_ways(tmp_path: Path) -> None:
    store = index(tmp_path)
    store.update(
        project(
            ("a.jpg", described("house in Töölö", relevance=relevance("related"))),
            ("b.jpg", described("street in Toolo", relevance=relevance("related"))),
        )
    )
    for query in ["Töölö", "toolo", "TOOLO"]:
        assert {file_id for file_id, _ in store.bm25("p1", query, KEPT)} == {"f1", "f2"}, query


def test_an_unchanged_source_is_not_embedded_again_a_changed_one_is(tmp_path: Path) -> None:
    embedder = Embedder()
    store = index(tmp_path, embedder)
    store.update(SITE)
    first = len(embedder.embedded)
    assert first == 7  # 3 summaries + 4 detail paragraphs
    store.update(SITE)
    assert len(embedder.embedded) == first  # nothing changed: nothing embedded
    changed = project(
        (
            "facade.jpg",
            described("north facade photo", "Grey render.", relevance=relevance("related")),
        ),
        *[
            (f.path, f.triage.model_dump(mode="json", by_alias=True))
            for f in SITE.files[1:]
            if f.triage is not None
        ],
    )
    store.update(changed)
    # each passage is embedded with its file's subject in front
    assert embedder.embedded[first:] == [
        "north facade photo. north facade photo",
        "north facade photo. Grey render.",
    ]
    assert store.bm25("p1", "brick", ALL) == []  # the old passages are gone from FTS too
    assert store.bm25("p1", "render", ALL) != []


def test_a_source_gone_from_the_status_is_dropped(tmp_path: Path) -> None:
    store = index(tmp_path)
    store.update(SITE)
    store.update(
        project(
            *[
                (f.path, f.triage.model_dump(mode="json", by_alias=True))
                for f in SITE.files[:1]
                if f.triage is not None
            ]
        )
    )
    assert store.bm25("p1", "rakennusvirastolle", ALL) == []
    assert store.bm25("p1", "brick", ALL) != []


def test_a_verdict_change_refreshes_the_filter_without_re_embedding(tmp_path: Path) -> None:
    embedder = Embedder()
    store = index(tmp_path, embedder)
    store.update(SITE)
    before = len(embedder.embedded)
    cat = SITE.files[1].triage
    assert cat is not None
    overruled = cat.model_dump(mode="json", by_alias=True) | {
        "overruled": {"verdict": "related", "by": "a person", "at": AT}
    }
    files = [
        (f.path, f.triage.model_dump(mode="json", by_alias=True))
        for f in SITE.files
        if f.triage is not None
    ]
    files[1] = ("cat.jpg", overruled)
    store.update(project(*files))
    assert len(embedder.embedded) == before
    assert store.bm25("p1", "cat", KEPT) != []  # now related: found by default


def test_another_embedder_re_embeds_everything(tmp_path: Path) -> None:
    store = index(tmp_path, Embedder())
    store.update(SITE)
    other = Embedder(name="letters-v2")
    index(tmp_path, other).update(SITE)
    assert len(other.embedded) == 7


def test_dense_ranks_by_cosine_and_filters_verdicts(tmp_path: Path) -> None:
    embedder = Embedder()
    store = index(tmp_path, embedder)
    store.update(SITE)
    (query,) = embedder.embed(["a grey cat"])
    assert "f2" not in dict(store.dense("p1", query, KEPT))  # the cat is unrelated
    ((file_id, best), *_) = store.dense("p1", query, ALL)
    found = store.passage("p1", best)
    assert file_id == "f2" and found is not None and found[1].path == "cat.jpg"
    assert len(store.dense("p1", query, ALL, files=2)) == 2  # files, not passages
    without = index(tmp_path / "no-vectors")
    without.update(SITE)
    assert without.dense("p1", query, ALL) == []  # BM25 only: no vectors stored


def test_ids_are_stable_across_rebuilds_and_lookup_misses_are_none(tmp_path: Path) -> None:
    first = index(tmp_path / "a")
    second = index(tmp_path / "b")
    first.update(SITE)
    second.update(SITE)
    assert first.bm25("p1", "brick", KEPT) == second.bm25("p1", "brick", KEPT)
    assert first.passage("p1", "f99-summary") is None
    assert first.passage("nope", "f99-summary") is None


def test_stale_words_never_match_a_new_passage_that_reuses_a_rowid(tmp_path: Path) -> None:
    """SQLite reuses the highest deleted rowid, so FTS5 must be told what was deleted, or a
    re-described file's old words would find its new passages."""
    store = index(tmp_path)
    store.update(project(("wall.jpg", described("brick wall"))))
    store.update(project(("wall.jpg", described("render wall"))))
    assert store.bm25("p1", "brick", ALL) == []
    assert store.bm25("p1", "render", ALL) != []


def test_a_second_first_open_waits_for_the_writer_instead_of_failing_locked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """K10: the writer holds SQLite's write lock while it embeds; a second sync of the same
    project used to give up after the busy timeout ('database is locked')."""
    import sqlite3
    import threading

    from app.adapters.evidence import store as store_module

    real = sqlite3.connect
    monkeypatch.setattr(
        store_module.sqlite3, "connect", lambda *a, **k: real(*a, **{**k, "timeout": 0.1})
    )
    inside_embed, release, waiting = threading.Event(), threading.Event(), threading.Event()
    guard = getattr(store_module, "_WRITERS_GUARD", None)  # None: no writer lock at all

    class Slow(Embedder):
        def embed(self, texts: Sequence[str]) -> NDArray[np.float32]:
            inside_embed.set()
            assert release.wait(10)
            return super().embed(texts)

    class Seen:
        """Tells when the second writer has passed the registry, so it is next on the writer
        lock (or, without the lock, already failing in SQLite)."""

        def __enter__(self) -> None:
            assert guard is not None
            guard.__enter__()

        def __exit__(self, *error: object) -> None:
            assert guard is not None
            guard.__exit__(*error)
            if threading.current_thread() is second:
                waiting.set()

    store = index(tmp_path, Slow())
    errors: list[BaseException] = []

    def run(status: ProjectStatus) -> None:
        try:
            store.update(status)
        except BaseException as error:  # collected for the assert
            errors.append(error)

    first = threading.Thread(target=run, args=(SITE,))
    second = threading.Thread(target=run, args=(project(("a.jpg", described("a wall"))),))
    first.start()
    assert inside_embed.wait(10)
    if guard is not None:
        monkeypatch.setattr(store_module, "_WRITERS_GUARD", Seen())
    second.start()
    while not waiting.wait(0.01) and second.is_alive():
        pass  # until the second waits on the lock, or has ended (failed)
    release.set()
    first.join(10)
    second.join(10)
    assert errors == []
    assert store.bm25("p1", "wall", ALL) != []
