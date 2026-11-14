"""A source's passages by how it is indexed (decision 0012 sources v2, report 7.4):

- `described`: the chunker's (`summary`, `detail-n`, `visible_text-n`), exactly as before, plus a
  drawn PDF's own text pages as `text-n` when it has them;
- `text`: the file's text as cut by `text_source` (`summary`, then `text-n`, each with its page);
- `listed`: one `summary`, the rule-made description's text (it names the file and says why its
  content is not read)."""

from collections.abc import Callable, Sequence

from app.core.evidence.file_sources import TextSource
from app.core.evidence.model import EvidenceSource, Passage

Chunker = Callable[[EvidenceSource], Sequence[Passage]]


def source_passages(
    source: EvidenceSource, chunker: Chunker, text: TextSource | None
) -> list[Passage]:
    """`text`: the file's own text when `source.texts` (None: it could not be read again)."""
    if source.how == "listed":
        return [Passage(part="summary", n=1, text=source.description.text)]
    found = list(chunker(source)) if source.how == "described" else []
    if text is not None:
        pieces = text.pieces if source.how == "text" else text.pieces[1:]  # one summary
        found += [Passage(part=p.part, n=p.n, text=p.text, page=p.page) for p in pieces]
    return found
