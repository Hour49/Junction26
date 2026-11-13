"""Stage 7: the route's extractor reads the group's richest source and places what it found on
the sheet. The extractors are adapters (the `Extractor` port), one per route."""

from collections.abc import Mapping

from app.core.pipeline.model import Extracted, Route, Routed, Sheet
from app.core.pipeline.ports import Extractor


def extract(routed: Routed, sheet: Sheet, extractors: Mapping[Route, Extractor]) -> Extracted:
    return extractors[routed.route].extract(routed.source, sheet)
