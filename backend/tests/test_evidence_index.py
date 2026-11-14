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
from app.core.evidence.fusion import RRF_K, fused
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


# ---------------------------------------------------------------- fusion


def test_rrf_sums_one_over_k_plus_rank_and_keeps_first_seen_order_on_ties() -> None:
    found = fused([["a", "b", "c"], ["b", "d"]])
    assert [name for name, _ in found] == ["b", "a", "d", "c"]
    scores = dict(found)
    assert scores["b"] == pytest.approx(1 / (RRF_K + 2) + 1 / (RRF_K + 1))
    assert scores["a"] == pytest.approx(1 / (RRF_K + 1))
    assert fused([["x", "y"], ["y", "x"]]) == [
        ("x", pytest.approx(scores["b"])),
        ("y", pytest.approx(scores["b"])),
    ]
    assert fused([]) == []


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
    (best, *_) = store.bm25("p1", "brick facade", 5, KEPT)
    found = store.passage("p1", best)
    assert found is not None
    assert found[1].path == "facade.jpg"
    assert store.bm25("p1", "rakennusvirastolle", 5, KEPT) != []  # Finnish, as printed
    assert store.bm25("p1", "nothing-like-this", 5, KEPT) == []
    assert store.bm25("other", "brick", 5, KEPT) == []  # no index yet: no hits, no file made
    assert not (tmp_path / "projects" / "other").exists()


def test_unrelated_files_are_left_out_unless_asked_for(tmp_path: Path) -> None:
    store = index(tmp_path)
    store.update(SITE)
    assert store.bm25("p1", "cat", 5, KEPT) == []
    (hit, *_) = store.bm25("p1", "cat", 5, ALL)
    found = store.passage("p1", hit)
    assert found is not None and found[1].path == "cat.jpg"


def test_a_query_with_quotes_or_fts_operators_is_words_not_syntax(tmp_path: Path) -> None:
    store = index(tmp_path)
    store.update(SITE)
    for query in ['"brick', "brick AND", "NEAR(brick", "brick*", "-brick", "brick OR"]:
        assert store.bm25("p1", query, 5, KEPT) != [], query
    assert fts_query("  ?! ") is None
    assert fts_query("Brick brick wall") == '"brick" OR "wall"'


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
    assert embedder.embedded[first:] == ["north facade photo", "Grey render."]
    assert store.bm25("p1", "brick", 5, ALL) == []  # the old passages are gone from FTS too
    assert store.bm25("p1", "render", 5, ALL) != []


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
    assert store.bm25("p1", "rakennusvirastolle", 5, ALL) == []
    assert store.bm25("p1", "brick", 5, ALL) != []


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
    assert store.bm25("p1", "cat", 5, KEPT) != []  # now related: found by default


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
    assert store.dense("p1", query, 1, KEPT) != []
    (best,) = store.dense("p1", query, 1, ALL)
    found = store.passage("p1", best)
    assert found is not None and found[0].text == "A grey cat."
    without = index(tmp_path / "no-vectors")
    without.update(SITE)
    assert without.dense("p1", query, 5, ALL) == []  # BM25 only: no vectors stored


def test_ids_are_stable_across_rebuilds_and_lookup_misses_are_none(tmp_path: Path) -> None:
    first = index(tmp_path / "a")
    second = index(tmp_path / "b")
    first.update(SITE)
    second.update(SITE)
    assert first.bm25("p1", "brick", 5, KEPT) == second.bm25("p1", "brick", 5, KEPT)
    assert first.passage("p1", "f99-summary") is None
    assert first.passage("nope", "f99-summary") is None


def test_stale_words_never_match_a_new_passage_that_reuses_a_rowid(tmp_path: Path) -> None:
    """SQLite reuses the highest deleted rowid, so FTS5 must be told what was deleted, or a
    re-described file's old words would find its new passages."""
    store = index(tmp_path)
    store.update(project(("wall.jpg", described("brick wall"))))
    store.update(project(("wall.jpg", described("render wall"))))
    assert store.bm25("p1", "brick", 5, ALL) == []
    assert store.bm25("p1", "render", 5, ALL) != []
