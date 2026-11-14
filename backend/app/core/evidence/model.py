"""What goes into a project's evidence index: one source per described file that is not a floor
plan (decision 0012), built from the project's saved status, so the index can be rebuilt from it
at any time."""

import hashlib
import json

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

    part: str  # which field it comes from, e.g. "summary", "detail", "visible_text"
    n: int  # its place among the source's passages of that part, from 0
    text: str
