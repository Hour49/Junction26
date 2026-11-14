"""RESOLVER=carbon: the Resolver port (app/core/review/ports.py) on Google's gemini-4-carbon.

One call per request: the question, the values in dispute with who read them, and the drawing as
images (each page the spots are on, small, then one crop per spot with the box drawn in red).
The model answers in JSON: it picks a value, or says it can't tell, with one sentence why.

- Price: 4 USD per million input tokens, 20 per million output tokens, thinking billed as output
  (orchestrator, 2026-11-14; not checked against Google's billing). Every paid call is charged to
  the process's Gemini ledger (GEMINI_BUDGET_USD, app/core/spend.py) and the thread's trace
  (app/core/cost.py), also when its reply is unusable.
- Replies are cached on disk by the request's JSON, the model and the prompt version, so a
  request is paid for once; a cached reply costs nothing and renders no page.
- A failed call (budget used up, HTTP error, timeout, a reply that is not the form, a page that
  can't be rendered) is `ResolverUnavailable` with the reason; nothing is cached and nothing is
  guessed.
"""

import base64
import hashlib
import http.client
import io
import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
from pydantic import ValidationError

from app.adapters.raster_ocr.gemini import URL, GeminiError, _status, reply_text
from app.adapters.whole_file import write_whole
from app.core import cost
from app.core.errors import InvalidInputError, NotFoundError
from app.core.pipeline.model import ValueMark
from app.core.review.model import Resolved, ResolveRequest, ResolverUnavailable, Spot
from app.core.spend import SpendGuard

log = logging.getLogger(__name__)

MODEL = "gemini-4-carbon"
USD_PER_M_INPUT = 4.00
USD_PER_M_OUTPUT = 20.00
PROMPT_VERSION = "carbon-1"  # change it with PROMPT, SCHEMA or the images: the cache key holds it
TEMPERATURE = 0.0
MAX_TOKENS = 8192
PAGE_SIDE = 1536  # px: a whole page, long side
CROP_SIDE = 1024  # px: a crop, long side at most (never enlarged past the rendered page)
CONTEXT = 0.06  # page fraction kept around a spot's box on each side, at least
JPEG_QUALITY = 90
UNAVAILABLE = "Carbon could not answer"

PROMPT = {
    "conflict": (
        "You check a quantity takeoff of a building drawing. Two methods read different values "
        "for the same quantity and no rule decides between them. Look at the drawing images and "
        "pick the value that is right, exactly as one of the values listed, or say you can't "
        "tell. Pick only when the drawing shows it; when the images don't settle it, answer "
        "cannot_tell."
    ),
    "answer": (
        "You check an answer read from a building drawing. The reader is not sure of it. Look at "
        "the drawing images and give the right value: the same value when the drawing confirms "
        "it, another when the drawing shows another, or cannot_tell when the images don't "
        "settle it."
    ),
}
RULES = (
    'Answer as JSON: {"verdict": "picked" or "cannot_tell", "value": the number (null with '
    'cannot_tell), "reason": one plain sentence for the person who reviews the takeoff, saying '
    "what in the drawing decides it}. The red box in a crop marks the place to look at."
)
SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "verdict": {"type": "STRING", "enum": ["picked", "cannot_tell"]},
        "value": {"type": "NUMBER", "nullable": True},
        "reason": {"type": "STRING"},
    },
    "required": ["verdict", "value", "reason"],
    "propertyOrdering": ["reason", "verdict", "value"],  # it says why before it decides
}

Page = Callable[[int], bytes]
Transport = Callable[[urllib.request.Request, float], dict[str, Any]]


def price(answer: dict[str, Any]) -> float:
    """Dollars of one reply from its `usageMetadata` at Carbon's price; 0 when it has none."""
    usage = answer.get("usageMetadata") or {}
    tokens_in = int(usage.get("promptTokenCount", 0))
    tokens_out = int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0))
    return (tokens_in * USD_PER_M_INPUT + tokens_out * USD_PER_M_OUTPUT) / 1e6


def _urlopen(request: urllib.request.Request, timeout: float) -> dict[str, Any]:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


class CarbonClient:
    """generateContent on Carbon; `transport` sends the request (a fake in tests)."""

    def __init__(
        self,
        api_key: str,
        timeout_s: float,
        model: str = MODEL,
        budget: SpendGuard | None = None,
        transport: Transport = _urlopen,
    ) -> None:
        if not api_key:
            raise InvalidInputError("GEMINI_API_KEY is empty: RESOLVER=carbon needs a key")
        self._key = api_key
        self.model = model
        self._timeout = timeout_s
        self._budget = budget  # GEMINI_BUDGET_USD; None: no limit
        self._send = transport

    def __repr__(self) -> str:
        return f"CarbonClient({self.model})"

    def ask(self, parts: list[dict[str, Any]]) -> dict[str, Any]:
        """The generateContent answer to `parts`; raises `GeminiError`."""
        if self._budget is not None and (refused := self._budget.exhausted()):
            raise GeminiError(refused)
        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": TEMPERATURE,
                "maxOutputTokens": MAX_TOKENS,
                "responseMimeType": "application/json",
                "responseSchema": SCHEMA,
            },
        }
        request = urllib.request.Request(
            f"{URL}/{self.model}:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._key},
        )
        try:
            answer = self._send(request, self._timeout)
        except urllib.error.HTTPError as error:
            raise GeminiError(f"HTTP {error.code} {_status(error)}".strip()) from None
        except (OSError, http.client.HTTPException) as error:  # URLError, timeouts, resets
            raise GeminiError(f"no answer: {type(error).__name__}") from None
        except json.JSONDecodeError:
            raise GeminiError("the answer is not JSON") from None
        if self._budget is not None:
            self._budget.charge(price(answer), "resolver")
        return answer


class CarbonResolver:
    """The Resolver port on a Carbon client, its replies cached in `cache_dir`."""

    def __init__(
        self,
        client: CarbonClient,
        cache_dir: Path,
        clock: Callable[[], str] = lambda: datetime.now(UTC).isoformat(timespec="seconds"),
    ) -> None:
        self._client = client
        self._cache = cache_dir
        self._clock = clock

    def resolve(self, request: ResolveRequest, page: Page) -> Resolved | ResolverUnavailable:
        key = f"{request.model_dump_json()}\0{self._client.model}\0{PROMPT_VERSION}"
        path = self._cache / f"{hashlib.sha256(key.encode()).hexdigest()}.json"
        if path.is_file():
            try:
                return Resolved.model_validate_json(json.loads(path.read_text())["resolved"])
            except (OSError, ValueError, KeyError, TypeError) as error:
                log.warning("cached reply %s unreadable (%s): asked again", path.name, error)
        try:
            parts = request_parts(request, page)
        except (NotFoundError, InvalidInputError, OSError, ValueError) as error:
            return ResolverUnavailable(note=f"{UNAVAILABLE}: the page could not be shown ({error})")
        try:
            answer = self._client.ask(parts)
        except GeminiError as error:
            return ResolverUnavailable(note=f"{UNAVAILABLE}: {error}")
        usd = price(answer)
        cost.charge(usd)  # paid for even when the reply is unusable
        try:
            form = json.loads(reply_text(answer))
            found = Resolved(
                verdict=form["verdict"],
                value=form["value"] if form["verdict"] == "picked" else None,
                reason=str(form["reason"]).strip(),
                marks=tuple(_looked(spot) for spot in request.spots),
                by=f"carbon:{self._client.model}",
                at=self._clock(),
            )
        except GeminiError as error:
            return ResolverUnavailable(note=f"{UNAVAILABLE}: {error}")
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError):
            return ResolverUnavailable(note=f"{UNAVAILABLE}: the reply is not the form")
        stored = {"resolved": found.model_dump_json(), "usage": answer.get("usageMetadata", {}),
                  "usd": usd, "model": self._client.model, "prompt": PROMPT_VERSION}  # fmt: skip
        write_whole(path, json.dumps(stored, ensure_ascii=False))
        return found


def _looked(spot: Spot) -> ValueMark:
    return ValueMark(page=spot.page, box=spot.box, label=spot.why)


def request_parts(request: ResolveRequest, page: Page) -> list[dict[str, Any]]:
    """The prompt and the images: each page the spots are on, then a crop per spot."""
    unit = "" if request.unit == "count" else f" {request.unit}"
    lines = [
        PROMPT[request.kind],
        "",
        f"Question: {request.question}",
        "Values:",
        *(
            f"- {candidate.value}{unit}, read by {candidate.source}"
            f" ({len(candidate.marks)} places marked)"
            for candidate in request.candidates
        ),
        "",
        RULES,
    ]
    parts: list[dict[str, Any]] = [{"text": "\n".join(lines)}]
    rendered: dict[int, Image.Image] = {}
    for number in sorted({spot.page for spot in request.spots}):
        rendered[number] = Image.open(io.BytesIO(page(number))).convert("RGB")
        parts += [{"text": f"The whole page {number}:"}, _jpeg(_fit(rendered[number], PAGE_SIDE))]
    for at, spot in enumerate(request.spots, 1):
        parts += [
            {"text": f"Crop {at}, page {spot.page}: {spot.why}"},
            _jpeg(crop(rendered[spot.page], spot)),
        ]
    return parts


def crop(image: Image.Image, spot: Spot) -> Image.Image:
    """The spot's place with CONTEXT around it (more for a small box), the box drawn in red."""
    x0, y0, x1, y1 = (float(value) for value in spot.box)
    pad_x = max(CONTEXT, x1 - x0)
    pad_y = max(CONTEXT, y1 - y0)
    width, height = image.size
    left, top = max(0.0, x0 - pad_x) * width, max(0.0, y0 - pad_y) * height
    right, bottom = min(1.0, x1 + pad_x) * width, min(1.0, y1 + pad_y) * height
    shown = image.crop((round(left), round(top), round(right), round(bottom))).copy()
    ImageDraw.Draw(shown).rectangle(
        (x0 * width - left, y0 * height - top, x1 * width - left, y1 * height - top),
        outline=(230, 0, 0),
        width=max(2, round(max(shown.size) / 300)),
    )
    return _fit(shown, CROP_SIDE)


def _fit(image: Image.Image, side: int) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail((side, side), Image.Resampling.LANCZOS)
    return fitted


def _jpeg(image: Image.Image) -> dict[str, Any]:
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=JPEG_QUALITY)
    data = base64.b64encode(out.getvalue()).decode()
    return {"inlineData": {"mimeType": "image/jpeg", "data": data}}
