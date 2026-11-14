"""How a source is cut into passages (decision 0012). A stand-in until rag specifies chunking:
one summary passage (subject, the short text, why it belongs to the project), then the long
description and the printed text, each in passages of about `SIZE` characters cut at paragraph
and then sentence ends. Numbering: summary is one passage; the others count from 1."""

import re

from app.core.evidence.model import EvidenceSource, PartName, Passage

SIZE = 600
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def pieces(text: str, size: int = SIZE) -> list[str]:
    """`text` in pieces of at most about `size` characters, cut at blank lines, then at sentence
    ends; a sentence longer than `size` is its own piece."""
    found: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        current = ""
        for sentence in SENTENCE.split(paragraph.strip()):
            if current and len(current) + 1 + len(sentence) > size:
                found.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            found.append(current)
    return found


def passages(source: EvidenceSource) -> list[Passage]:
    described = source.description
    summary = f"{described.subject}. {described.text}"
    if source.relevance is not None:
        summary += f" {source.relevance.why}"
    found = [Passage(part="summary", n=1, text=summary)]
    parts: tuple[tuple[PartName, str], ...] = (
        ("detail", described.detail),
        ("visible_text", described.visible_text),
    )
    for part, text in parts:
        found += [Passage(part=part, n=n, text=piece) for n, piece in enumerate(pieces(text), 1)]
    return found
