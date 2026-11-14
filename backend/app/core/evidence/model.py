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
    ProjectStatus,
    Register,
    Relevance,
    Verdict,
    WhatItIs,
)
from app.core.model import Frozen

PartName = Literal["summary", "detail", "visible_text"]


class EvidenceSource(Frozen):
    """One described non-plan file, with what the index shows and filters on."""

    file_id: str
    path: str
    page: int  # the PDF page a page entry is (`<name>#p<n>.pdf`), else 1
    kind: str  # the sheet register's kind when the classifier read one, else `what_it_is`
    what_it_is: WhatItIs
    verdict: Verdict | None  # the person's call, else the judge's; None while not judged
    description: Description
    sheet_register: Register | None  # what the classifier read off the sheet, if it read one
    relevance: Relevance | None
    content: str  # sha256 of what its passages are made from: changes mean re-index


def content_of(description: Description, register: Register | None) -> str:
    """What the passages are made of: the description and the register's kind. Not the judge's
    verdict or why, so judging a file or overruling it never re-cuts or re-embeds it."""
    body = {
        "description": description.model_dump(mode="json"),
        "kind": None if register is None else register.kind,
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def sources(status: ProjectStatus) -> tuple[EvidenceSource, ...]:
    """The project's described files that are not floor plans, in file order. A file a person had
    read as a floor plan is one now, so it is left out."""
    found: list[EvidenceSource] = []
    for file in status.files:
        triage = file.triage
        if triage is None or triage.description is None or triage.class_ == "floor_plan":
            continue
        if triage.read_as_plan is not None:
            continue
        page = PAGE_NUMBER.search(file.path)
        description, register = triage.description, triage.register_
        found.append(
            EvidenceSource(
                file_id=file.id,
                path=file.path,
                page=int(page[1]) if page else 1,
                kind=register.kind if register is not None else description.what_it_is,
                what_it_is=description.what_it_is,
                verdict=triage.verdict,
                description=description,
                sheet_register=register,
                relevance=triage.relevance,
                content=content_of(description, register),
            )
        )
    return tuple(found)


class Passage(Frozen):
    """One searchable piece of a source; how a source is cut is the chunker's (decision 0012)."""

    part: PartName  # which field it comes from
    n: int = Field(ge=1)  # its place among the source's passages of that part, from 1
    text: str


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
    kind: str  # the register's kind, else what_it_is; never floor_plan
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
    text: str  # the whole passage
    kind: str
    verdict: Verdict | None
    credit: str | None
    description: DescriptionView
    register_: Register | None = Field(alias="register")
    relevance: Relevance | None
