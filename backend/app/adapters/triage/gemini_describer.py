"""Triage step 2 by Gemini (decision 0010 sections 3 and 8): one gemini-3.5-flash call per image
that is not a floor plan fills the description form (what_it_is, shows_building, visible_text,
text_seen, language, subject) and its long text (detail, text).

The prompt and schema are prototypes/triage-describe's describe-5, word for word, so the
numbers measured on it hold here (.agents/exp/triage-describer.md). describe-5 is describe-4 with
two rules for the long text: a count only when every item can be counted, and a date only when
it is printed. On the same 50 images a blind count found 44 right, 6 minor errors, 0 wrong
(describe-4: 43, 7, 0), with no dates read from the style and no invented views; the form
fields matched describe-4's on 47 of 50 (what_it_is) and 50 of 50 (shows_building).
describe-4's what_it_is was right on 48 of 55 hand-checked hard rows. Price: 0.42 USD for the
50, about 8.5 USD per 1,000. Thinking "minimal", temperature 0.2, the image as a JPEG (quality
90) at most 2,048 px on its long side, the long text first in the schema so the form fields
come after the model has looked.

- Replies are cached on disk by the file's sha256, the prompt version and the model, as the
  prototype names them, so a file is paid for once. What is cached is the model's form as it
  came; the cuts and the contact-data rule below run on every read.
- The cost of a call comes from its `usageMetadata` and is charged (app/core/cost.py) even when
  the reply is unusable; a cached reply costs nothing.
- A failed call (HTTP error, timeout, a refusal such as RECITATION, a form that is incomplete) is
  `Unavailable` with the reason, and nothing is cached: nothing is guessed, and no other prompt
  is tried.
- Phone numbers and e-mail addresses are taken out of every text field (orchestrator,
  2026-11-14: "drop every phone number and e-mail address from visible_text and detail with a
  tested regex, firm or private"). Street addresses and firm names stay. Names of people in
  photos are kept out by the prompt.
"""

import base64
import hashlib
import http.client
import io
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol

from PIL import Image
from pydantic import ValidationError

from app.adapters.pdfium_lock import PDFIUM
from app.adapters.raster_ocr.gemini import URL, GeminiError, _status, price, reply_text
from app.adapters.whole_file import write_whole
from app.core import cost
from app.core.errors import InvalidInputError
from app.core.ingest.model import Classified, Description, Unavailable

MODEL = "gemini-3.5-flash"
THINKING = "minimal"  # 0 thought tokens; the pilot's form was right on 18 of 20
TEMPERATURE = 0.2
MAX_SIDE = 2048
JPEG_QUALITY = 90
MAX_TOKENS = 4096
PROMPT_VERSION = "describe-5"  # change it with PROMPT, SCHEMA or the image encoding
MAX_VISIBLE, MAX_DETAIL, MAX_SEEN = 2000, 4000, 20  # Description's limits (0010 section 8)
UNAVAILABLE = "the describer could not answer"

# 0010 section 8: photograph|artwork|text_page|object|music|map|drawing|other, in this order
KINDS = {
    "photograph": "a camera photograph of a scene, people, a building, a room, a street sign or "
    "an object. A camera photo of a drawing sheet (on a table, wall or mount) is classed by the "
    "drawing on it, not as a photograph",
    "artwork": "a painting, an artistic print or engraving, or an illustration that is not a "
    "technical drawing",
    "text_page": "mostly text: a cover or title sheet (also one with a small location map or "
    "vignette), a poster, letter, document, form, table or list",
    "object": "a drawing or print (not a photograph) of one loose object: furniture, a vase, "
    "a fossil, an instrument, lettering",
    "music": "a music score",
    "map": "a map of a town, a region or a larger area (a site plan of one plot or building "
    "group is a drawing)",
    "drawing": "an architectural or engineering drawing of a building, a part of one, a site, "
    "or a structure such as a bridge, dam or machine: elevation, section, site plan, "
    "construction detail, perspective, axonometric, or a floor plan",
    "other": "none of these (a blank sheet, an unreadable fragment)",
}

PROMPT = (
    "This image comes from an architectural archive and was judged not to be a floor plan. "
    "Describe it so that people and software can later search it and judge whether it belongs "
    "to a building project. Look only at what is visible. Answer in English, as JSON. Never name "
    "or identify people seen in a photograph (write 'a person', 'two people'), and never write "
    "the contact data of private people (phone numbers, e-mail addresses, home addresses) or "
    "number plates, in any field.\n\n"
    "detail: a description of a paragraph or more (about 120 to 250 words, at most 4,000 "
    "characters). Say what kind of picture it is (photograph, technical drawing, print, page of "
    "text, ...), what it shows and how the sheet is laid out; the building or object if there "
    "is one (type, storeys, roof, facade, materials, style); the drawing technique or the "
    "photo's conditions; what the text on it says, in short (title, place, date, scale, the "
    "firm or office that made it); and its condition (paper, stains, mount, a camera photo of a "
    "sheet). Do not guess what is not visible: when unsure, say 'possibly' or 'unclear'. Give the "
    "number of repeated things (bays, panels, windows, columns, clusters, sheets) only when you "
    "can count every one of them; otherwise write 'several', 'many' or 'about N'. Give a date, "
    "year or century only when it is printed on the sheet; a period you judge from the style is "
    "said as such ('in an 18th-century style'), never as the date.\n\n"
    "text: 1 to 3 plain sentences that sum up detail.\n\n"
    "visible_text: every legible word, as printed (its own language and spelling), titles "
    "first, then the other text in reading order, line breaks kept (one line per line of text "
    "or label). At most 2,000 characters: on a sheet with more text, keep titles, labels and "
    "notes and leave out repeated dimension figures. Do not invent text you cannot read. Empty "
    "string when nothing is readable. Building names, street and place names, firms, "
    "institutions, dates and scales stay.\n\n"
    "text_seen: the title-block and caption items of visible_text (title, place, date, scale, "
    "firm), one per item, the most important first, at most 20; [] when there are none.\n\n"
    "language: the ISO 639-1 code of most of visible_text (fi, sv, de, en, nl, fr, la, ...), "
    "or null (not the word 'null') when there is no text.\n\n"
    "what_it_is: the one value that fits best:\n"
    + "".join(f"- {key}: {words}\n" for key, words in KINDS.items())
    + "\nshows_building: true when the picture shows a building or a part of one, drawn or "
    "photographed, outside or inside: elevations, sections, details of building parts, "
    "perspectives, site plans that draw building outlines, a photograph with a building in it. "
    "false otherwise: bridges, machines, landscapes, town maps, text pages, music, people, "
    "objects.\n\n"
    "subject: a short label of at most 12 words, e.g. 'south elevation of a two-storey timber "
    "house'."
)

SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "detail": {"type": "STRING"},
        "text": {"type": "STRING"},
        "visible_text": {"type": "STRING"},
        "text_seen": {"type": "ARRAY", "items": {"type": "STRING"}, "maxItems": 20},
        "language": {"type": "STRING", "nullable": True},
        "what_it_is": {"type": "STRING", "enum": list(KINDS)},
        "shows_building": {"type": "BOOLEAN"},
        "subject": {"type": "STRING"},
    },
    "required": ["detail", "text", "visible_text", "text_seen", "language", "what_it_is",
                 "shows_building", "subject"],
    # the long text first: the form fields are then given after the model has looked closely
    "propertyOrdering": ["detail", "text", "visible_text", "text_seen", "language", "what_it_is",
                         "shows_building", "subject"],
}  # fmt: skip

# The prototype's cache names hold this, so its paid replies are read here as they are
PROMPT_SHA = hashlib.sha256((PROMPT + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest()

# Contact data, each with the digits a match needs to count (fewer: a level, date or scale)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# a phone or fax label (fi, sv, de, en, fr) and the number after it on the same line
_LABELLED = re.compile(
    r"\b(?:puh(?:elin)?|matkapuh(?:elin)?|tel(?:efon|ephone|éphone|efax)?|phone|fax|telefax|"
    r"gsm|mob(?:il|ile)?|tfn)\b\.?[ \t]*(?:n[or]o?\.?[ \t]*)?:?[ \t]*\+?\(?\d[\d \t()/.-]*\d",
    re.IGNORECASE,
)
_INTERNATIONAL = re.compile(r"(?<![\w+])\+\d{1,3}[ \t.-]?\(?\d{1,4}\)?(?:[ \t.-]?\d{1,4}){1,5}")
_AREA_CODE = re.compile(
    r"(?<![\w.,/+-])0\d{1,3}-[ \t]?\d{2,4}(?:[ \t]\d{2,4}){0,3}(?![\w/-]|[.,]\d)"
)
CONTACTS: tuple[tuple[re.Pattern[str], int], ...] = (
    (_EMAIL, 0),
    (_LABELLED, 5),  # "PUH 651088", "Tel. (09) 123 456"
    (_INTERNATIONAL, 8),  # "+358 9 123 4567", never a level such as "+108.65"
    (_AREA_CODE, 7),  # "09-123 4567", "040-123 4567"
)


def without_contacts(text: str) -> str:
    """`text` with every e-mail address and phone number found taken out. A line left empty
    goes; the rest of a line stays. A national number with no label, no "+" and no area-code
    dash is not caught: it cannot be told from a row of dimensions."""
    lines: list[str] = []
    for line in text.split("\n"):
        kept = line
        for pattern, digits in CONTACTS:
            kept = pattern.sub(lambda found, n=digits: _drop(found, n), kept)
        if kept != line:
            kept = re.sub(r"[ \t]{2,}", " ", kept).strip()
            if not kept:
                continue
        lines.append(kept)
    return "\n".join(lines)


def _drop(found: re.Match[str], digits: int) -> str:
    said = found.group(0)
    return "" if sum(char.isdigit() for char in said) >= digits else said


def cut(text: str, limit: int) -> str:
    """`text` at most `limit` characters long, cut at its last line break (else its last space)
    that fits."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    at = head.rfind("\n")
    if at <= 0:
        at = head.rfind(" ")
    return (head[:at] if at > 0 else head).rstrip()


def encode(data: bytes) -> bytes:
    """The image as sent when measured: RGB, long side at most MAX_SIDE (never enlarged), JPEG
    quality 90. A PDF scan sends its first page, rendered to MAX_SIDE."""
    if data.startswith(b"%PDF-"):
        import pypdfium2

        with PDFIUM:
            pdf = pypdfium2.PdfDocument(data)
            try:
                page = pdf[0]
                image = page.render(scale=MAX_SIDE / max(page.get_size())).to_pil()
            finally:
                pdf.close()
    else:
        image = Image.open(io.BytesIO(data))
    rgb = image.convert("RGB")
    rgb.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    rgb.save(out, format="JPEG", quality=JPEG_QUALITY)
    return out.getvalue()


def request_body(jpeg: bytes, thinking: str) -> dict[str, Any]:
    return {
        "contents": [{"role": "user", "parts": [
            {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(jpeg).decode()}},
            {"text": PROMPT},
        ]}],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "maxOutputTokens": MAX_TOKENS,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "thinkingConfig": {"thinkingLevel": thinking},
        },
    }  # fmt: skip


class DescribeModel(Protocol):
    @property
    def name(self) -> str: ...

    def ask(self, jpeg: bytes) -> dict[str, Any]:
        """The generateContent answer about the JPEG; raises `GeminiError`."""
        ...


class GeminiDescribeClient:
    def __init__(
        self, api_key: str, timeout_s: float, model: str = MODEL, thinking: str = THINKING
    ) -> None:
        if not api_key:
            raise InvalidInputError("GEMINI_API_KEY is empty: the Gemini describer needs a key")
        self._key = api_key
        self.model = model
        self.thinking = thinking
        self._timeout = timeout_s

    @property
    def name(self) -> str:
        return f"{self.model}-{self.thinking}"

    def __repr__(self) -> str:
        return f"GeminiDescribeClient({self.name})"

    def ask(self, jpeg: bytes) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{URL}/{self.model}:generateContent",
            data=json.dumps(request_body(jpeg, self.thinking)).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._key},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise GeminiError(f"HTTP {error.code} {_status(error)}".strip()) from None
        except (OSError, http.client.HTTPException) as error:  # URLError, timeouts, resets
            raise GeminiError(f"no answer: {type(error).__name__}") from None
        except json.JSONDecodeError:
            raise GeminiError("the answer is not JSON") from None


class GeminiDescriber:
    """The `Describer` port (app/core/ingest/ports.py) on Gemini."""

    def __init__(self, model: DescribeModel, cache_dir: Path) -> None:
        self._model = model
        self._cache = cache_dir

    def describe(self, image: bytes, classified: Classified) -> Description | Unavailable:
        digest = hashlib.sha256(image).hexdigest()
        name = f"{digest}-{PROMPT_VERSION}-{PROMPT_SHA[:12]}-{self._model.name}"
        path = self._cache / f"{re.sub(r'[^A-Za-z0-9.-]', '_', name)}.json"
        if path.is_file():
            return self._description(json.loads(path.read_text())["form"], 0.0)
        try:
            jpeg = encode(image)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            return Unavailable(note=f"{UNAVAILABLE}: the image could not be opened ({error})")
        try:
            answer = self._model.ask(jpeg)
        except GeminiError as error:
            return Unavailable(note=f"{UNAVAILABLE}: {error}")
        usd = price(answer)
        cost.charge(usd)  # a call that was paid for counts even when its reply is unusable
        try:
            form = json.loads(reply_text(answer))
            found = self._description(form, usd)
        except GeminiError as error:
            return Unavailable(note=f"{UNAVAILABLE}: {error}")
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError, ValidationError):
            return Unavailable(note=f"{UNAVAILABLE}: the answer is not the description form")
        stored = {"form": form, "usage": answer.get("usageMetadata", {}), "usd": usd,
                  "model": self._model.name, "prompt": PROMPT_VERSION}  # fmt: skip
        write_whole(path, json.dumps(stored, ensure_ascii=False))
        return found

    def _description(self, form: dict[str, Any], usd: float) -> Description:
        """The Description of a form as the model gave it; raises ValidationError (or KeyError,
        TypeError, AttributeError) when the form is incomplete or of the wrong types."""
        if not isinstance(form["text_seen"], list):
            raise TypeError("text_seen is not a list")
        language = form["language"]
        if language is not None and str(language).strip().casefold() in ("", "null", "none"):
            language = None  # the pilot once had the word "null"
        seen = (without_contacts(str(item)).strip() for item in form["text_seen"])
        return Description.model_validate(
            {
                "text": without_contacts(form["text"]),
                "subject": without_contacts(form["subject"]),
                "text_seen": tuple(item for item in seen if item)[:MAX_SEEN],
                "language": language,
                "model": f"{self._model.name}, {PROMPT_VERSION}",
                "cost_usd": usd,
                "what_it_is": form["what_it_is"],
                "shows_building": form["shows_building"],
                "visible_text": cut(without_contacts(form["visible_text"]), MAX_VISIBLE),
                "detail": cut(without_contacts(form["detail"]), MAX_DETAIL),
            }
        )
