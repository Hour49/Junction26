"""G1main: Gemini Decisions' count distribution for the 12 CubiCasa count families of one page.

One request per page: for each family a `choice` question over 0..K (K = the train split's largest
answer), worded as Stoa's English question plus "count only the main dwelling" (prototypes/decide
arm G1main-high; .agents/exp/decide.md). The reply gives, per family, the probability of every
count, so one call yields both Gemini's own count and its probability for any other count.

Replies are cached on disk under the image's sha256, the question set's hash and the model, so a
page is paid for once whichever use asks first.
"""

import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.adapters.decisions.client import Decider, DecisionsError

RESOLUTION = "high"  # val: no gain from ultra_high (G1-ultra_high -1.0 pp vs high)
MAIN_DWELLING = (
    " Count only the main dwelling the plan is about, drawn in full; ignore parts of neighbouring "
    "apartments or buildings cut off by the image edge."
)
# family (as the template parser names it) -> (question key, Stoa's English question, K)
FAMILIES: dict[str, tuple[str, str, int]] = {
    "door": ("door", "How many doors are shown on this floor plan? Count doorways fitted with a "
             "door; open doorways without a door leaf do not count.", 43),
    "window": ("window", "How many windows are shown on this floor plan?", 88),
    "sink": ("sink", "How many sinks and wash basins (kitchen and bathroom combined; a "
             "double-bowl sink counts as one) are drawn on this floor plan?", 10),
    "toilet": ("toilet", "How many toilet bowls (WC seats) are drawn on this floor plan?", 11),
    "shower+bathtub": ("shower_bathtub", "How many showers and bathtubs are drawn on this floor "
                       "plan in total?", 6),
    "sauna": ("sauna", "How many saunas are on this floor plan?", 2),
    "plan": ("plan", "How many floors (storeys) does this floor plan show?", 4),
    "room:kitchen": ("kitchen", "How many kitchens (including kitchenettes, open kitchens and "
                     "utility kitchens) are on this floor plan?", 4),
    "room:bedroom": ("bedroom", "How many bedrooms (makuuhuone, usually marked MH) are on this "
                     "floor plan?", 9),
    "room:bathroom": ("bathroom", "How many bathrooms or washrooms (e.g. KH, KPH, PH, PESUH, SH) "
                      "are on this floor plan, not counting separate WC rooms?", 4),
    "room:wc": ("wc", "How many separate WC rooms (toilet rooms marked WC) are on this floor "
                "plan?", 7),
    "room:balcony": ("balcony", "How many balconies (parveke, including glazed balconies) are on "
                     "this floor plan?", 2),
}  # fmt: skip
MIME = {b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg", b"RIFF": "image/webp"}


def questions() -> dict[str, dict[str, Any]]:
    return {
        f"g1_{key}": {
            "type": "choice",
            "instructions": text + MAIN_DWELLING,
            "criteria": {str(k): "" for k in range(top + 1)},
        }
        for key, text, top in FAMILIES.values()
    }


QUESTIONS_SHA = hashlib.sha256(json.dumps(questions(), sort_keys=True).encode()).hexdigest()


def mime_of(data: bytes) -> str:
    for magic, mime in MIME.items():
        if data.startswith(magic) and (mime != "image/webp" or data[8:12] == b"WEBP"):
            return mime
    raise DecisionsError("the page is not a PNG, JPEG or WebP image")


def request_body(image: bytes, model: str) -> dict[str, Any]:
    block = {"type": "image", "data": base64.b64encode(image).decode("ascii"),
             "mime_type": mime_of(image), "resolution": RESOLUTION}  # fmt: skip
    return {"model": model, "input": [block], "questions": questions()}


def request_key(body: dict[str, Any]) -> str:
    """The image's sha256 (the question set is fixed per QUESTIONS_SHA)."""
    return hashlib.sha256(base64.b64decode(body["input"][0]["data"])).hexdigest()


@dataclass(frozen=True)
class CountDist:
    """Gemini's distribution over one family's count."""

    probs: dict[int, float]

    @property
    def top(self) -> int:
        """The most probable count; a tie goes to the smaller count."""
        return max(sorted(self.probs), key=lambda k: self.probs[k])

    def p(self, value: int) -> float:
        return self.probs.get(value, 0.0)


@dataclass(frozen=True)
class PageCounts:
    families: dict[str, CountDist]
    note: str


def parse(reply: dict[str, Any]) -> dict[str, CountDist]:
    out: dict[str, CountDist] = {}
    answers = reply.get("answers")
    if not isinstance(answers, dict):
        raise DecisionsError("the answer has no answers")
    for family, (key, _, _) in FAMILIES.items():
        answer = answers.get(f"g1_{key}")
        probs = answer.get("probabilities") if isinstance(answer, dict) else None
        if not isinstance(probs, dict) or not probs:
            raise DecisionsError(f"the answer has no probabilities for {family}")
        out[family] = CountDist({int(k): float(v) for k, v in probs.items()})
    return out


class G1MainReader:
    def __init__(self, decider: Decider, cache_dir: Path | None) -> None:
        self._decider = decider
        self._cache = cache_dir

    def read(self, image: bytes) -> PageCounts:
        """Raises `DecisionsError` when the API gives no usable answer (nothing is cached)."""
        digest = hashlib.sha256(image).hexdigest()
        name = re.sub(r"[^A-Za-z0-9.-]", "_", f"{digest}-{QUESTIONS_SHA[:12]}-"
                      f"{self._decider.model}-{RESOLUTION}")  # fmt: skip
        path = None if self._cache is None else self._cache / f"{name}.json"
        if path is not None and path.is_file():
            reply, how = json.loads(path.read_text()), "cached reply"
        else:
            start = time.monotonic()
            reply = self._decider.decide(request_body(image, self._decider.model))
            how = f"read in {time.monotonic() - start:.1f} s"
            families = parse(reply)  # a reply that does not parse is not cached
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                part = path.with_suffix(".tmp")
                part.write_text(json.dumps(reply))
                part.replace(path)
            return PageCounts(families, f"{self._decider.model}: 12 count families, {how}")
        return PageCounts(parse(reply), f"{self._decider.model}: 12 count families, {how}")
