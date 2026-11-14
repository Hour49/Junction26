"""What goes into a project's evidence index: one source per described file that is not a floor
plan (decision 0012), built from the project's saved status, so the index can be rebuilt from it
at any time."""

import hashlib
import json
from typing import Literal

from pydantic import ConfigDict, Field

from app.core.ingest.model import (
    PAGE_NUMBER,
    Description,
    EvidenceHow,
    FileStatus,
    ProjectStatus,
    Register,
    Relevance,
    Verdict,
    WhatItIs,
)
from app.core.model import Frozen

PartName = Literal["summary", "detail", "visible_text", "text"]
# The version of the rules that cut and scrub a file's own text and a listed file's passage
# (app/core/contacts.py, file_sources.py's without_addresses and its cut): raise it with any change
# to them, so an index built before re-cuts those sources (rag's review of #272, S4)
TEXT_RULES = "1"


class EvidenceSource(Frozen):
    """One described non-plan file, with what the index shows and filters on."""

    how: EvidenceHow = "described"  # sources v2: also `text` and `listed`
    file_id: str
    path: str
    page: int  # the PDF page a page entry is (`<name>#p<n>.pdf`), else 1
    # the sheet register's kind when the classifier read one, else the evidence step's sheet kind,
    # else `what_it_is`
    kind: str
    what_it_is: WhatItIs
    verdict: Verdict | None  # the person's call, else the judge's; None while not judged
    description: Description
    sheet_register: Register | None  # what the classifier read off the sheet, if it read one
    relevance: Relevance | None
    content: str  # sha256 of what its passages are made from: changes mean re-index
    # sources v2: the probe's kind, and whether `text-n` passages come from the stored file's own
    # text (a text document, or a described drawn PDF's text pages)
    file_kind: str | None = None
    texts: bool = False


def content_of(
    description: Description, kind: str | None, file_sha256: str | None = None, rules: bool = False
) -> str:
    """What the passages are made of: the description and the register's (or the sheet's) kind,
    for a source with `text` passages the file they are read from, and for those and listed files
    the text rules' version. Not the judge's verdict or why, so judging a file or overruling it
    never re-cuts or re-embeds it."""
    body: dict[str, object] = {"description": description.model_dump(mode="json"), "kind": kind}
    if file_sha256 is not None:  # only then: the hashes of described-only sources stay
        body["file"] = file_sha256
    if rules:
        body["text_rules"] = TEXT_RULES
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def sources(status: ProjectStatus) -> tuple[EvidenceSource, ...]:
    """The project's files that are not floor plans, in file order: each one triage set aside and
    described (a file a person had read as a floor plan is one now, so it is left out), and each
    one the evidence step indexed (EVIDENCE_SCOPE=all_non_plan, decision 0012 sources v2)."""
    found: list[EvidenceSource] = []
    for file in status.files:
        source = _set_aside(file) or _indexed(file)
        if source is not None:
            found.append(source)
    return tuple(found)


def _page(file: FileStatus) -> int:
    page = PAGE_NUMBER.search(file.path)
    return int(page[1]) if page else 1


def _set_aside(file: FileStatus) -> EvidenceSource | None:
    triage = file.triage
    if triage is None or triage.description is None or triage.class_ == "floor_plan":
        return None
    if triage.read_as_plan is not None:
        return None
    description, register = triage.description, triage.register_
    kind = register.kind if register is not None else None
    return EvidenceSource(
        file_id=file.id,
        path=file.path,
        page=_page(file),
        kind=kind or description.what_it_is,
        what_it_is=description.what_it_is,
        verdict=triage.verdict,
        description=description,
        sheet_register=register,
        relevance=triage.relevance,
        content=content_of(description, kind),
    )


def _indexed(file: FileStatus) -> EvidenceSource | None:
    """A file the evidence step indexed: a picture it described (its kind is the sheet kind that
    made it a source; a register beside it may come from a triage that called the file a plan), a
    text document, or a file listed by name. Text and listed files carry a description made by
    rule. No verdict: the judge works on triage records."""
    evidence = file.evidence
    if evidence is None or not evidence.indexed or evidence.how is None:
        return None
    description = evidence.description
    assert description is not None  # FileEvidence: an indexed file has its description
    kind = evidence.kind
    texts = evidence.text_pages is not None
    return EvidenceSource(
        how=evidence.how,
        file_id=file.id,
        path=file.path,
        page=_page(file),
        kind=kind or description.what_it_is,
        what_it_is=description.what_it_is,
        verdict=None,
        description=description,
        sheet_register=None,
        relevance=None,
        content=content_of(
            description, kind, file.sha256 if texts else None, texts or evidence.how == "listed"
        ),
        file_kind=file.kind,
        texts=texts,
    )


class Passage(Frozen):
    """One searchable piece of a source; how a source is cut is the chunker's (decision 0012)."""

    part: PartName  # which field it comes from
    n: int = Field(ge=1)  # its place among the source's passages of that part, from 1
    text: str
    page: int = Field(default=1, ge=1)  # a `text` passage: the PDF page it comes from


# ---------------------------------------------------------------- what the tools and REST return
# The contract: .agents/exp/rag-evidence.md section 1 (rag, v1). The same JSON for both.


class HitWhy(Frozen):
    terms: tuple[str, ...]  # the query's words found in the passage; empty: by meaning only
    bm25_rank: int | None  # the file's rank by BM25; None: not returned, or not run
    dense_rank: int | None  # the file's rank by the embedder; None: not returned, or not run


class EvidenceHit(Frozen):
    id: str  # f7-summary, f7-detail-2, f7-visible_text-1
    file_id: str
    file: str  # the path as uploaded
    page: int
    part: PartName
    how: EvidenceHow  # described, text (the file's own text), listed (by name only; not read)
    kind: str  # the register's kind, else the sheet kind, else what_it_is; never floor_plan
    subject: str
    snippet: str  # <= 300 characters of the passage, around the matched words
    language: str | None
    verdict: Verdict | None
    credit: str | None
    score: float  # orders the hits of one result only
    why: HitWhy


class EvidenceSearch(Frozen):
    query: str
    method: str  # which retrieval ran, in plain words
    indexed_files: int
    unrelated_left_out: int  # files skipped as unrelated; 0 with include_unrelated
    note: str | None  # one sentence when nothing is indexed
    hits: tuple[EvidenceHit, ...]


class DescriptionView(Frozen):
    """The file's description as the tools show it (its cost left out)."""

    subject: str
    text: str
    detail: str
    visible_text: str
    text_seen: tuple[str, ...]
    language: str | None
    what_it_is: WhatItIs
    shows_building: bool
    model: str


class EvidenceDetail(Frozen):
    """`register` is a pydantic model attribute, so the field is `register_` under `register`."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        serialize_by_alias=True,
        validate_by_name=True,
        validate_by_alias=True,
    )

    id: str
    file_id: str
    file: str
    page: int
    part: PartName
    how: EvidenceHow
    text: str  # the whole passage
    kind: str
    verdict: Verdict | None
    credit: str | None
    description: DescriptionView
    register_: Register | None = Field(alias="register")
    relevance: Relevance | None
