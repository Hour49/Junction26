"""Rooms of a raster plan read by Gemini (prototypes/ocr arm G4).

On val (376 CubiCasa sheets) Gemini typing every room from its label or furniture beat the OCR
(arm A2d) and the self-hosted VLM (arm C4) on every asked room family; bathrooms it lists twice,
so bathrooms with the same label count once (val: 22 questions fixed, none broken). Kitchens stay
below the prior (.agents/exp/ocr.md, arm G). This module reproduces arm G4:

- `GeminiClient` sends one page to generateContent (thinking "low": the default thinking cost
  three times as much for the same counts) and returns the reply text. The key goes in a request
  header, never in a URL, a note or an error. Any failure (HTTP error, timeout, a blocked or empty
  answer) is a `GeminiError`.
- `GeminiRoomReader` caches each reply on disk under the sha256 of the decoded page (RGB pixels
  and size, not the file's bytes: the same plan saved again or with bytes appended is the same
  page), the prompt version, the model and the thinking level, so a page read once is never paid
  for again and gives the same rooms every time. Gemini itself does not: fresh reads of one page
  differ (seed and temperature 0 were tried, QA R1-1-5).
- `GeminiRoomExtractor` is the `Extractor`. When Gemini fails, the sheet's rooms are not read
  (`read` is empty and a note says why): the answer stays unknown, and nothing falls back to
  another reader behind the user's back.
"""

import base64
import hashlib
import http.client
import io
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from PIL import Image

from app.adapters.whole_file import write_whole
from app.core.drawing.model import Room, RoomType, Scale
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles

URL = "https://generativelanguage.googleapis.com/v1beta/models"
PROMPT_VERSION = "rooms2g-1"  # change it with PROMPT or the page encoding: the cache key holds it
MAX_SIDE = 2048  # the page is resized (up or down) to this long side, as on val
MAX_TOKENS = 16384
LOOP = 6  # one text more than this many times on one row or column is a generation loop
PROMPT = (
    "This is a floor plan, most often Finnish; the page may be rotated or mirrored. List every "
    "room of the plan, one entry per room, with its type, chosen from: bedroom (MH, makuuhuone, "
    "a room with a bed), kitchen (K, KK, KT, keittiö, keittokomero, an open kitchen counts too), "
    "bathroom (KPH, PH, PESUH, KH, PSH: shower or bath), wc (a separate toilet room, WC), sauna "
    "(S, SAUNA), balcony (PARVEKE, also glazed), living (OH, olohuone, RUOK, dining), hall (ET, "
    "TK, AULA, eteinen), storage (VH, VAR, KHH, wardrobe, utility), outdoor (terrace, yard, "
    "porch), other. Use the printed label when there is one, else the furniture. Answer with "
    'JSON only: [{"type": "bedroom", "label": "MH", "box_2d": [ymin, xmin, ymax, xmax]}, ...], '
    'label "" when nothing is printed, box_2d around the room in 0-1000 coordinates of the image. '
    "Each room once: never repeat an entry. A balcony (PARVEKE, LASITETTU PARVEKE) is type "
    "balcony, not outdoor. On a mirrored page the text reads backwards: HM is MH, HV is VH."
)
TYPES = ("bedroom", "kitchen", "bathroom", "wc", "sauna", "balcony", "living", "hall", "storage",
         "outdoor", "other")  # fmt: skip


class GeminiError(Exception):
    """Gemini gave no usable answer; the message is safe to show (no key, no image)."""


class RoomModel(Protocol):
    @property
    def name(self) -> str: ...

    def ask(self, png: bytes, prompt: str) -> str:
        """The reply text to `prompt` about the PNG page; raises `GeminiError`."""
        ...


class GeminiClient:
    def __init__(self, api_key: str, model: str, timeout_s: float, thinking: str = "low") -> None:
        if not api_key:
            raise InvalidInputError("GEMINI_API_KEY is empty: the Gemini room reader needs a key")
        self._key = api_key
        self.model = model
        self._timeout = timeout_s
        self.thinking = thinking

    @property
    def name(self) -> str:
        return f"{self.model}/{self.thinking}"

    def __repr__(self) -> str:
        return f"GeminiClient({self.name})"

    def ask(self, png: bytes, prompt: str) -> str:
        body = {
            "contents": [{"role": "user", "parts": [
                {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png).decode()}},
                {"text": prompt},
            ]}],
            "generationConfig": {
                "maxOutputTokens": MAX_TOKENS,
                "responseMimeType": "application/json",
                "thinkingConfig": {"thinkingLevel": self.thinking},
            },
        }  # fmt: skip
        request = urllib.request.Request(
            f"{URL}/{self.model}:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._key},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                answer = json.load(response)
        except urllib.error.HTTPError as error:
            raise GeminiError(f"HTTP {error.code} {_status(error)}".strip()) from None
        except (OSError, http.client.HTTPException) as error:  # URLError, timeouts, resets
            raise GeminiError(f"no answer: {type(error).__name__}") from None
        except json.JSONDecodeError:
            raise GeminiError("the answer is not JSON") from None
        return reply_text(answer)


def _status(error: urllib.error.HTTPError) -> str:
    """Google's error status word (PERMISSION_DENIED...), never the raw body."""
    try:
        status = json.loads(error.read()).get("error", {}).get("status", "")
    except (json.JSONDecodeError, OSError, AttributeError):
        return ""
    return status if isinstance(status, str) and status.replace("_", "").isalpha() else ""


def reply_text(answer: dict[str, Any]) -> str:
    """The text of the first candidate, thought parts left out; a blocked or empty answer is an
    error, not zero rooms."""
    candidates = answer.get("candidates") or []
    content = (candidates[0].get("content") or {}) if candidates else {}
    parts = content.get("parts") or []
    text = "".join(str(part.get("text", "")) for part in parts if not part.get("thought"))
    if not text.strip():
        reason = candidates[0].get("finishReason", "") if candidates else "no candidates"
        raise GeminiError(f"empty answer ({reason})")
    return text


def encode(image: Image.Image) -> bytes:
    """The page as sent on val: RGB, long side MAX_SIDE (Lanczos, up or down), PNG."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    scale = MAX_SIDE / max(w, h)
    if scale != 1:
        rgb = rgb.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    rgb.save(buffer, format="PNG")
    return buffer.getvalue()


def parse_rooms(text: str) -> list[tuple[RoomType, str, tuple[float, float, float, float]]]:
    """(type, label, box) per room of the reply. Every complete {...} object counts, so a reply
    cut at the token cap keeps what came before the cut; exact repeats count once; a text given
    more than LOOP times, all on one row or one column, is a generation loop and is dropped; a
    type outside TYPES is dropped; bathrooms with the same label count once. Boxes: page
    fractions, the whole page when unusable."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(r"\{[^{}]*\}", text):
        try:
            item = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict) or "type" not in item:
            continue
        item = cast(dict[str, Any], item)
        item["text"] = str(item.get("label") or "")
        b = item.get("box_2d")
        if isinstance(b, list) and len(cast(list[Any], b)) == 4:
            b = cast(list[Any], b)
            item["box"] = [b[1], b[0], b[3], b[2]]
        key = json.dumps([item["text"], str(item.get("type")), item.get("box")])
        if key not in seen:
            seen.add(key)
            items.append(item)
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(f"{item['text']}|{item.get('type')}", []).append(item)
    looped = {
        key
        for key, group in groups.items()
        if len(group) > LOOP
        and (boxes := [i["box"] for i in group if _usable(i.get("box"))])
        and (len({b[0] for b in boxes}) == 1 or len({b[1] for b in boxes}) == 1)
    }
    rooms: list[tuple[RoomType, str, tuple[float, float, float, float]]] = []
    bathrooms: set[str] = set()
    for item in items:
        kind = item.get("type")
        if f"{item['text']}|{kind}" in looped or kind not in TYPES:
            continue
        if kind == "bathroom":  # listed twice more often than drawn twice: one per label
            if item["text"] in bathrooms:
                continue
            bathrooms.add(item["text"])
        rooms.append((cast(RoomType, kind), item["text"].strip(), _fractions(item.get("box"))))
    return rooms


def _usable(box: object) -> bool:
    return (
        isinstance(box, list)
        and len(cast(list[Any], box)) == 4
        and all(isinstance(v, int | float) for v in cast(list[Any], box))
    )


def _fractions(box: object) -> tuple[float, float, float, float]:
    if not _usable(box):
        return (0.0, 0.0, 1.0, 1.0)
    x1, y1, x2, y2 = (float(v) for v in cast(list[float], box))
    out = (
        max(0.0, min(x1, x2) / 1000),
        max(0.0, min(y1, y2) / 1000),
        min(1.0, max(x1, x2) / 1000),
        min(1.0, max(y1, y2) / 1000),
    )
    return out if out[2] > out[0] and out[3] > out[1] else (0.0, 0.0, 1.0, 1.0)


@dataclass(frozen=True)
class GeminiRooms:
    rooms: tuple[tuple[RoomType, str, tuple[float, float, float, float]], ...]
    note: str


def pixel_digest(image: Image.Image) -> str:
    """sha256 of the page as decoded (RGB, as `encode` sends it) and its size."""
    rgb = image.convert("RGB")
    return hashlib.sha256(f"{rgb.width}x{rgb.height}:".encode() + rgb.tobytes()).hexdigest()


class GeminiRoomReader:
    def __init__(self, model: RoomModel, cache_dir: Path | None) -> None:
        self._model = model
        self._cache = cache_dir

    def read(self, image: Image.Image) -> GeminiRooms:
        """Raises `GeminiError` when Gemini gives no usable answer (nothing is cached then)."""
        digest = pixel_digest(image)
        name = re.sub(r"[^A-Za-z0-9.-]", "_", f"{digest}-{PROMPT_VERSION}-{self._model.name}")
        path = None if self._cache is None else self._cache / f"{name}.json"
        if path is not None and path.is_file():
            text = json.loads(path.read_text())["reply"]
            how = "cached reply"
        else:
            start = time.monotonic()
            text = self._model.ask(encode(image), PROMPT)
            how = f"read in {time.monotonic() - start:.1f} s"
            if path is not None:
                write_whole(path, json.dumps({"reply": text}, ensure_ascii=False))
        rooms = tuple(parse_rooms(text))
        return GeminiRooms(rooms, f"{self._model.name}: {len(rooms)} rooms, {how}")


class GeminiRoomExtractor:
    """Arm G4 behind the `Extractor` port; it looks for rooms only (`read` is ("room",))."""

    def __init__(self, files: DrawingFiles, gemini: GeminiRoomReader) -> None:
        self._files = files
        self._gemini = gemini

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        data = self._files.read(source.path)
        with Image.open(io.BytesIO(data)) as image:
            try:
                found = self._gemini.read(image)
            except GeminiError as error:
                return Extracted(
                    method="printed_label",
                    scale=Scale(status="no_scale"),
                    read=(),
                    notes=(f"gemini: rooms not read: {error}",),
                )
        rooms = tuple(
            Room(
                id=f"r{index}",
                type=kind,
                label=label or None,
                page=1,
                box=box,
                outdoor=kind in ("balcony", "outdoor"),
                attrs={"reader": "gemini"},
            )
            for index, (kind, label, box) in enumerate(found.rooms, start=1)
        )
        return Extracted(
            method="printed_label",
            scale=Scale(status="no_scale"),
            rooms=rooms,
            read=("room",),
            notes=(f"gemini: {found.note} (arm G4)",),
        )
