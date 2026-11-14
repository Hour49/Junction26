"""The sheet-kind signal: Gemini Decisions' 6-way answer to "what is this file's first page?".

One request per uploaded image or PDF (page 1): a `choice` over floor plan / elevation or section
/ schedule / phone photo of a plan / site plan / not a drawing (prototypes/decide2 decision 4,
.agents/exp/decide2.md). It gives ingest two things its content probe cannot see:

- `photo`: P(photo of a plan) >= 0.9. The probe needs camera EXIF to call an image a photo, and
  27 of the 30 real phone photos of plans had none; at 0.9 Gemini flags 26 of 30, and 0 of the
  376 CubiCasa val scans.
- `p_plan`: P(floor plan). Plan vs elevation, section, site plan or schedule sheet: AUROC 0.992
  on 117 labelled drawings. `p_plan_sheet` adds P(photo of a plan), since a photo of a plan is a
  plan: below 0.2 it marked 72 of 73 elevation/section/site/schedule/text sheets and 0 of 452
  plans (46 labelled, 30 phone photos, all 376 CubiCasa val pages).

Replies are cached on disk by the file's sha256, the question version and the model, so a file is
paid for once. On a Decisions error nothing is guessed: `read` returns `KindUnavailable` with
"kind signal not available: <why>", and ingest keeps its probe's answer (a declared degraded
mode, written to the trace). Off unless DECISIONS_KIND is true.
"""

import base64
import hashlib
import io
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.adapters.decisions.client import Decider, DecisionsError
from app.adapters.pdfium_lock import PDFIUM

# Option text = prototypes/decide2/kind.py KINDS, word for word (the A/B measured these words)
KINDS: dict[str, str] = {
    "floor_plan": "a floor plan: rooms, walls, doors and windows seen from above",
    "elevation_section": "an elevation (a facade seen from the side) or a section cut through "
    "the building, or a construction detail",
    "schedule": "a schedule or table sheet: door, window or finish schedules, mostly a table",
    "photo_plan": "a camera photo of a printed or posted plan (perspective, background, glare)",
    "site_plan": "a site plan: the building's outline on its plot with roads, neighbours, trees",
    "not_drawing": "not a drawing: a text document, letter, specification or an ordinary photo",
}
INSTRUCTIONS = "What is this file's first page?"
KEY = "kind"
RESOLUTION = "high"
MAX_SIDE = 3072  # long side of the image sent, in pixels (a PDF page is rendered to it)
PHOTO_AT = 0.9  # P(photo_plan) that flags a photo: 0/376 CubiCasa val scans, 26/30 real photos
UNAVAILABLE = "kind signal not available"


def question() -> dict[str, Any]:
    return {KEY: {"type": "choice", "instructions": INSTRUCTIONS, "criteria": dict(KINDS)}}


QUESTION_SHA = hashlib.sha256(json.dumps(question(), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class KindSignal:
    probs: dict[str, float]  # every kind's probability
    note: str

    @property
    def kind(self) -> str:
        """The most probable kind (a tie goes to the first in KINDS)."""
        return max(KINDS, key=lambda k: self.probs.get(k, 0.0))

    @property
    def photo(self) -> bool:
        return self.probs.get("photo_plan", 0.0) >= PHOTO_AT

    @property
    def p_plan(self) -> float:
        return self.probs.get("floor_plan", 0.0)

    @property
    def p_plan_sheet(self) -> float:
        """P(the page is a plan, drawn or photographed)."""
        return self.p_plan + self.probs.get("photo_plan", 0.0)

    def line(self) -> str:
        """One readable trace line."""
        top = self.kind
        flag = ", photo of a plan" if self.photo else ""
        return (f"sheet kind {top} ({self.probs.get(top, 0.0):.2f}), P(plan) {self.p_plan:.2f}"
                f"{flag}; {self.note}")  # fmt: skip


@dataclass(frozen=True)
class KindUnavailable:
    note: str  # "kind signal not available: <why>"


def page_png(data: bytes) -> bytes:
    """The image sent: a PDF's page 1 rendered, or the image, long side <= MAX_SIDE, as PNG."""
    from PIL import Image

    if data.startswith(b"%PDF-"):
        import pypdfium2

        with PDFIUM:
            pdf = pypdfium2.PdfDocument(data)
            try:
                page = pdf[0]
                width, height = page.get_size()
                image = page.render(scale=MAX_SIDE / max(width, height)).to_pil().convert("RGB")
            finally:
                pdf.close()
    else:
        try:
            image = Image.open(io.BytesIO(data)).convert("RGB")
        except OSError as error:
            raise DecisionsError(f"the file is not an image or PDF: {error}") from None
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def request_body(png: bytes, model: str) -> dict[str, Any]:
    block = {"type": "image", "data": base64.b64encode(png).decode("ascii"),
             "mime_type": "image/png", "resolution": RESOLUTION}  # fmt: skip
    return {"model": model, "input": [block], "questions": question()}


def parse(reply: dict[str, Any]) -> dict[str, float]:
    answers = reply.get("answers")
    answer = answers.get(KEY) if isinstance(answers, dict) else None
    probs = answer.get("probabilities") if isinstance(answer, dict) else None
    if not isinstance(probs, dict) or not set(probs) & set(KINDS):
        raise DecisionsError("the answer has no kind probabilities")
    return {k: float(v) for k, v in probs.items() if k in KINDS}


class KindReader:
    def __init__(self, decider: Decider, cache_dir: Path | None) -> None:
        self._decider = decider
        self._cache = cache_dir

    def read(self, data: bytes) -> KindSignal | KindUnavailable:
        digest = hashlib.sha256(data).hexdigest()
        name = re.sub(r"[^A-Za-z0-9.-]", "_", f"kind-{digest}-{QUESTION_SHA[:12]}-"
                      f"{self._decider.model}-{RESOLUTION}")  # fmt: skip
        path = None if self._cache is None else self._cache / f"{name}.json"
        try:
            if path is not None and path.is_file():
                return KindSignal(parse(json.loads(path.read_text())), f"{self._model} cached")
            start = time.monotonic()
            reply = self._decider.decide(request_body(page_png(data), self._decider.model))
            probs = parse(reply)  # a reply that does not parse is not cached
        except DecisionsError as error:
            return KindUnavailable(f"{UNAVAILABLE}: {error}")
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            part = path.with_suffix(".tmp")
            part.write_text(json.dumps(reply))
            part.replace(path)
        return KindSignal(probs, f"{self._model} in {time.monotonic() - start:.1f} s")

    @property
    def _model(self) -> str:
        return self._decider.model
