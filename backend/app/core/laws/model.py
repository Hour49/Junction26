"""A law of the knowledge base: one file per law, one clause per subsection (decision 0011).

A law is data (backend/app/laws/<pack>/<law id>.json). Validating it here refuses a clause nobody
could cite or find: no verbatim text, no English summary, too few keywords, a topic outside the
closed list, an id that does not name its law.
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.core.model import Frozen

Pack = Literal["fi", "ch-zh"]  # the ids of decision 0009's rule packs
PACKS: tuple[Pack, ...] = ("fi", "ch-zh")
Jurisdiction = Literal["FI", "CH", "CH-ZH"]
JURISDICTIONS: dict[str, tuple[str, ...]] = {"fi": ("FI",), "ch-zh": ("CH", "CH-ZH")}
Language = Literal["fi", "sv", "de", "fr", "it", "en"]
Topic = Literal[
    "rooms",
    "accessibility",
    "fire",
    "escape-routes",
    "stairs-railings",
    "doors-windows",
    "ventilation",
    "energy",
    "sound",
    "moisture",
    "structure",
    "daylight",
    "parking",
    "outdoor",
    "distances-heights",
    "permits-procedure",
    "general",
]
TOPICS: tuple[Topic, ...] = Topic.__args__  # pyright: ignore[reportAttributeAccessIssue]
DATE = r"^\d{4}-\d{2}-\d{2}$"
ID = r"^[a-z0-9][a-z0-9-]*$"
Text = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]  # not blank


class Limit(Frozen):
    """A number a drawing could be checked against: "habitable room area >= 7 m2"."""

    what: Text
    comparison: Literal[">=", ">", "<=", "<", "="]
    value: float
    unit: Text


class LawClause(Frozen):
    """One subsection (momentti, Absatz): `text` verbatim from the official source, `text_en` our
    unofficial translation (null only when the law is in English)."""

    id: str = Field(pattern=ID)  # "<law id>-<section>-<subsection>"
    ref: Text  # as a lawyer cites it: "4 § 2 mom.", "§ 12 Abs. 1"
    heading: Text | None = None
    heading_en: Text | None = None
    text: Text
    text_en: Text | None = None
    summary_en: Text  # one plain sentence, written for search
    keywords: tuple[Text, ...] = Field(min_length=3, max_length=12)  # English and original terms
    topics: tuple[Topic, ...] = Field(min_length=1)
    limits: tuple[Limit, ...] = ()
    drawing_checkable: bool


class Law(Frozen):
    id: str = Field(pattern=ID)  # the file name without .json
    pack: Pack
    jurisdiction: Jurisdiction  # Swiss federal law in the ch-zh pack is "CH"
    number: Text
    title: Text
    title_en: Text
    url: str = Field(pattern=r"^https://\S+$")
    language: Language
    in_force: str | None = Field(default=None, pattern=DATE)
    checked: str = Field(pattern=DATE)  # the day someone read it at `url`
    status_note: str | None = None
    clauses: tuple[LawClause, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> "Law":
        if self.jurisdiction not in JURISDICTIONS[self.pack]:
            raise ValueError(f"jurisdiction {self.jurisdiction} is not of pack {self.pack}")
        seen: set[str] = set()
        for clause in self.clauses:
            if not clause.id.startswith(f"{self.id}-"):
                raise ValueError(f"clause {clause.id} does not start with {self.id}-")
            if clause.id in seen:
                raise ValueError(f"clause {clause.id} twice")
            seen.add(clause.id)
            if clause.text_en is None and self.language != "en":
                raise ValueError(f"clause {clause.id}: text_en is needed for a {self.language} law")
        return self


class SearchHit(Frozen):
    id: str
    law_id: str
    ref: str
    title_en: str  # the law's
    summary_en: str
    url: str  # the law's page, to cite
    score: float  # higher is better (-bm25)


class ClauseView(LawClause):
    """A clause with what citing it needs from its law."""

    law_id: str
    law_number: str
    law_title: str
    law_title_en: str
    url: str
    language: Language
    checked: str
    status_note: str | None


class TocEntry(Frozen):
    """One line of a pack's table of contents: what exists, for the prompt and the screen."""

    law_id: str
    number: str
    title_en: str
    clauses: int
    topics: list[Topic]


def clause_view(law: Law, clause: LawClause) -> ClauseView:
    return ClauseView(
        **clause.model_dump(),
        law_id=law.id,
        law_number=law.number,
        law_title=law.title,
        law_title_en=law.title_en,
        url=law.url,
        language=law.language,
        checked=law.checked,
        status_note=law.status_note,
    )


def toc_entry(law: Law) -> TocEntry:
    used = {topic for clause in law.clauses for topic in clause.topics}
    return TocEntry(
        law_id=law.id,
        number=law.number,
        title_en=law.title_en,
        clauses=len(law.clauses),
        topics=[topic for topic in TOPICS if topic in used],
    )
