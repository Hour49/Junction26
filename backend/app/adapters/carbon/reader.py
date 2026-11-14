"""The Carbon reader: page 1 of a raster drawing read by gemini-4-carbon (brief r8 AS-2).

What is asked and how the replies become a drawing is the contract (contract.py, copied from
confidence's prototypes/carbon-reader/contract.py; .agents/exp/carbon-reader.md section 1). This
module makes the calls:

- `CarbonClient.generate(jpeg, prompt, schema, max_tokens)` is one generateContent call with the
  contract's body; it returns the whole reply. The key goes in a header, never in a URL, note or
  error. The spend guard is asked before the call and charged after a paid reply ("carbon
  reader", at the contract's 4 / 20 USD per million tokens), and `cost` is charged for the trace.
  Any failure (HTTP error, timeout, budget used up, not JSON) is a `GeminiError`.
- `CarbonReader.read(image)`: the page call (the whole page) and the tile calls (`tile_plan`; a
  page of at most TILE px is one tile, asked at the same time as the page call; a larger page
  waits for the page call's plan boxes, then its tiles run WORKERS at a time). Each reply is
  cached under the contract's `cache_name` (the pixel sha256 of the image as decoded, for a tile
  of its crop) as the whole reply, and only once it passes `check_page` / `check_tile`; a cached
  file that does not parse is a miss. A failed call is not cached and is a `None` reply for
  `assemble`, which decides what stays read (contract 1.2).
- `CarbonExtractor` is the `Extractor`.
"""

import base64
import http.client
import io
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from app.adapters.carbon import contract
from app.adapters.carbon.flight import flight
from app.adapters.eight_bit import eight_bit
from app.adapters.raster_ocr.gemini import URL, GeminiError, _status, pixel_digest, reply_text
from app.adapters.whole_file import write_whole
from app.core import cost
from app.core.drawing.model import Room
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles
from app.core.spend import SpendGuard

WORKERS = 4  # calls in flight at once for one read (contract 1.1)
# Carbon calls in flight at once in this process, whatever asks them (the page and tile calls of
# every sheet read at the same time, the printed-scale reader): ingest reads several drawings at
# once (INGEST_GROUPS_IN_FLIGHT), and their calls together stay under this
CALLS_IN_FLIGHT = 8
_in_flight = threading.BoundedSemaphore(CALLS_IN_FLIGHT)
SPENT_AS = "carbon reader"  # its name in the spend guard's ledger

Form = dict[str, Any]
Asked = tuple[Form | None, str | None, float]  # the checked reply or None, why not, dollars


class CarbonModel(Protocol):
    def generate(
        self, jpeg: bytes, prompt: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        """The whole generateContent reply; raises `GeminiError`."""
        ...


class CarbonClient:
    def __init__(self, api_key: str, timeout_s: float, budget: SpendGuard | None = None) -> None:
        if not api_key:
            raise InvalidInputError("GEMINI_API_KEY is empty: the Carbon reader needs a key")
        self._key = api_key
        self._timeout = timeout_s
        self._budget = budget  # GEMINI_BUDGET_USD (app/core/spend.py); None: no limit

    def __repr__(self) -> str:
        return f"CarbonClient({contract.MODEL}/{contract.THINKING})"

    def generate(
        self, jpeg: bytes, prompt: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        if self._budget is not None and (refused := self._budget.exhausted()):
            raise GeminiError(refused)
        body = contract.request_body(base64.b64encode(jpeg).decode(), prompt, schema, max_tokens)
        request = urllib.request.Request(
            f"{URL}/{contract.MODEL}:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._key},
        )
        try:
            with _in_flight, urllib.request.urlopen(request, timeout=self._timeout) as response:
                answer = json.load(response)
        except urllib.error.HTTPError as error:
            raise GeminiError(f"HTTP {error.code} {_status(error)}".strip()) from None
        except (OSError, http.client.HTTPException) as error:  # URLError, timeouts, resets
            raise GeminiError(f"no answer: {type(error).__name__}") from None
        except json.JSONDecodeError:
            raise GeminiError("the answer is not JSON") from None
        if not isinstance(answer, dict):
            raise GeminiError("the answer is not a JSON object")
        usd = contract.price(answer.get("usageMetadata") or {})
        cost.charge(usd)  # a call that was paid for counts even when its text is unusable
        if self._budget is not None:
            self._budget.charge(usd, SPENT_AS)
        return answer


def jpeg(image: Image.Image) -> bytes:
    """An image (the page or a tile's crop) as sent: RGB, `sent_size` (Lanczos), JPEG 90."""
    size = contract.sent_size(*image.size)
    if image.mode == "L":  # the same pixels, but the full-size RGB copy is never made
        if size != image.size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        rgb = image.convert("RGB")
    else:
        rgb = image.convert("RGB")
        if size != rgb.size:
            rgb = rgb.resize(size, Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    rgb.save(buffer, format="JPEG", quality=contract.JPEG_QUALITY)
    return buffer.getvalue()


class CarbonReader:
    name = contract.SOURCE

    def __init__(self, model: CarbonModel, cache_dir: Path | None) -> None:
        self._model = model
        self._cache = cache_dir

    def read(self, image: Image.Image) -> Extracted:
        page = eight_bit(image)  # jpeg and pixel_digest convert what they send, a cut at a time
        page.load()  # the pool's threads share it
        width, height = page.size
        with ThreadPoolExecutor(WORKERS, thread_name_prefix="carbon") as pool:
            if max(width, height) <= contract.TILE:  # one tile, the page: both calls at once
                pending = [pool.submit(self._ask, kind, page) for kind in ("page", "tile")]
                (form, why, usd), tile = (job.result() for job in pending)
                tiles: list[contract.Px] | None = [(0, 0, width, height)]
                asked = [tile]
            else:  # the tiles need the page call's plan boxes
                form, why, usd = pool.submit(self._ask, "page", page).result()
                tiles = None if form is None else contract.tile_plan(width, height, _plans(form))
                asked = list(pool.map(lambda box: self._ask("tile", page.crop(box)), tiles or []))
        cost.charge(usd + sum(paid for _, _, paid in asked))  # paid on the pool's threads
        found = contract.assemble(
            width,
            height,
            form,
            tiles if form is not None else None,
            [checked for checked, _, _ in asked] if form is not None else [],
            why,
        )
        failed = [said for _, said, _ in asked if said is not None]
        if form is not None and failed:  # assemble counts them; say the first reason too
            found["notes"].append(f"carbon: {failed[0]}")
        return _extracted(found)

    def _ask(self, kind: str, image: Image.Image) -> Asked:
        """One call's checked reply (from the cache or paid for), or None and why not; and what
        it cost on this thread."""
        before = cost.mark()
        name = contract.cache_name(kind, pixel_digest(image))
        path = None if self._cache is None else self._cache / name
        shared = path if kind == "page" else None  # the printed-scale reader asks it too
        with flight(shared):
            check = contract.check_page if kind == "page" else contract.check_tile
            if path is not None and path.is_file():
                try:
                    return check(json.loads(reply_text(json.loads(path.read_text())))), None, 0.0
                except (ValueError, GeminiError, AttributeError, TypeError, KeyError, IndexError):
                    pass  # a cached file that does not parse is a miss
            prompt, schema, tokens = (
                (contract.PAGE_PROMPT, contract.PAGE_SCHEMA, contract.PAGE_MAX_TOKENS)
                if kind == "page"
                else (contract.TILE_PROMPT, contract.TILE_SCHEMA, contract.TILE_MAX_TOKENS)
            )
            try:
                answer = self._model.generate(jpeg(image), prompt, schema, tokens)
                form = check(json.loads(reply_text(answer)))
            except GeminiError as error:
                return None, f"the {kind} call failed: {error}", cost.since(before)
            except ValueError as error:  # not JSON, or not the form (contract.ReplyError)
                return None, f"the {kind} reply is not the form: {error}", cost.since(before)
            except (AttributeError, TypeError, KeyError, IndexError) as error:  # an odd envelope
                said = type(error).__name__
                return None, f"the {kind} reply is not the form: {said}", cost.since(before)
            if path is not None:
                write_whole(path, json.dumps(answer, ensure_ascii=False))
            return form, None, cost.since(before)


def _plans(form: Form) -> list[contract.Frac]:
    """The page reply's plan boxes, as `tile_plan` takes them."""
    entries = (entry for entry in form["plans"] if isinstance(entry, dict))
    boxes = (contract.box_of(entry.get("box_2d")) for entry in entries)
    return [box for box in boxes if box is not None]


def _extracted(found: dict[str, Any]) -> Extracted:
    """`assemble`'s parts as an `Extracted`; its `facts` are already in the notes (contract
    1.5)."""
    parts = ("scale", "plans", "elements", "rooms", "tables", "read", "notes")
    return Extracted.model_validate({"method": "detector", **{key: found[key] for key in parts}})


RoomPolicy = Callable[[Sequence[Room]], Sequence[Room]]


class CarbonExtractor:
    """The Carbon reader behind the `Extractor` port. `room_policy` (ROOM_POLICY) retypes its
    rooms when it reads a sheet on its own, as the composite does for any rooms source."""

    def __init__(
        self, files: DrawingFiles, reader: CarbonReader, room_policy: RoomPolicy | None = None
    ) -> None:
        self._files = files
        self._reader = reader
        self._room_policy = room_policy

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        with Image.open(io.BytesIO(self._files.read(source.path))) as image:
            found = self._reader.read(image)
        if self._room_policy is None or not found.rooms:
            return found
        return found.model_copy(update={"rooms": tuple(self._room_policy(found.rooms))})
