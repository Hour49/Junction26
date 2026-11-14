"""The Carbon reader of raster drawings (brief r8 AS-2; .agents/exp/carbon-reader.md):
gemini-4-carbon reads page 1 whole and in full-resolution tiles. contract.py is what is asked and
how the replies become a drawing; reader.py makes the calls. `CarbonSwitch` (CARBON_READER) sends
a raster drawing to it or to the shipped reader.
"""

from collections.abc import Callable

from app.adapters.carbon.reader import CarbonClient, CarbonExtractor, CarbonReader
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor

__all__ = ["CarbonClient", "CarbonExtractor", "CarbonReader", "CarbonSwitch"]


class CarbonSwitch:
    """CARBON_READER: a drawing `use_carbon` says yes to (by its path) is read by Carbon alone,
    every other by the shipped reader. Ingest flags the first kind with the same `use_carbon`
    (composition `Pipeline.carbon_read`)."""

    def __init__(
        self, other: Extractor, carbon: Extractor, use_carbon: Callable[[str], bool]
    ) -> None:
        self._other = other
        self._carbon = carbon
        self._use_carbon = use_carbon

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        reader = self._carbon if self._use_carbon(source.path) else self._other
        return reader.extract(source, sheet)
